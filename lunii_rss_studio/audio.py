"""Conversion audio Lunii et TTS des titres (gTTS + silence)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from gtts import gTTS

from .config import AUDIO_MP3_RATE, TTS_LANG, TTS_SILENCE_MS

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def generate_title_tts(
    text: str,
    output_path: Path,
    lang: str | None = None,
    silence_ms: int | None = None,
    progress: ProgressFn = None,
) -> Path:
    """
    Génère un MP3 titre avec gTTS + 300 ms de silence au début (format Lunii).
    Équivalent du script bash fourni par l'utilisateur.
    """
    lang = lang or TTS_LANG
    silence_ms = silence_ms if silence_ms is not None else TTS_SILENCE_MS
    output_path = output_path.with_suffix(".mp3")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _log(progress, f"TTS : {text[:50]}…")

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "vocal_raw.mp3"
        gTTS(text=text, lang=lang).save(str(raw))

        if not _ffmpeg_available():
            shutil.copy(raw, output_path)
            _log(progress, "ffmpeg absent — MP3 brut sans silence")
            return output_path

        silence_sec = silence_ms / 1000.0
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_MP3_RATE}:cl=mono",
                "-i", str(raw),
                "-filter_complex",
                f"[0:a]atrim=end={silence_sec}[s];[s][1:a]concat=n=2:v=0:a=1",
                "-ar", str(AUDIO_MP3_RATE),
                "-ac", "1",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
    _log(progress, f"Vocal généré : {output_path.name}")
    return output_path


def convert_audio_for_lunii(src: Path, dest: Path | None = None, progress: ProgressFn = None) -> Path:
    """Convertit en MP3 mono 44100 Hz (requis Lunii pour MP3/OGG)."""
    dest = dest or src
    if not _ffmpeg_available():
        _log(progress, "ffmpeg absent — conversion audio ignorée")
        return src

    dest = dest.with_suffix(".mp3")
    tmp = dest.with_suffix(".tmp.mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-ar", str(AUDIO_MP3_RATE),
            "-ac", "1",
            "-b:a", "128k",
            str(tmp),
        ],
        check=True,
        capture_output=True,
    )
    tmp.replace(dest)
    _log(progress, f"Audio converti : {dest.name}")
    return dest


def generate_story_titles(
    story_dir: Path,
    pack_title: str | None = None,
    menu_names: list[str] | None = None,
    progress: ProgressFn = None,
) -> None:
    """Génère 0-item.mp3 (racine + sous-menus) et les fichiers *.item.mp3 manquants."""
    if pack_title:
        root_tts = story_dir / "0-item.mp3"
        if not root_tts.exists():
            generate_title_tts(pack_title, root_tts, progress=progress)

    for menu_name in menu_names or []:
        menu_dir = story_dir / menu_name
        if not menu_dir.is_dir():
            continue
        menu_mp3 = menu_dir / "0-item.mp3"
        if not menu_mp3.exists():
            generate_title_tts(menu_name, menu_mp3, progress=progress)
            convert_audio_for_lunii(menu_mp3, progress=progress)
            _log(progress, f"Audio menu : {menu_mp3.relative_to(story_dir)}")

    for mp3 in story_dir.rglob("*.mp3"):
        if mp3.name == "0-item.mp3" or mp3.name.endswith(".item.mp3"):
            continue
        item_mp3 = mp3.with_name(mp3.stem + ".item.mp3")
        if not item_mp3.exists():
            title = mp3.stem
            if " - " in title:
                title = title.split(" - ", 1)[-1]
            generate_title_tts(title, item_mp3, progress=progress)
        convert_audio_for_lunii(item_mp3, progress=progress)

    for mp3 in story_dir.rglob("*.mp3"):
        if not mp3.name.endswith(".item.mp3") and mp3.name != "0-night-mode.mp3":
            convert_audio_for_lunii(mp3, progress=progress)
