"""Appel à studio-pack-generator."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .config import STUDIO_PACK_GENERATOR

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BUNDLED_SPG = _PROJECT_ROOT / "bin" / "studio-pack-generator-x86_64-linux"

ProgressFn = Callable[[str], None] | None


def _log(fn: ProgressFn, msg: str) -> None:
    if fn:
        fn(msg)


def _find_deno() -> str | None:
    found = shutil.which("deno")
    if found:
        return found
    home_deno = Path.home() / ".deno" / "bin" / "deno"
    if home_deno.is_file():
        return str(home_deno)
    return None


def find_studio_pack_generator() -> list[str] | None:
    if STUDIO_PACK_GENERATOR:
        p = Path(STUDIO_PACK_GENERATOR)
        if p.is_file():
            return [str(p)]
    if _BUNDLED_SPG.is_file():
        return [str(_BUNDLED_SPG)]
    for name in ("studio-pack-generator", "studio-pack-generator-x86_64-linux"):
        found = shutil.which(name)
        if found:
            return [found]
    deno = _find_deno()
    if deno:
        return [deno, "-A", "jsr:@jersou/studio-pack-generator"]
    return None


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def run_studio_pack_generator(
    story_path: Path,
    output_folder: Path | None = None,
    lang: str = "fr",
    progress: ProgressFn = None,
) -> Path | None:
    cmd_base = find_studio_pack_generator()
    if not cmd_base:
        _log(progress, "studio-pack-generator non trouvé — dossier prêt, zip non généré")
        _log(progress, f"Installez : bash {_PROJECT_ROOT / 'scripts' / 'install_studio_pack_generator.sh'}")
        return None

    cmd = [
        *cmd_base, "-l", lang, "-v", "-j", "-a", "-i", "-m",
        "--rss-use-image-as-thumbnail",
    ]
    if output_folder:
        cmd.extend(["-o", str(output_folder)])
    cmd.append(str(story_path))

    _log(progress, f"Pack Studio : {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = _strip_ansi(result.stderr or result.stdout or "")
        hint = ""
        if "data-uri" in err or "zip-js" in err:
            hint = (
                "\n\n→ Installez le binaire : "
                f"bash {_PROJECT_ROOT / 'scripts' / 'install_studio_pack_generator.sh'}"
            )
        raise RuntimeError(f"studio-pack-generator a échoué :\n{err[-2000:]}{hint}")

    _log(progress, result.stdout or "Pack généré.")
    zips = sorted(
        (output_folder or story_path.parent).glob("*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return zips[0] if zips else None
