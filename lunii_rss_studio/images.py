"""Traitement et génération d'images pour Lunii (320×240)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import requests
from PIL import Image, ImageDraw, ImageFont

from .config import HF_TOKEN, IMAGE_MODEL, LUNII_IMAGE_SIZE

ProgressFn = Callable[[str], None] | None

FONT_CHOICES = {
    "dejavu-sans-bold": {
        "label": "DejaVu Sans gras",
        "path": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    },
    "dejavu-serif-bold": {
        "label": "DejaVu Serif gras",
        "path": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    },
    "dejavu-mono-bold": {
        "label": "DejaVu Mono gras",
        "path": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    },
    "liberation-sans-bold": {
        "label": "Liberation Sans gras",
        "path": "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    },
}
_CHAPTER_RE = re.compile(r"\bchapitre\s+(\d+)\b", re.I)


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


def chapter_number_from_title(title: str) -> str | None:
    match = _CHAPTER_RE.search(title)
    return match.group(1) if match else None


def _font(font_key: str, size: int):
    choice = FONT_CHOICES.get(font_key) or FONT_CHOICES["dejavu-sans-bold"]
    path = Path(choice["path"])
    try:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    except OSError:
        pass
    return ImageFont.load_default()


def render_chapter_image_text(
    image_path: Path,
    text: str,
    *,
    font_key: str = "dejavu-sans-bold",
    font_size: int = 46,
) -> Path:
    """Ajoute un libellé de chapitre centré sur une image Lunii."""
    resize_for_lunii(image_path, image_path)
    font_size = max(12, min(int(font_size), 96))

    with Image.open(image_path) as img:
        img = img.convert("RGB").resize(LUNII_IMAGE_SIZE, Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", LUNII_IMAGE_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = _font(font_key, font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x = 18
        pad_y = 10
        rect_w = min(LUNII_IMAGE_SIZE[0] - 24, text_w + pad_x * 2)
        rect_h = text_h + pad_y * 2
        x = (LUNII_IMAGE_SIZE[0] - rect_w) // 2
        y = LUNII_IMAGE_SIZE[1] - rect_h - 22

        draw.rounded_rectangle(
            (x, y, x + rect_w, y + rect_h),
            radius=8,
            fill=(0, 0, 0, 165),
        )
        draw.text(
            ((LUNII_IMAGE_SIZE[0] - text_w) // 2, y + pad_y - bbox[1]),
            text,
            fill=(255, 255, 255, 255),
            font=font,
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        img.save(image_path, "PNG")
    return image_path


def render_chapter_image_preview(
    output_path: Path,
    *,
    text: str = "Chapitre 1",
    font_key: str = "dejavu-sans-bold",
    font_size: int = 46,
) -> Path:
    """Crée une image de prévisualisation du libellé de chapitre."""
    output_path = output_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", LUNII_IMAGE_SIZE, color=(48, 76, 118))
    draw = ImageDraw.Draw(img)
    for y in range(LUNII_IMAGE_SIZE[1]):
        color = (48 + y // 8, 76 + y // 12, 118 + y // 20)
        draw.line((0, y, LUNII_IMAGE_SIZE[0], y), fill=color)
    img.save(output_path, "PNG")
    return render_chapter_image_text(output_path, text, font_key=font_key, font_size=font_size)


def apply_chapter_image_texts(
    menu_dir: Path,
    feed,
    *,
    enabled: bool = False,
    font_key: str = "dejavu-sans-bold",
    font_size: int = 46,
    template: str = "Chapitre {n}",
    progress: ProgressFn = None,
) -> None:
    """Ajoute 'Chapitre X' sur les images des pistes chapitrées."""
    if not enabled:
        return

    for ep in feed.episodes:
        chapter = chapter_number_from_title(ep.title)
        if not chapter:
            continue
        item_png = menu_dir / f"{ep.index:02d} - {ep.safe_name}.item.png"
        if not item_png.exists():
            continue
        text = (template or "Chapitre {n}").replace("{n}", chapter).replace("X", chapter)
        render_chapter_image_text(item_png, text, font_key=font_key, font_size=font_size)
        _log(progress, f"Texte chapitre : {item_png.name}")


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
