#!/usr/bin/env bash
# yt-dlp récent + support YouTube (nécessite Deno)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -U "yt-dlp>=2025.11.12"
if ! command -v deno &>/dev/null && [[ ! -x "$HOME/.deno/bin/deno" ]]; then
  echo "Installation de Deno…"
  curl -fsSL https://deno.land/install.sh | sh
fi
DENO="${DENO_PATH:-$HOME/.deno/bin/deno}"
echo "yt-dlp : $(.venv/bin/yt-dlp --version)"
echo "Test JS runtime…"
.venv/bin/yt-dlp --js-runtimes "deno:$DENO" --remote-components ejs:github -J --no-playlist \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw" | head -c 200
echo ""
echo "OK"
