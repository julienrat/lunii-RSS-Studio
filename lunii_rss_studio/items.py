"""Fichiers menu Lunii : 0-item (sous-menu) et *.item (par épisode)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

from .config import LUNII_IMAGE_SIZE
from .images import resize_for_lunii
from .rss import FeedInfo, sanitize_filename

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _font(size: int = 16):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def placeholder_image(title: str, dest: Path, progress: ProgressFn = None) -> Path:
    """Image 320×240 avec le titre de l'épisode ou du menu."""
    dest = dest.with_suffix(".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", LUNII_IMAGE_SIZE, color=(60, 90, 140))
    draw = ImageDraw.Draw(img)
    text = title[:40] + ("…" if len(title) > 40 else "")
    draw.text((12, 100), text, fill=(255, 255, 255), font=_font(14))
    img.save(dest, "PNG")
    _log(progress, f"Image placeholder : {dest.name}")
    return dest


def extract_cover_from_mp3(mp3_path: Path, dest_png: Path, progress: ProgressFn = None) -> bool:
    """Extrait la pochette embarquée dans le MP3 (ffmpeg)."""
    if not shutil.which("ffmpeg"):
        return False
    tmp = dest_png.with_suffix(".cover.tmp.jpg")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(mp3_path),
            "-an", "-vcodec", "mjpeg", "-frames:v", "1",
            str(tmp),
        ],
        capture_output=True,
    )
    if result.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 100:
        tmp.unlink(missing_ok=True)
        return False
    resize_for_lunii(tmp, dest_png)
    tmp.unlink(missing_ok=True)
    _log(progress, f"Pochette MP3 → {dest_png.name}")
    return True


def download_episode_image(url: str, dest_png: Path, progress: ProgressFn = None) -> bool:
    """Télécharge une image RSS et la convertit en .item.png."""
    try:
        dest_png.parent.mkdir(parents=True, exist_ok=True)
        ext = Path(urlparse(url).path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"):
            ext = ".jpg"
        tmp = dest_png.with_suffix(f".dl{ext}")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            tmp.write_bytes(r.content)
        resize_for_lunii(tmp, dest_png)
        tmp.unlink(missing_ok=True)
        _log(progress, f"Image épisode : {dest_png.name}")
        return True
    except (requests.RequestException, OSError) as e:
        _log(progress, f"Image RSS ignorée : {e}")
        return False


def ensure_episode_item_images(
    menu_dir: Path,
    feed: FeedInfo,
    story_dir: Path,
    progress: ProgressFn = None,
) -> None:
    """Crée les fichiers *.item.png manquants pour chaque épisode."""
    root_thumb = story_dir / "0-item.png"

    for ep in feed.episodes:
        base = f"{ep.index:02d} - {ep.safe_name}"
        story_mp3 = menu_dir / f"{base}.mp3"
        item_png = menu_dir / f"{base}.item.png"
        if item_png.exists():
            resize_for_lunii(item_png, item_png)
            continue

        if ep.image_url and download_episode_image(ep.image_url, item_png, progress):
            continue
        if story_mp3.exists() and extract_cover_from_mp3(story_mp3, item_png, progress):
            continue
        if root_thumb.exists():
            shutil.copy(root_thumb, item_png)
            resize_for_lunii(item_png, item_png)
            _log(progress, f"Image épisode (vignette pack) : {item_png.name}")
            continue

        title = ep.title
        if " - " in base:
            title = base.split(" - ", 1)[-1]
        placeholder_image(title, item_png, progress)


def ensure_menu_items(
    story_dir: Path,
    menu_name: str,
    menu_label: str | None = None,
    lang: str | None = None,
    tts_engine: str = "gtts",
    hf_token: str | None = None,
    tts_style_prompt: str | None = None,
    progress: ProgressFn = None,
) -> None:
    """
    Crée Épisodes/0-item.mp3 (voix du menu) et Épisodes/0-item.png (image du menu).
    Requis pour entendre/voir le choix d'épisode sur la Lunii.
    """
    from .audio import convert_audio_for_lunii, generate_title_tts

    menu_dir = story_dir / sanitize_filename(menu_name)
    if not menu_dir.is_dir():
        return

    label = menu_label or menu_name
    menu_mp3 = menu_dir / "0-item.mp3"
    if not menu_mp3.exists():
        generate_title_tts(
            label,
            menu_mp3,
            lang=lang,
            tts_engine=tts_engine,
            hf_token=hf_token,
            tts_style_prompt=tts_style_prompt,
            progress=progress,
        )
        convert_audio_for_lunii(menu_mp3, progress=progress)
        _log(progress, f"Audio menu : {menu_mp3.relative_to(story_dir)}")

    menu_png = menu_dir / "0-item.png"
    if menu_png.exists():
        resize_for_lunii(menu_png, menu_png)
        return

    # Première image d'épisode disponible
    for item_png in sorted(menu_dir.glob("*.item.png")):
        shutil.copy(item_png, menu_png)
        resize_for_lunii(menu_png, menu_png)
        _log(progress, f"Image menu (depuis épisode) : {menu_png.name}")
        return

    root_png = story_dir / "0-item.png"
    if root_png.exists():
        shutil.copy(root_png, menu_png)
        resize_for_lunii(menu_png, menu_png)
        _log(progress, f"Image menu (vignette pack) : {menu_png.name}")
        return

    placeholder_image(label, menu_png, progress)
