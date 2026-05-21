"""Téléchargement et parsing de flux RSS podcast."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import feedparser
import requests

ProgressFn = Callable[[str], None] | None


@dataclass
class Episode:
    title: str
    audio_url: str
    image_url: str | None
    duration_sec: int
    index: int
    safe_name: str
    entry_id: str


@dataclass
class FeedInfo:
    title: str
    description: str
    image_url: str | None
    episodes: list[Episode] = field(default_factory=list)


@dataclass(frozen=True)
class EpisodeNumber:
    number: int
    group: str
    start: int


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def sanitize_filename(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "episode")[:max_len]


def parse_duration(entry) -> int:
    if hasattr(entry, "itunes_duration") and entry.itunes_duration:
        raw = str(entry.itunes_duration)
        if ":" in raw:
            parts = [int(p) for p in raw.split(":")]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
        try:
            return int(float(raw))
        except ValueError:
            pass
    return 0


def extract_image_url(entry, feed) -> str | None:
    if hasattr(entry, "image") and entry.image and entry.image.get("href"):
        return entry.image.href
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("medium") == "image" or (m.get("type") or "").startswith("image/"):
                return m.get("url")
    if hasattr(entry, "itunes_image") and entry.itunes_image:
        return entry.itunes_image.get("href")
    return None


def episode_entry_id(entry, audio_url: str) -> str:
    """Identifiant stable pour sélectionner un épisode entre aperçu et génération."""
    return entry.get("id") or entry.get("link") or audio_url


_NUMBER_PATTERNS = (
    re.compile(r"(?<!\d)(\d{1,4})\s*/\s*(\d{1,4})(?!\d)"),
    re.compile(r"\b(?:episode|épisode|ep|ép|partie|part|chapitre|ch)\.?\s*(?:n[°o]\s*)?(\d{1,4})\b", re.I),
    re.compile(r"#\s*(\d{1,4})\b"),
    re.compile(r"^\s*(\d{1,4})(?:\s*[-.)_:]|$)"),
)


def _normalize_sort_group(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b(?:episode|épisode|ep|ép|partie|part|chapitre|ch)\b", "", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def extract_episode_number(title: str) -> EpisodeNumber | None:
    """Détecte un numéro d'épisode dans les formes courantes : 1/10, épisode 1, #1, 01 - titre."""
    for pattern in _NUMBER_PATTERNS:
        match = pattern.search(title)
        if not match:
            continue
        number = int(match.group(1))
        if number <= 0:
            continue
        prefix = title[:match.start()]
        if not prefix.strip():
            prefix = "__episodes__"
        group = _normalize_sort_group(prefix)
        return EpisodeNumber(number=number, group=group, start=match.start())
    return None


def renumber_episodes(feed: FeedInfo) -> FeedInfo:
    for i, ep in enumerate(feed.episodes, start=1):
        ep.index = i
    return feed


def sort_numbered_episodes(feed: FeedInfo) -> FeedInfo:
    """
    Trie les épisodes numérotés du premier au dernier.

    Les podcasts publient souvent les entrées RSS du plus récent au plus ancien. Quand les titres
    contiennent une numérotation fiable, on trie chaque série de titres similaire sans mélanger des
    arcs distincts qui recommencent tous à 1/10.
    """
    numbered = [(i, ep, extract_episode_number(ep.title)) for i, ep in enumerate(feed.episodes)]
    detected = [(i, ep, n) for i, ep, n in numbered if n is not None]
    if len(detected) < 2:
        return renumber_episodes(feed)

    groups: dict[str, int] = {}
    for i, _ep, number in detected:
        assert number is not None
        key = number.group or "__episodes__"
        groups.setdefault(key, i)

    sortable_groups = {
        key
        for key in groups
        if len({n.number for _i, _ep, n in detected if (n.group or "__episodes__") == key}) > 1
    }
    if not sortable_groups:
        return renumber_episodes(feed)

    def sort_key(item: tuple[int, Episode, EpisodeNumber | None]) -> tuple[int, int, int, int]:
        original_index, _ep, number = item
        if number is None:
            return (original_index, 1, 0, original_index)
        key = number.group or "__episodes__"
        if key not in sortable_groups:
            return (original_index, 1, number.number, original_index)
        return (groups[key], 0, number.number, original_index)

    feed.episodes = [ep for _i, ep, _number in sorted(numbered, key=sort_key)]
    return renumber_episodes(feed)


def extract_audio_url(entry) -> str | None:
    for link in getattr(entry, "links", []):
        if link.get("type", "").startswith("audio/") or link.get("rel") == "enclosure":
            return link.get("href")
    if hasattr(entry, "enclosures"):
        for enc in entry.enclosures:
            if (enc.get("type") or "").startswith("audio/"):
                return enc.get("href")
    return None


def fetch_feed(rss_url: str, min_duration: int = 0, max_episodes: int | None = None) -> FeedInfo:
    parsed = feedparser.parse(rss_url)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Flux RSS invalide : {parsed.bozo_exception}")

    feed_image = None
    if parsed.feed.get("image") and parsed.feed.image.get("href"):
        feed_image = parsed.feed.image.href
    elif hasattr(parsed.feed, "itunes_image") and parsed.feed.itunes_image:
        feed_image = parsed.feed.itunes_image.get("href")

    info = FeedInfo(
        title=parsed.feed.get("title", "Podcast"),
        description=parsed.feed.get("subtitle") or parsed.feed.get("description", ""),
        image_url=feed_image,
    )

    for i, entry in enumerate(parsed.entries):
        audio_url = extract_audio_url(entry)
        if not audio_url:
            continue
        duration = parse_duration(entry)
        if min_duration and duration and duration < min_duration:
            continue
        title = entry.get("title", f"Épisode {i + 1}")
        safe = sanitize_filename(title)
        info.episodes.append(
            Episode(
                title=title,
                audio_url=audio_url,
                image_url=extract_image_url(entry, parsed) or feed_image,
                duration_sec=duration,
                index=len(info.episodes) + 1,
                safe_name=safe,
                entry_id=episode_entry_id(entry, audio_url),
            )
        )
    sort_numbered_episodes(info)
    if max_episodes is not None:
        info.episodes = info.episodes[:max_episodes]
        renumber_episodes(info)
    return info


def filter_episodes(feed: FeedInfo, episode_ids: list[str]) -> FeedInfo:
    """Ne garde que les épisodes sélectionnés, dans l'ordre demandé, puis renumérote."""
    by_id = {e.entry_id: e for e in feed.episodes}
    selected = [by_id[entry_id] for entry_id in episode_ids if entry_id in by_id]
    if not selected:
        raise ValueError("Aucun épisode sélectionné ne correspond au flux RSS")
    feed.episodes = selected
    return renumber_episodes(feed)


def download_file(url: str, dest: Path, progress: ProgressFn = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _log(progress, f"Téléchargement : {dest.name}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    return dest


def download_episodes(
    feed: FeedInfo,
    story_dir: Path,
    menu_name: str = "Épisodes",
    progress: ProgressFn = None,
) -> Path:
    """Crée l'arborescence Studio à partir du flux RSS."""
    menu_dir = story_dir / sanitize_filename(menu_name)
    menu_dir.mkdir(parents=True, exist_ok=True)

    for ep in feed.episodes:
        base = f"{ep.index:02d} - {ep.safe_name}"
        audio_dest = menu_dir / f"{base}.mp3"
        download_file(ep.audio_url, audio_dest, progress)
        # Les .item.png sont créés dans ensure_episode_item_images (plus fiable)

    return menu_dir
