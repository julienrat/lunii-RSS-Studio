# Lunii RSS Studio

Lunii RSS Studio transforme des podcasts, des MP3 ou des livres audio en pack compatible avec Studio/Lunii.

L'objectif : ouvrir une page web locale, choisir une source audio, previsualiser les pistes, puis generer un fichier `.zip` importable dans Studio.

## Installation Express

### 1. Recuperer le projet

Ouvrez un terminal dans le dossier ou vous voulez installer l'application, puis placez-vous dans le dossier du projet :

```bash
cd /chemin/vers/lunii-RSS-Studio
```

Si vous venez de telecharger le projet en ZIP, decompressez-le d'abord, puis ouvrez un terminal dans le dossier decompresse.

### 2. Installer les outils systeme

Sur Ubuntu, Debian, Linux Mint ou WSL :

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg curl unzip
```

Ces outils servent a :

- `python3` et `python3-venv` : lancer l'application
- `ffmpeg` : convertir et decouper les MP3
- `curl` et `unzip` : installer le generateur de zip Studio

### 3. Lancer l'application

```bash
bash scripts/start.sh
```

Le script fait tout le necessaire :

- cree l'environnement Python `.venv`
- installe les dependances
- cree le fichier `.env` si besoin
- installe `studio-pack-generator` si possible
- lance l'interface web

Quand le terminal affiche l'adresse, ouvrez :

```text
http://localhost:5556
```

Pour arreter l'application, revenez dans le terminal et appuyez sur `Ctrl+C`.

## Utilisation Rapide

1. Choisissez une source : RSS, ZIP MP3, Litterature audio ou YouTube.
2. Collez l'URL ou choisissez le fichier ZIP.
3. Cliquez sur `Generer l'aperçu`.
4. Selectionnez les pistes a garder.
5. Changez l'ordre avec les boutons haut/bas si besoin.
6. Choisissez les options : chapitrage, TTS, images IA.
7. Cliquez sur `Generer le pack`.
8. Telechargez le `.zip` produit.
9. Importez ce `.zip` dans Studio, puis envoyez-le sur la Lunii.

Les fichiers generes sont places dans le dossier `output/`.

## Sources Disponibles

| Source | Utilisation |
| --- | --- |
| Podcast RSS | Collez l'URL du flux RSS du podcast. |
| ZIP MP3 | Donnez un ZIP contenant des fichiers `.mp3`. |
| Litterature audio | Collez l'URL d'une page `litteratureaudio.com`. |
| YouTube | Collez l'URL d'une video YouTube. |

## Options Importantes

### Selection et ordre des pistes

Apres l'aperçu, vous pouvez cocher/decocher les pistes et les deplacer. L'ordre affiche est l'ordre utilise pour generer le pack.

Si les episodes sont numerotes dans le flux RSS, l'application essaie automatiquement de commencer par le premier.

### Chapitrage

Le chapitrage decoupe les fichiers longs en parties plus courtes.

Exemple : si une piste s'appelle `Mon histoire`, les chapitres auront des annonces TTS comme :

```text
Mon histoire, chapitre 1
Mon histoire, chapitre 2
Mon histoire, chapitre 3
```

Vous pouvez aussi ajouter automatiquement un texte sur l'image de chaque chapitre, par exemple `Chapitre 1`, `Chapitre 2`, etc. L'interface permet de choisir la police, la taille du texte et de previsualiser le rendu avant generation.

### TTS

Le TTS sert a generer les petits fichiers audio de menu lus par la Lunii.

Dans l'interface, vous pouvez choisir :

- `gTTS` : simple, rapide, sans token Hugging Face
- `Chatterbox TTS French`
- `French Tortoise`

Le bouton `Previsualiser la voix` permet d'ecouter une phrase de test avant de generer le pack.

Les modeles Hugging Face demandent un token Hugging Face.
Le modele Parler-TTS français `PHBJT/french_parler_tts_mini_v0.1` existe, mais il est propose via un Space Hugging Face et ne repond pas correctement avec l'API serverless utilisee par l'application. Il n'est donc pas affiche dans la liste active.

### Token Hugging Face

Le token Hugging Face est utile pour :

- generer une vignette IA
- generer des images IA par piste
- tester ou utiliser les modeles TTS Hugging Face

