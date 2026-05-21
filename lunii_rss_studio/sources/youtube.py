"""Téléchargement audio depuis YouTube (yt-dlp + Deno)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from ..rss import FeedInfo, Episode, sanitize_filename

ProgressFn = Callable[[str], None] | None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VENV_YT_DLP = _PROJECT_ROOT / ".venv" / "bin" / "yt-dlp"
_JS_RUNTIME_CACHED: list[str] | None = None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _find_deno() -> str | None:
    explicit = os.getenv("DENO_PATH", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    found = shutil.which("deno")
    if found:
        return found
    home = Path.home() / ".deno" / "bin" / "deno"
    if home.is_file():
        return str(home)
    return None


def _yt_dlp() -> str:
    explicit = os.getenv("YT_DLP_PATH", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    if _VENV_YT_DLP.is_file():
        return str(_VENV_YT_DLP)
    for cmd in ("yt-dlp", "youtube-dl"):
        if shutil.which(cmd):
            return cmd
    raise RuntimeError(
        "yt-dlp introuvable — pip install -U yt-dlp dans le venv du projet"
    )


def _youtube_extra_args(progress: ProgressFn = None) -> list[str]:
    global _JS_RUNTIME_CACHED
    if _JS_RUNTIME_CACHED is not None:
        return list(_JS_RUNTIME_CACHED)

    extra: list[str] = []
    try:
        help_out = subprocess.run(
            [_yt_dlp(), "--help"], capture_output=True, text=True, timeout=15,
        ).stdout or ""
    except (subprocess.SubprocessError, OSError):
        help_out = ""

    if "--js-runtimes" not in help_out:
        _log(progress, "⚠ yt-dlp ancien — pip install -U yt-dlp")
        _JS_RUNTIME_CACHED = extra
        return extra

    deno = _find_deno()
    if deno:
        extra.extend(["--js-runtimes", f"deno:{deno}"])
        _log(progress, f"yt-dlp utilise Deno : {deno}")
    else:
        raise RuntimeError(
            "YouTube nécessite Deno : curl -fsSL https://deno.land/install.sh | sh"
        )
    extra.extend(["--remote-components", "ejs:github"])
    _JS_RUNTIME_CACHED = extra
    return extra


def _sanitize_out_template(title: str) -> str:
    """Titre sûr pour le chemin de sortie yt-dlp (%(title)s)."""
    safe = sanitize_filename(title)[:120] or "youtube"
    safe = re.sub(r"[%]", "", safe)
    return safe


def _run_yt_dlp_streaming(
    args: list[str],
    progress: ProgressFn = None,
    *,
    youtube: bool = False,
    label: str = "yt-dlp",
) -> None:
    base = _youtube_extra_args(progress) if youtube else []
    cmd = [_yt_dlp(), *base, *args]
    _log(progress, f"{label} : {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        if any(
            k in line.lower()
            for k in ("download", "extract", "merger", "destination", "error", "warning", "%")
        ):
            _log(progress, line[:200])
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"yt-dlp a échoué (code {code})")


def fetch_video(url: str, progress: ProgressFn = None) -> tuple[FeedInfo, Path, Path]:
    """Télécharge l'audio : yt-dlp -x --audio-format mp3 (comme script bash utilisateur)."""
    work = Path(tempfile.mkdtemp(prefix="yt_"))
    _log(progress, f"YouTube : {url}")

    _log(progress, "Lecture des métadonnées…")
    meta_proc = subprocess.run(
        [_yt_dlp(), *_youtube_extra_args(progress), "-J", "--no-playlist", url],
        capture_output=True,
        text=True,
    )
    if meta_proc.returncode != 0:
        err = (meta_proc.stderr or meta_proc.stdout or "")[-2000:]
        raise RuntimeError(f"yt-dlp métadonnées :\n{err}")
    meta = json.loads(meta_proc.stdout)

    title = meta.get("title") or "youtube"
    thumb = meta.get("thumbnail")
    out_name = _sanitize_out_template(title)
    out_tpl = str(work / f"{out_name}.%(ext)s")

    _log(progress, f"Téléchargement audio : {out_name}.mp3 …")
    _run_yt_dlp_streaming(
        ["--no-playlist", "-x", "--audio-format", "mp3", "-o", out_tpl, url],
        progress=progress,
        youtube=True,
        label="Téléchargement",
    )

    mp3s = sorted(work.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp3s:
        raise ValueError("Aucun MP3 produit — vérifiez ffmpeg et la disponibilité de la vidéo")

    mp3 = mp3s[0]
    _log(progress, f"✓ Audio : {mp3.name} ({mp3.stat().st_size // 1024} Ko)")

    safe_title = sanitize_filename(title)
    feed = FeedInfo(title=safe_title, description="YouTube", image_url=thumb)
    feed.episodes.append(
        Episode(
            title=safe_title,
            audio_url=str(mp3),
            image_url=thumb,
            duration_sec=int(meta.get("duration") or 0),
            index=1,
            safe_name=safe_title,
            entry_id=f"yt:{meta.get('id', mp3.stem)}",
        )
    )
    return feed, mp3, work


def preview_video(url: str) -> dict:
    r = subprocess.run(
        [_yt_dlp(), *_youtube_extra_args(), "-J", "--no-playlist", url],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[-1500:])
    meta = json.loads(r.stdout)
    title = meta.get("title", "YouTube")
    dur = int(meta.get("duration") or 0)
    thumb = meta.get("thumbnail")
    return {
        "title": title,
        "description": (meta.get("description") or "")[:300],
        "image_url": thumb,
        "episodes": [{
            "id": meta.get("id", "yt"),
            "title": title,
            "duration_sec": dur,
            "has_image": bool(thumb),
        }],
        "total": 1,
    }
