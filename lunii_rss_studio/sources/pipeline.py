"""Orchestration des sources non-RSS."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

from ..builder import build_story_from_tracks
from ..chaptering import apply_chaptering
from ..rss import sanitize_filename
from .litteratureaudio import fetch_book
from .youtube import fetch_video
from .zip_source import extract_zip_mp3s

ProgressFn = Callable[[str], None] | None


def _tracks_from_extract_dir(extract_dir: Path) -> list[tuple[str, Path]]:
    mp3s = sorted(extract_dir.rglob("*.mp3"), key=lambda p: str(p).lower())
    return [(p.stem, p) for p in mp3s if p.stem.lower() != "0-item"]


def build_from_zip_upload(
    zip_path: Path,
    *,
    title: str | None = None,
    output_base: Path | None = None,
    chaptering: bool = False,
    chapter_minutes: int = 15,
    progress: ProgressFn = None,
    **pack_opts,
) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="zip_up_"))
    try:
        extract_to = tmp / "ex"
        feed = extract_zip_mp3s(zip_path, extract_to, title=title, progress=progress)
        tracks = _tracks_from_extract_dir(extract_to)
        return build_story_from_tracks(
            feed.title,
            tracks,
            output_base=output_base,
            description=feed.description,
            image_url=feed.image_url,
            chaptering=chaptering,
            chapter_minutes=chapter_minutes,
            progress=progress,
            **pack_opts,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_from_litteratureaudio(
    page_url: str,
    *,
    output_base: Path | None = None,
    chaptering: bool = False,
    chapter_minutes: int = 15,
    progress: ProgressFn = None,
    **pack_opts,
) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="la_"))
    try:
        feed, extract_dir = fetch_book(page_url, progress=progress)
        tracks = _tracks_from_extract_dir(extract_dir)
        return build_story_from_tracks(
            feed.title,
            tracks,
            output_base=output_base,
            description=feed.description,
            image_url=feed.image_url,
            menu_name="Chapitres",
            chaptering=chaptering,
            chapter_minutes=chapter_minutes,
            progress=progress,
            **pack_opts,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_from_youtube(
    video_url: str,
    *,
    output_base: Path | None = None,
    chaptering: bool = False,
    chapter_minutes: int = 15,
    progress: ProgressFn = None,
    **pack_opts,
) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="yt_"))
    try:
        feed, mp3, work = fetch_video(video_url, progress=progress)
        tracks = [(feed.title, mp3)]
        chaptered = apply_chaptering(tracks, enabled=chaptering, duration_min=chapter_minutes, progress=progress)
        return build_story_from_tracks(
            sanitize_filename(feed.title),
            chaptered,
            output_base=output_base,
            description="YouTube",
            image_url=feed.image_url,
            menu_name="Chapitres",
            chaptering=False,
            progress=progress,
            **pack_opts,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
