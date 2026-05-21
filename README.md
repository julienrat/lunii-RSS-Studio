# Lunii RSS Studio

Convertit **plusieurs sources audio** en **pack d'histoires Lunii** (format Studio) :

| Source | Description |
|--------|-------------|
| **Podcast RSS** | Flux RSS classique |
| **ZIP** | Archive de MP3 (livre audio déjà découpé) |
| **Littérature audio** | [litteratureaudio.com](https://www.litteratureaudio.com) — télécharge le ZIP du livre |
| **YouTube** | Vidéo → MP3 via `yt-dlp` |

Fonctionnalités communes :

- Téléchargement des épisodes et images depuis le RSS
- Redimensionnement des images en **320×240** (PNG/JPEG)
- Conversion audio **MP3 mono 44100 Hz**
- **Titres TTS** (gTTS + 300 ms de silence au début, comme sur votre script bash)
- **Images IA** optionnelles via Hugging Face (FLUX.1-schnell)
- Génération du **zip Studio** via [studio-pack-generator](https://github.com/jersou/studio-pack-generator)

## Prérequis système

```bash
sudo apt update && sudo apt install -y ffmpeg unzip
pip install -r requirements.txt   # inclut yt-dlp récent (obligatoire pour YouTube)
# Deno pour yt-dlp + YouTube (si pas déjà fait) :
curl -fsSL https://deno.land/install.sh | sh
bash scripts/install_studio_pack_generator.sh
```

**YouTube** : le `yt-dlp` du système (apt, souvent 2024) est **trop vieux**. Le projet utilise celui du **venv** (`.venv/bin/yt-dlp`) avec **Deno** et `--remote-components ejs:github`.

**Chapitrage** : découpe les pistes plus longues que N minutes en plusieurs morceaux (reprise à un chapitre sur la Lunii).

Optionnel pour le zip final — **recommandé : binaire** (Deno/JSR peut échouer avec une erreur `zip-js/data-uri`) :

```bash
bash scripts/install_studio_pack_generator.sh
```

Le binaire est placé dans `bin/` et détecté automatiquement.

Alternative : **Deno** (runtime séparé — **pas** dans le venv Python, souvent instable pour le zip) :

```bash
curl -fsSL https://deno.land/install.sh | sh
echo 'export DENO_INSTALL="$HOME/.deno"' >> ~/.bashrc
echo 'export PATH="$DENO_INSTALL/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
deno --version
```

Lunii RSS Studio détecte aussi Deno dans `~/.deno/bin/deno` sans modifier le PATH.

## Installation Python

```bash
cd ~/Developpement/lunii-rss-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditez .env : HF_TOKEN pour l'IA image
```

## Configuration (.env)

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | Token Hugging Face (images IA) |
| `IMAGE_MODEL` | URL modèle HF (défaut FLUX.1-schnell) |
| `TTS_LANG` | Langue gTTS (`fr`, `en`, …) |
| `WEB_PORT` | Port interface web (défaut 5556) |

## Interface web (navigateur)

```bash
source .venv/bin/activate
python app.py
```

Ouvrez **http://localhost:5556** — collez l'URL RSS, prévisualisez, puis générez le pack.

## Ligne de commande

```bash
# Podcast RSS
python -m lunii_rss_studio "https://example.com/podcast.xml" --chaptering --chapter-minutes 15

# ZIP local
python -m lunii_rss_studio ./mon-livre.zip -t zip

# Littérature audio
python -m lunii_rss_studio "https://www.litteratureaudio.com/livre-audio-gratuit-mp3/…" -t la

# YouTube
python -m lunii_rss_studio "https://www.youtube.com/watch?v=…" -t youtube --chaptering
```

Options utiles : `--skip-tts`, `--skip-zip`, `--ai-episodes`, `-o ./output`

## Format Lunii / Studio

Conforme aux specs Lunii :

| Média | Format |
|-------|--------|
| Images | PNG/JPEG/BMP, **320×240** |
| Audio | MP3 **44100 Hz**, mono |

Structure générée (compatible studio-pack-generator) :

```
📂 Nom du podcast/
├── 🎵 0-item.mp3          ← titre vocal du pack (TTS)
├── 🔳 0-item.png          ← vignette 320×240
├── metadata.json
└── 📂 Épisodes/
    ├── 🎵 01 - Episode.item.mp3
    ├── 🔳 01 - Episode.item.png
    └── 🎵 01 - Episode.mp3
```

Le zip produit s'importe dans [Studio](https://github.com/marian-m12l/studio) puis sur la Lunii.

## Exemple RSS (Radio France)

```bash
python -m lunii_rss_studio.cli "http://radiofrance-podcast.net/podcast09/rss_19721.xml" -n 3
```

## Licence

MIT — utilise studio-pack-generator (MIT) pour l'empaquetage final.
