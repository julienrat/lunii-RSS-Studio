"""Téléchargement depuis litteratureaudio.com."""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import requests

from ..rss import FeedInfo, sanitize_filename
from .zip_source import extract_zip_mp3s

ProgressFn = Callable[[str], None] | None

BASE = "https://www.litteratureaudio.com"


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _parse_page(html: str, page_url: str) -> tuple[str, str | None, str | None]:
    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    title = title_m.group(1).split("|")[0].strip() if title_m else "Livre audio"
    title = re.sub(r"\s+", " ", title)

    download_url = None
    for m in re.finditer(r'href="([^"]+\?download=[a-f0-9]+)"', html, re.I):
        download_url = urljoin(page_url, m.group(1))
        break

    image_url = None
    og = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
    if og:
        image_url = og.group(1)

    return title, download_url, image_url


def fetch_book(page_url: str, progress: ProgressFn = None) -> tuple[FeedInfo, Path]:
    """
    Télécharge le ZIP du livre et retourne FeedInfo + dossier d'extraction temporaire.
    L'appelant doit nettoyer extract_dir si besoin.
    """
    _log(progress, f"Littérature audio : {page_url}")
    r = requests.get(page_url, timeout=60, headers={"User-Agent": "LuniiRSSStudio/1.0"})
    r.raise_for_status()

    title, download_url, image_url = _parse_page(r.text, page_url)
    if not download_url:
        raise ValueError("Lien de téléchargement ZIP introuvable sur cette page")

    _log(progress, "Téléchargement du ZIP…")
    zr = requests.get(download_url, timeout=300, headers={"User-Agent": "LuniiRSSStudio/1.0"})
    zr.raise_for_status()

    tmp = Path(tempfile.mkdtemp(prefix="la_"))
    zip_path = tmp / "book.zip"
    zip_path.write_bytes(zr.content)

    extract_to = tmp / "extracted"
    feed = extract_zip_mp3s(zip_path, extract_to, title=title, progress=progress)
    feed.image_url = image_url
    feed.description = f"Livre audio — litteratureaudio.com"
    return feed, extract_to


def preview_book(page_url: str) -> dict:
    """Aperçu sans télécharger le ZIP complet (titres depuis la page si possible)."""
    r = requests.get(page_url, timeout=30, headers={"User-Agent": "LuniiRSSStudio/1.0"})
    r.raise_for_status()
    title, download_url, image_url = _parse_page(r.text, page_url)
    return {
        "title": title,
        "description": "Téléchargement ZIP au moment de la génération",
        "image_url": image_url,
        "has_zip": bool(download_url),
        "episodes": [{"id": "all", "title": "Tout le livre (ZIP)", "duration_sec": 0, "has_image": bool(image_url)}],
        "total": 1,
    }
