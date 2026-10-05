"""Local web app (Flask). Run:  python -m facelessapp serve   then open http://127.0.0.1:5000"""
from __future__ import annotations

import logging
import shutil
from dataclasses import asdict

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

from .config import get_settings
from .jobs import JobManager, library, read_item
from .models import VideoRequest
from .presets import ART_STYLES, CAPTION_STYLES, FORMATS, LANGUAGES, NICHES, VOICES
from .script_writer import suggest_topics
from .tts import get_engines

ALLOWED_FILES = {"video.mp4", "thumbnail.jpg", "captions.srt", "description.txt", "metadata.json", "script.json"}


def _request_from(data: dict) -> VideoRequest:
    def num(key, default, cast=int):
        try:
            return cast(data.get(key) or default)
        except (TypeError, ValueError):
            return default

    return VideoRequest(
        topic=str(data.get("topic", "")).strip(),
        niche=data.get("niche") or "facts",
        format=data.get("format") if data.get("format") in FORMATS else "short",
        duration=num("duration", 0),
        language=data.get("language") or "",
        voice=data.get("voice") or "",
        art_style=data.get("art_style") or "",
        caption_style=data.get("caption_style") or "",
        visual_source=data.get("visual_source") or "",
        music=str(data.get("music", "on")).lower() not in ("0", "false", "off", ""),
        music_volume=num("music_volume", 0.12, float),
        custom_script=str(data.get("custom_script", "")),
        seed=num("seed", 0),
    )


def create_app(settings=None) -> Flask:
    settings = settings or get_settings()
    app = Flask(__name__)
    jobs = JobManager(settings)
    app.config["settings"] = settings

    @app.context_processor
    def globals_():
        return dict(niches=NICHES, formats=FORMATS, voices=VOICES, art_styles=ART_STYLES,
                    caption_styles=CAPTION_STYLES, languages=LANGUAGES)

    def status():
        return {
            "claude": settings.has_claude,
            "model": settings.claude_model,
            "tts": [e.name for e in get_engines(settings)],
            "pexels": bool(settings.pexels_api_key),
            "pixabay": bool(settings.pixabay_api_key),
            "ffmpeg": bool(shutil.which("ffmpeg")),
        }

    @app.get("/")
    def index():
        return render_template("index.html", status=status(), recent=library(settings)[:6],
                               active=[j for j in jobs.list() if j.status in ("queued", "running")])

    @app.post("/generate")
    def generate():
        form = request.form.to_dict()
        topics = [t.strip() for t in form.get("topics", "").splitlines() if t.strip()]
        if form.get("topic", "").strip():
            topics.insert(0, form["topic"].strip())
        if not topics:
            return redirect(url_for("index"))
        for i, topic in enumerate(topics[:200]):
            req = _request_from({**form, "topic": topic})
            req.seed = req.seed + i
            jobs.submit(req)
        return redirect(url_for("jobs_page"))

    @app.get("/jobs")
    def jobs_page():
        return render_template("jobs.html", jobs=jobs.list())

    @app.get("/library")
    def library_page():
        return render_template("library.html", items=library(settings))

    @app.get("/video/<item_id>")
    def video_page(item_id):
        item = read_item(settings, item_id)
        if not item:
            abort(404)
        return render_template("video.html", item=item)

    @app.get("/files/<item_id>/<name>")
    def files(item_id, name):
        if name not in ALLOWED_FILES or not read_item(settings, item_id):
            abort(404)
        return send_from_directory(settings.output_dir / item_id, name,
                                   as_attachment=request.args.get("download") == "1")

    @app.post("/video/<item_id>/delete")
    def delete_video(item_id):
        if read_item(settings, item_id):
            shutil.rmtree(settings.output_dir / item_id, ignore_errors=True)
        return redirect(url_for("library_page"))

    # ---- JSON API
    @app.post("/api/generate")
    def api_generate():
        data = request.get_json(force=True) or {}
        req = _request_from(data)
        if not req.topic and not req.custom_script:
            return jsonify(error="topic is required"), 400
        return jsonify(asdict(jobs.submit(req))), 202

    @app.get("/api/jobs")
    def api_jobs():
        return jsonify([asdict(j) for j in jobs.list()[:200]])

    @app.get("/api/jobs/<job_id>")
    def api_job(job_id):
        job = jobs.get(job_id)
        return (jsonify(asdict(job)), 200) if job else (jsonify(error="not found"), 404)

    @app.post("/api/ideas")
    def api_ideas():
        data = request.get_json(force=True) or {}
        try:
            topics = suggest_topics(settings, data.get("niche", "facts"), int(data.get("count", 10)),
                                    data.get("language", "en"))
        except Exception as e:
            return jsonify(error=str(e)), 502
        return jsonify(topics=topics)

    @app.get("/api/status")
    def api_status():
        return jsonify(status())

    return app


def serve(host: str = "127.0.0.1", port: int = 5000) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_app().run(host=host, port=port, threaded=True)
