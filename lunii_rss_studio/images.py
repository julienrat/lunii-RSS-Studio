"""Traitement et génération d'images pour Lunii (320×240)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import requests
from PIL import Image

from .config import HF_TOKEN, IMAGE_MODEL, LUNII_IMAGE_SIZE

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def resize_for_lunii(src: Path, dest: Path | None = None) -> Path:
    """Redimensionne une image en 320×240 (PNG ou JPEG)."""
    dest = dest or src
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        img = img.resize(LUNII_IMAGE_SIZE, Image.Resampling.LANCZOS)
        suffix = dest.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            img.save(dest, "JPEG", quality=90)
        elif suffix == ".bmp":
            img.save(dest, "BMP")
        else:
            if dest.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
                dest = dest.with_suffix(".png")
            img.save(dest, "PNG")
    return dest


def process_story_images(story_dir: Path, progress: ProgressFn = None) -> int:
    """Redimensionne toutes les images d'un dossier histoire."""
    count = 0
    for path in story_dir.rglob("*"):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"):
            continue
        if path.name.endswith(".item.png") or path.name == "0-item.png":
            resize_for_lunii(path, path)
            count += 1
            _log(progress, f"Image redimensionnée : {path.relative_to(story_dir)}")
    return count


def generate_image_hf(
    prompt: str,
    output_path: Path,
    token: str | None = None,
    model_url: str | None = None,
    progress: ProgressFn = None,
) -> Path:
    """Génère une image via l'API Hugging Face (FLUX.1-schnell)."""
    token = token or HF_TOKEN
    model_url = model_url or IMAGE_MODEL
    if not token or token == "TON_TOKEN":
        raise ValueError("HF_TOKEN manquant — configurez-le dans .env")

    _log(progress, f"Génération IA : {prompt[:60]}…")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        model_url,
        headers=headers,
        json={"inputs": prompt},
        timeout=180,
    )
    if response.status_code == 503:
        raise RuntimeError("Modèle HF en chargement — réessayez dans quelques secondes.")
    response.raise_for_status()

    output_path = output_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    resize_for_lunii(output_path, output_path)
    _log(progress, f"Image IA enregistrée : {output_path}")
    return output_path


def ensure_thumbnail(
    story_dir: Path,
    feed_image_url: str | None,
    ai_prompt: str | None,
    download_fn,
    token: str | None = None,
    progress: ProgressFn = None,
) -> Path:
    """Crée 0-item.png (vignette du pack) depuis RSS ou IA."""
    thumb = story_dir / "0-item.png"
    if thumb.exists():
        resize_for_lunii(thumb, thumb)
        return thumb

    if ai_prompt:
        return generate_image_hf(ai_prompt, thumb, token=token, progress=progress)

    if feed_image_url:
        try:
            ext = ".jpg"
            tmp = story_dir / f"_thumb_dl{ext}"
            download_fn(feed_image_url, tmp)
            resize_for_lunii(tmp, thumb)
            tmp.unlink(missing_ok=True)
            return thumb
        except Exception as e:
            _log(progress, f"Vignette RSS échouée : {e}")

    # Image par défaut : fond coloré avec titre
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", LUNII_IMAGE_SIZE, color=(70, 130, 180))
    draw = ImageDraw.Draw(img)
    title = story_dir.name[:30]
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    draw.text((10, 100), title, fill=(255, 255, 255), font=font)
    img.save(thumb, "PNG")
    return thumb
