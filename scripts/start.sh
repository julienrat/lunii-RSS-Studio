#!/usr/bin/env bash
# Prepare l'environnement Python puis lance l'interface web.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

echo "== Lunii RSS Studio =="

if ! need_cmd python3; then
  echo "Python 3 est introuvable."
  echo "Installez-le puis relancez ce script : sudo apt install python3 python3-venv"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creation de l'environnement Python .venv..."
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo "Installation/mise a jour des dependances Python..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
  else
    touch .env
  fi
  echo "Fichier .env cree. Vous pourrez y ajouter un token Hugging Face plus tard."
fi

PORT="${WEB_PORT:-}"
if [ -z "$PORT" ] && [ -f ".env" ]; then
  PORT="$(grep -E '^WEB_PORT=' .env | tail -n 1 | cut -d= -f2- || true)"
fi
PORT="${PORT:-5556}"

missing_system=()
for cmd in ffmpeg curl unzip; do
  if ! need_cmd "$cmd"; then
    missing_system+=("$cmd")
  fi
done

if [ "${#missing_system[@]}" -gt 0 ]; then
  echo
  echo "Outils systeme manquants : ${missing_system[*]}"
  echo "Sur Ubuntu/Debian, installez-les avec :"
  echo "sudo apt update && sudo apt install -y ffmpeg curl unzip"
  echo
fi

if [ ! -x "bin/studio-pack-generator-x86_64-linux" ]; then
  if need_cmd curl && need_cmd unzip; then
    echo "Installation du generateur de zip Studio..."
    bash scripts/install_studio_pack_generator.sh || true
  else
    echo "Le generateur de zip Studio sera installe quand curl et unzip seront disponibles."
  fi
fi

echo
echo "Interface prete : http://localhost:${PORT}"
echo "Arret : Ctrl+C dans ce terminal"
echo

python app.py
