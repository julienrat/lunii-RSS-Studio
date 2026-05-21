#!/usr/bin/env python3
"""Interface ligne de commande."""

import argparse
import sys
from pathlib import Path

from .builder import build_story_from_rss
from .config import WORK_DIR
from .sources.pipeline import build_from_litteratureaudio, build_from_youtube, build_from_zip_upload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lunii RSS Studio")
    parser.add_argument("url", nargs="?", help="URL RSS / littérature audio / YouTube, ou fichier .zip")
    parser.add_argument("-t", "--type", choices=("rss", "zip", "la", "youtube"), default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-n", "--max-episodes", type=int, default=10)
    parser.add_argument("--chaptering", action="store_true")
    parser.add_argument("--chapter-minutes", type=int, default=15)
    parser.add_argument("--skip-tts", action="store_true")
    parser.add_argument("--skip-zip", action="store_true")
    args = parser.parse_args(argv)

    url = (args.url or "").strip()
    if not url:
        parser.error("URL ou chemin .zip requis")

    output = Path(args.output) if args.output else WORK_DIR
    stype = args.type
    if not stype:
        if url.lower().endswith(".zip"):
            stype = "zip"
        elif "litteratureaudio.com" in url:
            stype = "la"
        elif "youtube.com" in url or "youtu.be" in url:
            stype = "youtube"
        else:
            stype = "rss"

    opts = {
        "skip_tts": args.skip_tts,
        "skip_pack_zip": args.skip_zip,
        "chaptering": args.chaptering,
        "chapter_minutes": args.chapter_minutes,
    }

    def progress(msg: str) -> None:
        print(msg)

    try:
        if stype == "zip":
            result = build_from_zip_upload(Path(url), output_base=output, progress=progress, **opts)
        elif stype == "la":
            result = build_from_litteratureaudio(url, output_base=output, progress=progress, **opts)
        elif stype == "youtube":
            result = build_from_youtube(url, output_base=output, progress=progress, **opts)
        else:
            result = build_story_from_rss(
                url, output_base=output, max_episodes=args.max_episodes, progress=progress, **opts,
            )
        print("\n✅ Terminé")
        print(f"   Dossier : {result['story_dir']}")
        if result.get("zip_path"):
            print(f"   Zip : {result['zip_path']}")
        return 0
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
