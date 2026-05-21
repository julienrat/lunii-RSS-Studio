#!/usr/bin/env bash
# Installe le binaire studio-pack-generator (évite le bug Deno/JSR zip-js)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/bin"
VERSION="0.5.14"
ZIP="studio-pack-generator-${VERSION}-x86_64-linux.zip"
URL="https://github.com/jersou/studio-pack-generator/releases/download/v${VERSION}/${ZIP}"

mkdir -p "$BIN"
echo "Téléchargement de $URL ..."
curl -fsSL -o "$BIN/$ZIP" "$URL"
unzip -o -j "$BIN/$ZIP" -d "$BIN"
chmod +x "$BIN/studio-pack-generator-x86_64-linux"
rm -f "$BIN/$ZIP"
echo "OK : $BIN/studio-pack-generator-x86_64-linux"
"$BIN/studio-pack-generator-x86_64-linux" --help | head -3
