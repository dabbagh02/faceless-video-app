"""End-to-end pipeline: topic -> script -> voice-over -> visuals -> music -> captions -> MP4 + metadata."""
from __future__ import annotations

import json
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import audio, captions, music, quality, render, tts, visuals
from .config import Settings
from .models import Script, VideoRequest, VideoResult, WordTiming
from .presets import ART_STYLES, CAPTION_STYLES, FORMATS, VOICES, niche as get_niche
from .script_writer import get_writer, resolve_language
from .thumbnail import make_thumbnail

log = logging.getLogger(__name__)
ProgressFn = Callable[[str, float], None]


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", text, flags=re.U).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:n].strip("-") or "video"


def fmt_ts(t: float) -> str:
    t = int(t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_chapters(script: Script) -> list[tuple[float, str]]:
    """YouTube chapter rules: first at 0:00, >= 3 chapters, each >= 10 s."""
    chapters: list[tuple[float, str]] = []
    for scene, title in zip(script.scenes, script.chapter_titles):
        if not title:
            continue
        start = 0.0 if not chapters else scene.start
        if chapters and start - chapters[-1][0] < 10:
            continue
        chapters.append((start, title))
    total = script.scenes[-1].start + script.scenes[-1].duration
    if chapters and total - chapters[-1][0] < 10:
        chapters.pop()
    return chapters if len(chapters) >= 3 else []


def build_description(script: Script, chapters: list[tuple[float, str]]) -> str:
    parts = [script.description.strip()]
    if chapters:
        parts.append("\n".join(f"{fmt_ts(t)} {name}" for t, name in chapters))
    return "\n\n".join(p for p in parts if p)


def _fit_duration(scenes, max_seconds: float, gap: float, lead: float, tail: float) -> None:
    """Speed narration up slightly (max 20%) and, if still too long, drop middle scenes."""
    def total():
        return lead + sum(tts.audio_duration(s.audio_path) for s in scenes) + gap * (len(scenes) - 1) + tail

    t = total()
    if t <= max_seconds:
        return
    speech = t - lead - tail - gap * (len(scenes) - 1)
    tempo = min(1.2, speech / max(1.0, (max_seconds - lead - tail - gap * (len(scenes) - 1))) + 0.01)
    for s in scenes:
        src = Path(s.audio_path)
        tmp = src.with_suffix(".tmp.wav")
        tts.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", f"atempo={tempo:.3f}", "-ar", "48000",
                 "-ac", "1", "-c:a", "pcm_s16le", str(tmp)])
        tmp.replace(src)
        s.words = [WordTiming(w.text, w.start / tempo, w.end / tempo) for w in s.words]
    while total() > max_seconds and len(scenes) > 2:
        scenes.pop(len(scenes) - 2)  # keep the hook and the payoff


