"""Background music.

If `assets/music/<mood>/` (or `assets/music/`) contains audio files, one is picked.
Otherwise a royalty-free ambient bed is synthesised for the mood, so every video
always has music and there are never copyright claims.
"""
from __future__ import annotations

import random
import wave
from pathlib import Path

import numpy as np

from .config import MUSIC_DIR

SR = 48000
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

# chord progressions as semitone offsets from the root (minor/major triads + 7ths)
MOODS = {
    "dark": dict(root=38, prog=[[0, 3, 7], [-4, 0, 3], [-2, 2, 5], [-5, -2, 2]], bpm=60, pulse=False, bright=0.25),
    "tense": dict(root=40, prog=[[0, 3, 6], [1, 4, 8], [0, 3, 7], [-1, 3, 6]], bpm=84, pulse=True, bright=0.3),
    "epic": dict(root=41, prog=[[0, 3, 7], [-4, 0, 3], [-7, -3, 0], [-2, 2, 5]], bpm=72, pulse=True, bright=0.45),
    "uplifting": dict(root=45, prog=[[0, 4, 7], [-5, -1, 2], [-3, 0, 4], [-7, -3, 0]], bpm=96, pulse=True, bright=0.6),
    "playful": dict(root=48, prog=[[0, 4, 7], [5, 9, 12], [-3, 0, 4], [7, 11, 14]], bpm=108, pulse=True, bright=0.7),
    "ambient": dict(root=43, prog=[[0, 4, 7, 11], [-3, 0, 4, 7], [5, 9, 12, 16], [2, 5, 9, 12]], bpm=64, pulse=False,
                    bright=0.4),
}


def _freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    """One-pole lowpass via cumulative IIR in vectorised chunks."""
    from scipy.signal import lfilter  # type: ignore
    return lfilter([alpha], [1, alpha - 1], x)


def _lowpass_np(x: np.ndarray, alpha: float) -> np.ndarray:
    try:
        return _lowpass(x, alpha)
    except ImportError:
        # FFT-based gentle lowpass fallback
        spec = np.fft.rfft(x)
        f = np.fft.rfftfreq(len(x), 1 / SR)
        cutoff = alpha * SR / (2 * np.pi)
        spec /= np.sqrt(1 + (f / max(cutoff, 1)) ** 4)
        return np.fft.irfft(spec, len(x))


def synthesize(mood: str, seconds: float, seed: int = 0) -> np.ndarray:
    cfg = MOODS.get(mood, MOODS["ambient"])
    rng = random.Random(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    beat = 60 / cfg["bpm"]
    bar = beat * 4
    prog = cfg["prog"][:]
    if rng.random() < 0.5:
        prog = prog[1:] + prog[:1]
    root = cfg["root"] + rng.choice([-2, 0, 0, 2])
    out = np.zeros(n)

    bars = int(np.ceil(seconds / bar)) + 1
    for b in range(bars):
        chord = prog[b % len(prog)]
        s0 = int(b * bar * SR)
        s1 = min(n, int((b + 1) * bar * SR + 0.6 * SR))
        if s0 >= n:
            break
        seg_t = t[s0:s1] - b * bar
        env = np.minimum(1, seg_t / 0.9) * np.exp(-np.maximum(0, seg_t - bar) / 0.4)
        for k, iv in enumerate(chord):
            f = _freq(root + 12 + iv)
            for det in (-0.12, 0.0, 0.11):  # detuned pad voices
                ph = rng.random() * 6.28
                tone = np.sin(2 * np.pi * f * (1 + det / 100) * seg_t + ph)
                tone += 0.35 * np.sin(2 * np.pi * 2 * f * seg_t + ph) * cfg["bright"]
                out[s0:s1] += tone * env * 0.06
        # bass
        fb = _freq(root + chord[0] - 12)
        out[s0:s1] += np.sin(2 * np.pi * fb * seg_t) * env * 0.12
        # rhythmic pulse (soft pluck on 8th notes)
        if cfg["pulse"]:
            for e in range(8):
                p0 = s0 + int(e * beat / 2 * SR)
                p1 = min(n, p0 + int(0.35 * SR))
                if p0 >= n:
                    break
                pt = t[p0:p1] - t[p0]
                note = root + 24 + chord[(e * 2 + b) % len(chord)]
                out[p0:p1] += np.sin(2 * np.pi * _freq(note) * pt) * np.exp(-pt / 0.09) * 0.05 * cfg["bright"]
            if mood in ("epic", "tense"):
                for q in range(4):  # low "boom" on each beat
                    k0 = s0 + int(q * beat * SR)
                    k1 = min(n, k0 + int(0.5 * SR))
                    if k0 >= n:
                        break
                    kt = t[k0:k1] - t[k0]
                    out[k0:k1] += np.sin(2 * np.pi * (55 * np.exp(-kt * 8) + 40) * kt) * np.exp(-kt / 0.18) * 0.18

    out = _lowpass_np(out, 0.12 + cfg["bright"] * 0.25)
    # simple stereo-ish reverb tail (feedback delays), mono output
    for d, g in ((0.113, 0.35), (0.271, 0.25), (0.433, 0.18)):
        k = int(d * SR)
        out[k:] += out[:-k] * g
    fade = int(min(2.0, seconds / 4) * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    peak = np.max(np.abs(out)) or 1
    return (out / peak * 0.7).astype(np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def pick_music(mood: str, seconds: float, out_path: Path, seed: int = 0) -> Path:
    for folder in (MUSIC_DIR / mood, MUSIC_DIR):
        if folder.is_dir():
            files = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT)
            if files:
                return random.Random(seed).choice(files)
    write_wav(out_path, synthesize(mood, seconds + 1, seed))
    return out_path
