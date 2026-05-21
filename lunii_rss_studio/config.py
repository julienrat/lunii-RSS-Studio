import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN", "")
IMAGE_MODEL = os.getenv(
    "IMAGE_MODEL",
    "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
)
TTS_LANG = os.getenv("TTS_LANG", "fr")
WEB_PORT = int(os.getenv("WEB_PORT", "5556"))
STUDIO_PACK_GENERATOR = os.getenv("STUDIO_PACK_GENERATOR", "")

LUNII_IMAGE_SIZE = (320, 240)
AUDIO_MP3_RATE = 44100
TTS_SILENCE_MS = 300

WORK_DIR = Path(os.getenv("WORK_DIR", Path.cwd() / "output"))
WORK_DIR.mkdir(parents=True, exist_ok=True)

# Taille max upload ZIP (Mo). 0 = pas de limite Flask.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "0"))