Vous pouvez le coller directement dans l'interface. Il est enregistre dans le `localStorage` du navigateur, donc vous n'avez pas besoin de le retaper a chaque lancement.

Vous pouvez aussi le mettre dans `.env` :

```env
HF_TOKEN=hf_votre_token
```

## Configuration

Le fichier `.env` est cree automatiquement au premier lancement.

Variables utiles :

| Variable | Valeur par defaut | Description |
| --- | --- | --- |
| `HF_TOKEN` | vide | Token Hugging Face optionnel. |
| `IMAGE_MODEL` | FLUX.1-schnell | Modele Hugging Face pour les images IA. |
| `TTS_LANG` | `fr` | Langue de gTTS. |
| `WEB_PORT` | `5556` | Port de l'interface web. |
| `WORK_DIR` | `output` | Dossier des fichiers generes. |
| `MAX_UPLOAD_MB` | `0` | Limite d'upload ZIP. `0` signifie sans limite Flask. |
| `STUDIO_PACK_GENERATOR` | vide | Chemin manuel vers `studio-pack-generator` si besoin. |

Pour changer le port :

```env
WEB_PORT=8080
```

Puis relancez :

```bash
bash scripts/start.sh
```

## Relancer Plus Tard

Une fois l'installation faite, il suffit de relancer :

```bash
bash scripts/start.sh
```

Le script reutilise `.venv` et `.env` existants.

## Mise A Jour

Si vous avez recupere le projet avec Git :

```bash
git pull
bash scripts/start.sh
```

Sinon, telechargez la nouvelle version du projet et relancez `bash scripts/start.sh`.

## Depannage

### `python3: command not found`

Installez Python :

```bash
sudo apt install python3 python3-venv
```

### Erreur avec `ffmpeg`

Installez ffmpeg :

```bash
sudo apt install ffmpeg
```

### Le zip Studio n'est pas genere

Relancez l'installation du generateur :

```bash
bash scripts/install_studio_pack_generator.sh
```

Si cela echoue, verifiez que `curl` et `unzip` sont installes :

```bash
sudo apt install curl unzip
```

### Le port 5556 est deja utilise

Changez le port dans `.env` :

```env
WEB_PORT=5557
```

Puis relancez :

```bash
bash scripts/start.sh
```

### YouTube ne fonctionne pas

Le projet installe un `yt-dlp` recent dans `.venv`.

Si YouTube demande Deno, installez-le :

```bash
curl -fsSL https://deno.land/install.sh | sh
```

Puis fermez et rouvrez le terminal, ou relancez :

```bash
source ~/.bashrc
bash scripts/start.sh
```

### Un modele Hugging Face ne repond pas

Certains modeles peuvent etre lents, indisponibles ou non compatibles avec l'inference distante Hugging Face. Dans ce cas :

- testez d'abord avec `gTTS`
- verifiez votre token Hugging Face
- essayez un autre modele TTS dans la liste
- relancez la previsualisation apres quelques minutes

## Utilisation En Ligne De Commande

L'interface web est recommandee. La ligne de commande reste disponible pour les usages avances.

```bash
source .venv/bin/activate

# Podcast RSS
python -m lunii_rss_studio "https://example.com/podcast.xml" --chaptering --chapter-minutes 15

# ZIP local
python -m lunii_rss_studio ./mon-livre.zip -t zip

# Litterature audio
python -m lunii_rss_studio "https://www.litteratureaudio.com/livre-audio-gratuit-mp3/..." -t la

# YouTube
python -m lunii_rss_studio "https://www.youtube.com/watch?v=..." -t youtube --chaptering
```

Options utiles :

```bash
--skip-tts
--skip-zip
--chaptering
--chapter-minutes 15
-o ./output
```

## Format Des Fichiers Generes

Les medias sont convertis pour la Lunii :

| Media | Format |
| --- | --- |
| Images | PNG/JPEG/BMP, 320 x 240 |
| Audio | MP3, mono, 44100 Hz |

Structure typique :

```text
Nom du podcast/
├── 0-item.mp3
├── 0-item.png
├── metadata.json
└── Episodes/
    ├── 01 - Episode.item.mp3
    ├── 01 - Episode.item.png
    └── 01 - Episode.mp3
```

Le fichier `.zip` final est celui a importer dans Studio.

## Licence

MIT. Le projet utilise `studio-pack-generator` pour produire le zip compatible Studio.
