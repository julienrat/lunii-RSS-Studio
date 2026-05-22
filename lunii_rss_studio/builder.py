"""Pipeline unifié : pistes audio → dossier Studio → zip Lunii."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Callable

from .audio import convert_audio_for_lunii, generate_story_titles
from .chaptering import apply_chaptering
from .config import WORK_DIR
from .images import apply_chapter_image_texts, ensure_thumbnail, generate_image_hf, process_story_images
from .items import ensure_episode_item_images, ensure_menu_items
from .pack_spg import run_studio_pack_generator
from .rss import FeedInfo, Episode, download_episodes, download_file, fetch_feed, filter_episodes, sanitize_filename

ProgressFn = Callable[[str], None] | None
_CHAPTER_SUFFIX_RE = re.compile(r"(, chapitre \d+)$", re.I)


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _safe_track_name(title: str) -> str:
    safe = sanitize_filename(title, max_len=200)
    match = _CHAPTER_SUFFIX_RE.search(safe)
    if not match or len(safe) <= 80:
        return sanitize_filename(title)

    suffix = match.group(1)
    prefix = safe[: 80 - len(suffix)].rstrip(" ,-–—")
    return f"{prefix}{suffix}" or sanitize_filename(title)


def tracks_to_feed(title: str, tracks: list[tuple[str, Path]], description: str = "", image_url: str | None = None) -> FeedInfo:
    feed = FeedInfo(title=title, description=description, image_url=image_url)
    for i, (t, _) in enumerate(tracks, start=1):
        safe = _safe_track_name(t)
        feed.episodes.append(
            Episode(
                title=t,
                audio_url="",
                image_url=None,
                duration_sec=0,
                index=i,
                safe_name=safe,
                entry_id=f"track:{i}:{safe}",
            )
        )
    return feed


def install_tracks(
    menu_dir: Path,
    tracks: list[tuple[str, Path]],
    progress: ProgressFn = None,
) -> FeedInfo:
    """Copie les MP3 dans le menu Studio et retourne le feed correspondant."""
    menu_dir.mkdir(parents=True, exist_ok=True)
    title = menu_dir.parent.name
    feed = tracks_to_feed(title, tracks)
    chapter_tmp_dirs: set[Path] = set()
    expected_mp3s: set[Path] = set()

    for ep, (_, src) in zip(feed.episodes, tracks):
        dest = menu_dir / f"{ep.index:02d} - {ep.safe_name}.mp3"
        expected_mp3s.add(dest.resolve())
        if any(parent.name == "_chapitres_tmp" for parent in src.parents):
            chapter_tmp_dirs.add(next(parent for parent in src.parents if parent.name == "_chapitres_tmp"))
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        convert_audio_for_lunii(dest, progress=progress)
        _log(progress, f"Piste : {dest.name}")

    for stale in menu_dir.glob("*.mp3"):
        if stale.name == "0-item.mp3" or stale.name.endswith(".item.mp3"):
            continue
        if stale.resolve() not in expected_mp3s:
            stale.unlink(missing_ok=True)

    for tmp_dir in chapter_tmp_dirs:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return feed


def finalize_story_pack(
    feed: FeedInfo,
    story_dir: Path,
    *,
    menu_name: str = "Épisodes",
    pack_title: str | None = None,
    ai_thumbnail_prompt: str | None = None,
    ai_episode_images: bool = False,
    hf_token: str | None = None,
    skip_tts: bool = False,
    skip_pack_zip: bool = False,
    lang: str = "fr",
    tts_engine: str = "gtts",
    tts_style_prompt: str | None = None,
    chapter_image_text: bool = False,
    chapter_image_font: str = "dejavu-sans-bold",
    chapter_image_font_size: int = 46,
    chapter_image_template: str = "Chapitre {n}",
    output_base: Path | None = None,
    progress: ProgressFn = None,
) -> dict:
    """Images, TTS, metadata et zip Studio."""
    menu_folder = sanitize_filename(menu_name)
    menu_dir = story_dir / menu_folder

    thumb_prompt = ai_thumbnail_prompt or (
        f"Illustration pour livre audio, {feed.title}, style classique"
    )
    ensure_thumbnail(
        story_dir,
        feed.image_url,
        ai_thumbnail_prompt or (thumb_prompt if not feed.image_url else None),
        download_file,
        token=hf_token,
        progress=progress,
    )

    if menu_dir.is_dir():
        ensure_episode_item_images(menu_dir, feed, story_dir, progress=progress)

    if ai_episode_images:
        for ep in feed.episodes:
            item_png = menu_dir / f"{ep.index:02d} - {ep.safe_name}.item.png"
            try:
                generate_image_hf(f"Illustration : {ep.title}", item_png, token=hf_token, progress=progress)
            except Exception as e:
                _log(progress, f"IA ignorée : {e}")

    if menu_dir.is_dir():
        apply_chapter_image_texts(
            menu_dir,
            feed,
            enabled=chapter_image_text,
            font_key=chapter_image_font,
            font_size=chapter_image_font_size,
            template=chapter_image_template,
            progress=progress,
        )

    process_story_images(story_dir, progress=progress)

    title = pack_title or feed.title
    if not skip_tts:
        generate_story_titles(
            story_dir,
            pack_title=title,
            menu_names=[menu_folder],
            lang=lang,
            tts_engine=tts_engine,
            hf_token=hf_token,
            tts_style_prompt=tts_style_prompt,
            progress=progress,
        )
    if menu_dir.is_dir():
        ensure_menu_items(
            story_dir,
            menu_name,
            menu_label=menu_name,
            lang=lang,
            tts_engine=tts_engine,
            hf_token=hf_token,
            tts_style_prompt=tts_style_prompt,
            progress=progress,
        )

    (story_dir / "metadata.json").write_text(
        json.dumps({
            "title": feed.title,
            "description": (feed.description or "")[:500],
            "format": "v1",
            "version": 1,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    output_base = output_base or WORK_DIR
    zip_path = None
    if not skip_pack_zip:
        zip_path = run_studio_pack_generator(story_dir, output_base, lang=lang, progress=progress)

    return {
        "feed_title": feed.title,
        "story_dir": str(story_dir),
        "episodes": len(feed.episodes),
        "zip_path": str(zip_path) if zip_path else None,
    }


def build_story_from_rss(
    rss_url: str,
    *,
    output_base: Path | None = None,
    max_episodes: int | None = 10,
    min_duration: int = 0,
    menu_name: str = "Épisodes",
    pack_title: str | None = None,
    ai_thumbnail_prompt: str | None = None,
    ai_episode_images: bool = False,
    hf_token: str | None = None,
    skip_download: bool = False,
    skip_tts: bool = False,
    skip_pack_zip: bool = False,
    lang: str = "fr",
    tts_engine: str = "gtts",
    tts_style_prompt: str | None = None,
    chapter_image_text: bool = False,
    chapter_image_font: str = "dejavu-sans-bold",
    chapter_image_font_size: int = 46,
    chapter_image_template: str = "Chapitre {n}",
    episode_ids: list[str] | None = None,
    chaptering: bool = False,
    chapter_minutes: int = 15,
    progress: ProgressFn = None,
) -> dict:
    output_base = output_base or WORK_DIR
    fetch_limit = None if episode_ids else max_episodes
    feed = fetch_feed(rss_url, min_duration=min_duration, max_episodes=fetch_limit)
    if episode_ids:
        feed = filter_episodes(feed, episode_ids)

    story_name = sanitize_filename(feed.title)
    story_dir = output_base / story_name
    story_dir.mkdir(parents=True, exist_ok=True)
    menu_dir = story_dir / sanitize_filename(menu_name)

    _log(progress, f"Podcast : {feed.title} ({len(feed.episodes)} épisode(s))")

    if not skip_download:
        download_episodes(feed, story_dir, menu_name=menu_name, progress=progress)

    if chaptering and menu_dir.is_dir():
        tracks = [
            (ep.title, menu_dir / f"{ep.index:02d} - {ep.safe_name}.mp3")
            for ep in feed.episodes
            if (menu_dir / f"{ep.index:02d} - {ep.safe_name}.mp3").exists()
        ]
        chaptered = apply_chaptering(tracks, enabled=True, duration_min=chapter_minutes, progress=progress)
        if len(chaptered) != len(tracks):
            feed = install_tracks(menu_dir, chaptered, progress=progress)

    return finalize_story_pack(
        feed, story_dir,
        menu_name=menu_name,
        pack_title=pack_title,
        ai_thumbnail_prompt=ai_thumbnail_prompt,
        ai_episode_images=ai_episode_images,
        hf_token=hf_token,
        skip_tts=skip_tts,
        skip_pack_zip=skip_pack_zip,
        lang=lang,
        tts_engine=tts_engine,
        tts_style_prompt=tts_style_prompt,
        chapter_image_text=chapter_image_text,
        chapter_image_font=chapter_image_font,
        chapter_image_font_size=chapter_image_font_size,
        chapter_image_template=chapter_image_template,
        output_base=output_base,
        progress=progress,
    )


def build_story_from_tracks(
    title: str,
    tracks: list[tuple[str, Path]],
    *,
    output_base: Path | None = None,
    menu_name: str = "Chapitres",
    description: str = "",
    image_url: str | None = None,
    pack_title: str | None = None,
    ai_thumbnail_prompt: str | None = None,
    ai_episode_images: bool = False,
    hf_token: str | None = None,
    skip_tts: bool = False,
    skip_pack_zip: bool = False,
    lang: str = "fr",
    tts_engine: str = "gtts",
    tts_style_prompt: str | None = None,
    chapter_image_text: bool = False,
    chapter_image_font: str = "dejavu-sans-bold",
    chapter_image_font_size: int = 46,
    chapter_image_template: str = "Chapitre {n}",
    chaptering: bool = False,
    chapter_minutes: int = 15,
    progress: ProgressFn = None,
) -> dict:
    """Construit un pack depuis une liste de pistes (ZIP, YouTube, littérature audio…)."""
    output_base = output_base or WORK_DIR
    story_dir = output_base / sanitize_filename(title)
    if story_dir.exists():
        shutil.rmtree(story_dir)
    story_dir.mkdir(parents=True, exist_ok=True)
    menu_dir = story_dir / sanitize_filename(menu_name)

    _log(progress, f"{title} — {len(tracks)} piste(s)")
    chaptered = apply_chaptering(tracks, enabled=chaptering, duration_min=chapter_minutes, progress=progress)
    feed = install_tracks(menu_dir, chaptered, progress=progress)
    feed.title = title
    feed.description = description
    feed.image_url = image_url

    return finalize_story_pack(
        feed, story_dir,
        menu_name=menu_name,
        pack_title=pack_title or title,
        ai_thumbnail_prompt=ai_thumbnail_prompt,
        ai_episode_images=ai_episode_images,
        hf_token=hf_token,
        skip_tts=skip_tts,
        skip_pack_zip=skip_pack_zip,
        lang=lang,
        tts_engine=tts_engine,
        tts_style_prompt=tts_style_prompt,
        chapter_image_text=chapter_image_text,
        chapter_image_font=chapter_image_font,
        chapter_image_font_size=chapter_image_font_size,
        chapter_image_template=chapter_image_template,
        output_base=output_base,
        progress=progress,
    )
