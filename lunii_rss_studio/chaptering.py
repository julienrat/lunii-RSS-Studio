"""Découpe des MP3 longs en chapitres pour la navigation Lunii."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _audio_duration_sec(path: Path) -> float:
    if not shutil.which("ffprobe"):
        return 0.0
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def split_mp3_by_duration(
    src: Path,
    dest_dir: Path,
    *,
    segment_sec: int,
    base_title: str,
    progress: ProgressFn = None,
) -> list[tuple[str, Path]]:
    """Découpe un MP3 en segments de durée fixe (ffmpeg segment)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg requis pour le chapitrage")

    dest_dir.mkdir(parents=True, exist_ok=True)
    pattern = dest_dir / "seg_%03d.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-f", "segment", "-segment_time", str(segment_sec),
            "-reset_timestamps", "1",
            "-ar", "44100", "-ac", "1", "-b:a", "128k",
            str(pattern),
        ],
        check=True,
        capture_output=True,
    )

    parts: list[tuple[str, Path]] = []
    for i, p in enumerate(sorted(dest_dir.glob("seg_*.mp3")), start=1):
        title = f"{base_title}, chapitre {i}"
        final = dest_dir / f"{i:02d}.mp3"
        p.rename(final)
        parts.append((title, final))
    _log(progress, f"Chapitré : {src.name} → {len(parts)} partie(s)")
    return parts


def apply_chaptering(
    tracks: list[tuple[str, Path]],
    *,
    enabled: bool,
    duration_min: int = 15,
    progress: ProgressFn = None,
) -> list[tuple[str, Path]]:
    """
    Si activé, découpe les fichiers plus longs que duration_min minutes.
    tracks: liste (titre, chemin mp3)
    """
    if not enabled or duration_min <= 0:
        return tracks

    segment_sec = duration_min * 60
    out: list[tuple[str, Path]] = []
    work = Path(tracks[0][1]).parent / "_chapitres_tmp"

    for title, path in tracks:
        dur = _audio_duration_sec(path)
        if dur <= segment_sec * 1.05:
            out.append((title, path))
            continue

        _log(progress, f"Chapitrage ({duration_min} min) : {path.name}")
        subdir = work / re.sub(r'[<>:"/\\|?*]', "", path.stem)[:40]
        if subdir.exists():
            shutil.rmtree(subdir)
        parts = split_mp3_by_duration(
            path, subdir, segment_sec=segment_sec, base_title=title, progress=progress,
        )
        out.extend(parts)
        path.unlink(missing_ok=True)

    return out if out else tracks
