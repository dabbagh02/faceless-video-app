"""Voice-over synthesis with word-level timings (used for animated captions).

Engines:
- edge:       Microsoft Edge neural voices (free, high quality, exact word timings)
- elevenlabs: ElevenLabs (paid, most natural, character-level timings)
- espeak:     espeak-ng (offline fallback, robotic; timings estimated)

Every engine returns a 48 kHz mono WAV plus a list of WordTiming.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import Settings
from .models import WordTiming
from .presets import Voice

log = logging.getLogger(__name__)
SAMPLE_RATE = 48000


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def audio_duration(path: str | Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]).stdout
    return float(json.loads(out)["format"]["duration"])


def to_wav(src: Path, dst: Path, tempo: float = 1.0) -> None:
    """Convert to 48k mono wav, trimming leading/trailing silence."""
    filters = ["silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05",
               "areverse", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1", "areverse"]
    if abs(tempo - 1.0) > 0.01:
        filters.append(f"atempo={tempo:.3f}")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", ",".join(filters),
         "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


def split_words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def estimate_timings(text: str, duration: float) -> list[WordTiming]:
    """Distribute words across `duration` proportionally to their length (+ pauses at punctuation)."""
    words = split_words(text)
    if not words:
        return []
    weights = []
    for w in words:
        weight = 1.0 + len(re.sub(r"\W", "", w)) * 0.32
        if re.search(r"[.!?؟]$", w):
            weight += 1.6
        elif re.search(r"[,;:،]$", w):
            weight += 0.8
        weights.append(weight)
    scale = duration / sum(weights)
    t, out = 0.0, []
    for w, weight in zip(words, weights):
        span = weight * scale
        speak = span * (0.8 if re.search(r"[.!?,;:؟،]$", w) else 0.95)
        out.append(WordTiming(w, round(t, 3), round(t + speak, 3)))
        t += span
    return out


class EspeakTTS:
    name = "espeak"

    def available(self) -> bool:
        return bool(shutil.which("espeak-ng") or shutil.which("espeak"))

    def synthesize(self, text: str, voice: Voice, out_wav: Path, rate: str = "+0%") -> list[WordTiming]:
        exe = shutil.which("espeak-ng") or "espeak"
        pct = int(re.sub(r"[^\d-]", "", rate) or 0)
        speed = int(160 * (1 + pct / 100))
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "raw.wav"
            run([exe, "-v", voice.espeak, "-s", str(speed), "-p", "40", "-g", "2", "-w", str(raw), text])
            to_wav(raw, out_wav)
        return estimate_timings(text, audio_duration(out_wav))


class EdgeTTS:
    name = "edge"

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    async def _synth(self, text: str, voice: str, rate: str, mp3: Path) -> list[WordTiming]:
        import edge_tts
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        words: list[WordTiming] = []
        with open(mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    words.append(WordTiming(chunk["text"], start, start + chunk["duration"] / 1e7))
        return words

    def synthesize(self, text: str, voice: Voice, out_wav: Path, rate: str = "+0%") -> list[WordTiming]:
        with tempfile.TemporaryDirectory() as td:
            mp3 = Path(td) / "v.mp3"
            boundaries = asyncio.run(self._synth(text, voice.edge, rate, mp3))
            if not mp3.exists() or mp3.stat().st_size == 0:
                raise RuntimeError("edge-tts returned no audio")
            # Leading silence is trimmed in to_wav; shift timings by the measured offset.
            lead = _leading_silence(mp3)
            to_wav(mp3, out_wav)
        dur = audio_duration(out_wav)
        words = [WordTiming(w.text, max(0.0, w.start - lead), min(dur, w.end - lead)) for w in boundaries]
        return attach_punctuation(text, words) if words else estimate_timings(text, dur)


class ElevenLabsTTS:
    name = "elevenlabs"
    MODEL = "eleven_multilingual_v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def synthesize(self, text: str, voice: Voice, out_wav: Path, rate: str = "+0%") -> list[WordTiming]:
        import httpx
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice.elevenlabs}/with-timestamps",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": self.MODEL,
                  "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3}},
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        with tempfile.TemporaryDirectory() as td:
            mp3 = Path(td) / "v.mp3"
            mp3.write_bytes(base64.b64decode(data["audio_base64"]))
            lead = _leading_silence(mp3)
            pct = int(re.sub(r"[^\d-]", "", rate) or 0)
            tempo = 1 + pct / 100
            to_wav(mp3, out_wav, tempo=tempo)
        words = _words_from_chars(data.get("alignment") or {}, lead, tempo)
        dur = audio_duration(out_wav)
        return words or estimate_timings(text, dur)


def _words_from_chars(al: dict, lead: float, tempo: float) -> list[WordTiming]:
    chars = al.get("characters") or []
    starts = al.get("character_start_times_seconds") or []
    ends = al.get("character_end_times_seconds") or []
    words, cur, s, e = [], "", None, 0.0
    for c, cs, ce in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                words.append(WordTiming(cur, (s - lead) / tempo, (e - lead) / tempo))
            cur, s = "", None
            continue
        if s is None:
            s = cs
        cur += c
        e = ce
    if cur:
        words.append(WordTiming(cur, (s - lead) / tempo, (e - lead) / tempo))
    return [WordTiming(w.text, max(0.0, w.start), max(0.0, w.end)) for w in words]


def _leading_silence(path: Path) -> float:
    """Seconds of leading silence (matches the threshold used by to_wav)."""
    p = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af",
                        "silencedetect=noise=-50dB:d=0.05", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"silence_start: (-?[\d.]+)\s.*?silence_end: ([\d.]+)", p.stderr, re.S)
    if m and float(m.group(1)) <= 0.01:
        return max(0.0, float(m.group(2)) - 0.05)  # to_wav keeps 50 ms of lead-in
    return 0.0


def attach_punctuation(text: str, words: list[WordTiming]) -> list[WordTiming]:
    """Edge word boundaries drop punctuation; map them back onto the original tokens."""
    tokens = split_words(text)
    norm = lambda s: re.sub(r"[^\w]", "", s.lower())
    out, ti = [], 0
    for w in words:
        target = norm(w.text)
        j = ti
        while j < len(tokens) and j < ti + 4 and norm(tokens[j]) != target and target not in norm(tokens[j]):
            j += 1
        if j < len(tokens) and j < ti + 4:
            out.append(WordTiming(tokens[j], w.start, w.end))
            ti = j + 1
        else:
            out.append(w)
    return out


def get_engines(settings: Settings, preferred: str = "") -> list:
    pref = (preferred or settings.tts_engine or "auto").lower()
    engines = {
        "elevenlabs": ElevenLabsTTS(settings.elevenlabs_api_key),
        "edge": EdgeTTS(),
        "espeak": EspeakTTS(),
    }
    order = ["elevenlabs", "edge", "espeak"] if pref == "auto" else [pref] + [
        k for k in ("edge", "espeak") if k != pref]
    return [engines[k] for k in order if k in engines and engines[k].available()]


def synthesize(settings: Settings, text: str, voice: Voice, out_wav: Path, rate: str = "+0%",
               preferred: str = "") -> tuple[list[WordTiming], str]:
    """Try engines in order; returns (word timings, engine name used)."""
    errors = []
    for engine in get_engines(settings, preferred):
        try:
            return engine.synthesize(text, voice, out_wav, rate), engine.name
        except Exception as e:  # network down, quota, etc. -> next engine
            log.warning("TTS engine %s failed: %s", engine.name, e)
            errors.append(f"{engine.name}: {e}")
    raise RuntimeError("All TTS engines failed: " + "; ".join(errors))