def generate_video(req: VideoRequest, settings: Settings, progress: ProgressFn | None = None,
                   out_dir: Path | None = None, force_offline_script: bool = False, run_qa: bool = True,
                   writer=None) -> VideoResult:
    t0 = time.time()
    report = lambda stage, frac: progress and progress(stage, frac)
    n = get_niche(req.niche)
    fmt = FORMATS.get(req.format, FORMATS["short"])
    voice = VOICES.get(req.voice) or VOICES[n.voice]
    language = resolve_language(req)
    if not req.voice and voice.language != language:  # pick a voice that speaks the language
        voice = next(v for v in VOICES.values() if v.language == language)
    style = ART_STYLES.get(req.art_style or n.art_style, ART_STYLES["cinematic"])
    cap_style = CAPTION_STYLES.get(req.caption_style or n.caption_style, CAPTION_STYLES["bold_pop"])
    W, H = fmt.width, fmt.height

    if out_dir is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = settings.output_dir / f"{stamp}-{slugify(req.topic)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    (out_dir / "request.json").write_text(json.dumps(req.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # 1. script
    report("Writing script", 0.02)
    writer = writer or get_writer(settings, force_offline=force_offline_script)
    script = writer.write(req)
    script.language = language
    (out_dir / "script.json").write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. voice-over, one clip per scene
    engine_used = ""
    for i, scene in enumerate(script.scenes):
        report("Recording voice-over", 0.08 + 0.17 * i / len(script.scenes))
        path = work / f"voice_{i:03d}.wav"
        scene.words, engine_used = tts.synthesize(settings, scene.narration, voice, path, n.speech_rate,
                                                  preferred=engine_used)
        scene.audio_path = str(path)

    # 3. timeline
    gap = 0.28 if fmt.vertical else 0.45
    lead, tail = 0.12, 1.2
    max_seconds = fmt.max_seconds if not req.duration else min(fmt.max_seconds, max(req.duration * 1.25, 20))
    if fmt.vertical:
        _fit_duration(script.scenes, max_seconds, gap, lead, tail)
    script.chapter_titles = script.chapter_titles[:len(script.scenes)] + [""] * (
        len(script.scenes) - len(script.chapter_titles))
    t = lead
    for scene in script.scenes:
        scene.start = t
        scene.duration = tts.audio_duration(scene.audio_path)
        t += scene.duration + gap
    total = round(t - gap + tail, 3)

    # 4. visuals
    report("Creating visuals", 0.27)
    vis_usage = visuals.fetch_visuals(settings, script.scenes, W, H, req.visual_source, n.palette, req.seed,
                                      on_progress=lambda a, b: report("Creating visuals", 0.27 + 0.18 * a / b))

    # 5. audio: voice + music, mastered for YouTube
    report("Mixing audio", 0.46)
    voice_wav = work / "voice.wav"
    audio.build_voice_track(script.scenes, total, voice_wav)
    music_path = music.pick_music(n.music_mood, total, work / "music.wav", req.seed) if req.music else None
    final_wav = work / "final_audio.wav"
    loud = audio.mix_and_master(voice_wav, music_path, total, final_wav, req.music_volume)

    # 6. captions
    ass_path, srt_path = out_dir / "captions.ass", out_dir / "captions.srt"
    captions.write_captions(ass_path, srt_path, script.scenes, cap_style, W, H, language, total)

    # 7. render
    video_path = out_dir / "video.mp4"
    render.render_video(settings, script.scenes, total, W, H, final_wav, ass_path, video_path, style.grade,
                        dark=n.music_mood in ("dark", "tense"), seed=req.seed,
                        on_progress=lambda f: report("Rendering video", 0.5 + 0.45 * f))

    # 8. thumbnail + metadata
    report("Thumbnail & metadata", 0.96)
    thumb = make_thumbnail(script.scenes[0].visual_path, script.thumbnail_text, n.palette[2],
                           out_dir / "thumbnail.jpg", language)
    chapters = [] if fmt.vertical else build_chapters(script)
    description = build_description(script, chapters)
    if fmt.vertical and "#shorts" not in description.lower():
        description += "\n\n#shorts"
    meta = {
        "title": script.title,
        "description": description,
        "tags": script.tags,
        "language": language,
        "format": fmt.key,
        "resolution": f"{W}x{H}",
        "duration": total,
        "chapters": [{"start": fmt_ts(t), "title": c} for t, c in chapters],
        "niche": n.key,
        "voice": voice.key,
        "tts_engine": engine_used,
        "script_engine": type(writer).__name__,
        "visual_sources": vis_usage,
        "music": "library" if music_path and music_path.parent != work else ("generated" if music_path else "none"),
        "loudness_input_lufs": loud["input_lufs"],
        "render_seconds": None,
    }
    (out_dir / "description.txt").write_text(f"{script.title}\n\n{description}\n\nTags: {', '.join(script.tags)}\n",
                                             encoding="utf-8")

    qa = {}
    if run_qa:
        report("Quality check", 0.98)
        qa = quality.check_video(video_path, W, H, settings.fps, total, fmt.max_seconds if fmt.vertical else None)
    meta["render_seconds"] = round(time.time() - t0, 1)
    meta["qa"] = qa
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    report("Done", 1.0)
    return VideoResult(video_path, thumb, meta_path, srt_path, total, script, qa)
