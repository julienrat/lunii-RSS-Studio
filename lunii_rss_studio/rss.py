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
        if max_episodes is not None and i >= max_episodes:
            break
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
    return info


def filter_episodes(feed: FeedInfo, episode_ids: list[str]) -> FeedInfo:
    """Ne garde que les épisodes sélectionnés et renumérote pour le dossier Studio."""
    wanted = set(episode_ids)
    selected = [e for e in feed.episodes if e.entry_id in wanted]
    if not selected:
        raise ValueError("Aucun épisode sélectionné ne correspond au flux RSS")
    for i, ep in enumerate(selected, start=1):
        ep.index = i
    feed.episodes = selected
    return feed


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
