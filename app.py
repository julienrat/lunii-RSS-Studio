#!/usr/bin/env python3
"""Interface web Lunii RSS Studio."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from lunii_rss_studio.builder import build_story_from_rss
from lunii_rss_studio.config import MAX_UPLOAD_MB, WEB_PORT, WORK_DIR
from lunii_rss_studio.pack_spg import find_studio_pack_generator
from lunii_rss_studio.sources.litteratureaudio import preview_book
from lunii_rss_studio.sources.pipeline import (
    build_from_litteratureaudio,
    build_from_youtube,
    build_from_zip_upload,
)
from lunii_rss_studio.sources.youtube import preview_video

app = Flask(__name__)
if MAX_UPLOAD_MB > 0:
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
else:
    app.config["MAX_CONTENT_LENGTH"] = None  # pas de limite (usage local)


@app.errorhandler(413)
def request_entity_too_large(_e):
    limit = f"{MAX_UPLOAD_MB} Mo" if MAX_UPLOAD_MB > 0 else "limite serveur"
    msg = (
        f"Fichier trop volumineux (max upload : {limit}). "
        "Utilisez « Chemin ZIP sur ce PC » dans l'onglet ZIP, ou la ligne de commande : "
        "python -m lunii_rss_studio /chemin/vers/fichier.zip -t zip"
    )
    if request.path.startswith("/api/"):
        return jsonify({"error": msg}), 413
    return msg, 413

UPLOAD_DIR = WORK_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_jobs: dict[str, dict] = {}
_job_lock = threading.Lock()

# Onglets UI → noms API
_SOURCE_ALIASES = {
    "yt": "youtube",
    "youtube": "youtube",
    "la": "litteratureaudio",
    "litteratureaudio": "litteratureaudio",
    "rss": "rss",
    "zip": "zip",
}


def _normalize_source(raw: str) -> str:
    return _SOURCE_ALIASES.get((raw or "rss").strip().lower(), (raw or "rss").strip().lower())


def _set_job(job_id: str, **kwargs) -> None:
    with _job_lock:
        _jobs.setdefault(job_id, {}).update(kwargs)


def _pack_kwargs(data: dict) -> dict:
    return {
        "pack_title": data.get("pack_title") or None,
        "ai_thumbnail_prompt": data.get("ai_thumbnail_prompt") or None,
        "ai_episode_images": bool(data.get("ai_episodes")),
        "skip_tts": bool(data.get("skip_tts")),
        "skip_pack_zip": bool(data.get("skip_zip")),
        "lang": data.get("lang", "fr"),
        "chaptering": bool(data.get("chaptering")),
        "chapter_minutes": int(data.get("chapter_minutes", 15)),
    }


@app.route("/")
def index():
    spg = find_studio_pack_generator()
    return render_template(
        "index.html",
        work_dir=str(WORK_DIR),
        spg_available=spg is not None,
        spg_cmd=" ".join(spg) if spg else None,
        max_upload_mb=MAX_UPLOAD_MB,
    )


def _run_job(job_id: str, fn) -> None:
    def progress(msg: str) -> None:
        with _job_lock:
            _jobs[job_id]["log"].append(msg)

    try:
        result = fn(progress)
        _set_job(job_id, status="done", result=result)
    except Exception as e:
        _set_job(job_id, status="error", error=str(e))


@app.route("/api/jobs", methods=["POST"])
def start_job():
    import uuid as _uuid

    # Upload ZIP (multipart) ou JSON
    if request.files.get("zip_file"):
        source = "zip"
        f = request.files["zip_file"]
        if not f.filename or not f.filename.lower().endswith(".zip"):
            return jsonify({"error": "Fichier .zip requis"}), 400
        zip_path = UPLOAD_DIR / f"{_uuid.uuid4().hex[:8]}_{secure_filename(f.filename)}"
        f.save(zip_path)
        data = request.form.to_dict()
        data["source"] = "zip"
        data["zip_path"] = str(zip_path)
    elif request.form.get("source") == "zip":
        data = request.form.to_dict()
        data["source"] = "zip"
        local = (data.get("zip_path_local") or "").strip()
        if local:
            data["zip_path_local"] = local
    else:
        data = request.get_json(force=True) or {}

    source = _normalize_source(data.get("source") or "rss")
    output = Path(data.get("output_dir") or WORK_DIR)
    opts = _pack_kwargs(data)

    job_id = str(_uuid.uuid4())[:8]
    _set_job(job_id, status="running", log=[], result=None)

    if source == "rss":
        rss_url = (data.get("rss_url") or "").strip()
        if not rss_url:
            return jsonify({"error": "URL RSS requise"}), 400
        episode_ids = data.get("episode_ids") or None
        if episode_ids is not None and len(episode_ids) == 0:
            return jsonify({"error": "Sélectionnez au moins un épisode"}), 400

        def task(progress):
            return build_story_from_rss(
                rss_url,
                output_base=output,
                max_episodes=int(data.get("max_episodes", 10)) if not episode_ids else None,
                min_duration=int(data.get("min_duration", 0)),
                episode_ids=episode_ids,
                **opts,
                progress=progress,
            )

    elif source == "zip":
        zip_path = (data.get("zip_path_local") or data.get("zip_path") or "").strip()
        if zip_path:
            zp = Path(zip_path).expanduser().resolve()
            if not zp.is_file():
                return jsonify({"error": f"ZIP introuvable : {zp}"}), 400
            zip_path = str(zp)
        elif not zip_path or not Path(zip_path).is_file():
            return jsonify({"error": "Archive ZIP manquante (upload ou chemin local)"}), 400

        def task(progress):
            return build_from_zip_upload(
                Path(zip_path),
                title=data.get("pack_title") or None,
                output_base=output,
                **opts,
                progress=progress,
            )

    elif source == "litteratureaudio":
        url = (data.get("la_url") or "").strip()
        if not url or "litteratureaudio.com" not in url:
            return jsonify({"error": "URL litteratureaudio.com requise"}), 400

        def task(progress):
            return build_from_litteratureaudio(url, output_base=output, **opts, progress=progress)

    elif source == "youtube":
        url = (data.get("youtube_url") or "").strip()
        if not url:
            return jsonify({"error": "URL YouTube requise"}), 400

        def task(progress):
            return build_from_youtube(url, output_base=output, **opts, progress=progress)

    else:
        return jsonify({"error": f"Source inconnue : {source}"}), 400

    threading.Thread(target=_run_job, args=(job_id, task), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>")
def job_status(job_id: str):
    with _job_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job inconnu"}), 404
    return jsonify(job)


@app.route("/api/download")
def download_zip():
    path = request.args.get("path", "")
    p = Path(path).resolve()
    if not p.is_file() or not str(p).startswith(str(WORK_DIR.resolve())):
        return jsonify({"error": "Fichier invalide"}), 400
    return send_file(p, as_attachment=True)


@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json(force=True) or {}
    source = _normalize_source(data.get("source") or "rss")

    try:
        if source == "rss":
            from lunii_rss_studio.rss import fetch_feed

            feed = fetch_feed(
                data.get("rss_url", "").strip(),
                min_duration=int(data.get("min_duration", 0)),
                max_episodes=int(data.get("max_episodes", 30)),
            )
            return jsonify({
                "title": feed.title,
                "description": (feed.description or "")[:300],
                "image_url": feed.image_url,
                "episodes": [
                    {"id": e.entry_id, "title": e.title, "duration_sec": e.duration_sec, "has_image": bool(e.image_url)}
                    for e in feed.episodes
                ],
                "total": len(feed.episodes),
            })
        if source == "litteratureaudio":
            return jsonify(preview_book(data.get("la_url", "").strip()))
        if source == "youtube":
            return jsonify(preview_video(data.get("youtube_url", "").strip()))
        if source == "zip":
            return jsonify({
                "title": data.get("pack_title") or "Archive ZIP",
                "description": "Les pistes seront listées après upload",
                "episodes": [{"id": "all", "title": "Tous les MP3 du ZIP", "duration_sec": 0, "has_image": False}],
                "total": 1,
            })
        return jsonify({"error": "Source inconnue"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Compat ancienne route
@app.route("/api/preview-feed", methods=["POST"])
def preview_feed():
    data = request.get_json(force=True) or {}
    data["source"] = "rss"
    with app.test_request_context(json=data):
        return preview()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
