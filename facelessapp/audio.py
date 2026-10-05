"""Voice + music mixing and YouTube loudness mastering (-14 LUFS, -1.5 dBTP)."""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .models import Scene

SR = 48000
TARGET_LUFS = -14.0


def read_wav(path: str | Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2, path
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())


def build_voice_track(scenes: list[Scene], total: float, out: Path) -> None:
    track = np.zeros(int(total * SR) + SR, np.float32)
    for s in scenes:
        data = read_wav(s.audio_path)
        i = int(s.start * SR)
        track[i:i + len(data)] += data[: len(track) - i]
    write_wav(out, track[: int(total * SR)])


def _run(cmd: list) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(map(str, cmd))}\n{p.stderr[-2000:]}")
    return p.stderr


VOICE_CHAIN = ("highpass=f=75,lowpass=f=15000,"
               "equalizer=f=200:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.5:g=2.5,"
               "acompressor=threshold=-21dB:ratio=3:attack=6:release=120:makeup=2,"
               "alimiter=limit=0.95:level=disabled")


def mix_and_master(voice_wav: Path, music_path: Path | None, total: float, out_wav: Path,
                   music_volume: float = 0.12) -> dict:
    """Mix voice with ducked music, then 2-pass loudnorm. Returns measured loudness stats."""
    tmp = out_wav.with_name("premaster.wav")
    if music_path:
        fade_start = max(0.0, total - 2.5)
        graph = (
            f"[0:a]{VOICE_CHAIN},asplit=2[v][sc];"
            f"[1:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
            f"volume={music_volume:.3f},afade=t=in:d=1.2,afade=t=out:st={fade_start:.2f}:d=2.5[m];"
            f"[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=450[md];"
            f"[v]aformat=channel_layouts=stereo[vs];"
            f"[vs][md]amix=inputs=2:duration=first:normalize=0[out]"
        )
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_wav), "-stream_loop", "-1", "-i", str(music_path),
              "-filter_complex", graph, "-map", "[out]", "-t", f"{total:.3f}", "-ar", str(SR),
              "-c:a", "pcm_s16le", str(tmp)])
    else:
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_wav), "-af", VOICE_CHAIN + ",aformat=channel_layouts=stereo",
              "-ar", str(SR), "-c:a", "pcm_s16le", str(tmp)])

    # pass 1: measure
    err = _run(["ffmpeg", "-y", "-v", "info", "-i", str(tmp), "-af",
                f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)[-1])
    # pass 2: apply (linear mode keeps dynamics natural)
    af = (f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          f"linear=true:print_format=json")
    _run(["ffmpeg", "-y", "-v", "info", "-i", str(tmp), "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le", str(out_wav)])
    tmp.unlink(missing_ok=True)
    return {"input_lufs": float(m["input_i"])}
