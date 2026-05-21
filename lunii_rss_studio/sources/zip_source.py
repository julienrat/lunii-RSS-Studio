"""Import d'archives ZIP contenant des MP3."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Callable

from ..rss import FeedInfo, Episode, sanitize_filename

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def extract_zip_mp3s(
    zip_path: Path,
    extract_to: Path,
    *,
    title: str | None = None,
    progress: ProgressFn = None,
) -> FeedInfo:
    """Extrait les MP3 d'un ZIP et construit un FeedInfo."""
    extract_to.mkdir(parents=True, exist_ok=True)
    _log(progress, f"Extraction : {zip_path.name}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    mp3s = sorted(
        extract_to.rglob("*.mp3"),
        key=lambda p: (len(p.parts), str(p).lower()),
    )
    if not mp3s:
        raise ValueError("Aucun fichier MP3 dans l'archive ZIP")

    book_title = title or sanitize_filename(zip_path.stem)
    feed = FeedInfo(title=book_title, description="", image_url=None)

    for i, mp3 in enumerate(mp3s, start=1):
        stem = mp3.stem
        if stem.lower() in ("0-item",):
            continue
        feed.episodes.append(
            Episode(
                title=stem,
                audio_url="",
                image_url=None,
                duration_sec=0,
                index=i,
                safe_name=sanitize_filename(stem),
                entry_id=f"zip:{mp3.relative_to(extract_to)}",
            )
        )
    _log(progress, f"{len(feed.episodes)} piste(s) MP3 trouvée(s)")
    return feed


def copy_tracks_to_menu(
    zip_extract_dir: Path,
    menu_dir: Path,
    episodes: list[Episode],
    progress: ProgressFn = None,
) -> None:
    """Copie les MP3 extraits vers le dossier menu Studio."""
    import shutil

    menu_dir.mkdir(parents=True, exist_ok=True)
    mp3_by_rel = {str(p.relative_to(zip_extract_dir)): p for p in zip_extract_dir.rglob("*.mp3")}

    for ep in episodes:
        rel = ep.entry_id.removeprefix("zip:")
        src = zip_extract_dir / rel
        if not src.exists():
            # fallback par index
            all_mp3 = sorted(zip_extract_dir.rglob("*.mp3"), key=lambda p: str(p).lower())
            if ep.index <= len(all_mp3):
                src = all_mp3[ep.index - 1]
            else:
                continue
        dest = menu_dir / f"{ep.index:02d} - {ep.safe_name}.mp3"
        shutil.copy2(src, dest)
        _log(progress, f"Copié : {dest.name}")
