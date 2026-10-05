"""Automatic QA for rendered videos (used by the app and the 100-video stress test)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def analyse(path: Path) -> dict:
    """One decode pass: decode errors, black segments, loudness, long silences."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(path),
                        "-vf", "blackdetect=d=0.6:pix_th=0.06",
                        "-af", "ebur128=peak=true,silencedetect=n=-45dB:d=2.5",
                        "-f", "null", "-"], capture_output=True, text=True)
    err = p.stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    peak = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    decode_errors = [l for l in err.splitlines() if re.search(r"error|corrupt|invalid", l, re.I)
                     and "blackdetect" not in l]
    return {
        "returncode": p.returncode,
        "integrated_lufs": float(lufs[-1]) if lufs else None,
        "true_peak_dbfs": float(peak[-1]) if peak and peak[-1] != "-inf" else None,
        "black_segments": len(re.findall(r"black_start", err)),
        "long_silences": len(re.findall(r"silence_start", err)),
        "decode_errors": decode_errors[:5],
    }


def check_video(path: Path, width: int, height: int, fps: int, expected_duration: float,
                max_duration: float | None = None) -> dict:
    issues: list[str] = []
    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"].get("duration", 0))
    if not v:
        issues.append("no video stream")
    else:
        if (v["width"], v["height"]) != (width, height):
            issues.append(f"resolution {v['width']}x{v['height']} != {width}x{height}")
        if v["codec_name"] != "h264" or v.get("pix_fmt") != "yuv420p":
            issues.append(f"video codec {v['codec_name']}/{v.get('pix_fmt')}")
        num, den = map(int, v["r_frame_rate"].split("/"))
        if abs(num / den - fps) > 0.01:
            issues.append(f"fps {num / den:.2f} != {fps}")
    if not a:
        issues.append("no audio stream")
    elif a["codec_name"] != "aac" or int(a["sample_rate"]) != 48000:
        issues.append(f"audio {a['codec_name']} {a['sample_rate']}")
    if abs(duration - expected_duration) > 0.6:
        issues.append(f"duration {duration:.2f}s != expected {expected_duration:.2f}s")
    if max_duration and duration > max_duration + 0.05:
        issues.append(f"duration {duration:.2f}s exceeds {max_duration}s")
    a_res = analyse(path)
    if a_res["returncode"] != 0 or a_res["decode_errors"]:
        issues.append(f"decode problems: {a_res['decode_errors'][:2]}")
    if a_res["integrated_lufs"] is None or abs(a_res["integrated_lufs"] + 14) > 1.5:
        issues.append(f"loudness {a_res['integrated_lufs']} LUFS (target -14)")
    if a_res["true_peak_dbfs"] is not None and a_res["true_peak_dbfs"] > -0.5:
        issues.append(f"peak {a_res['true_peak_dbfs']} dBFS too hot")
    if a_res["black_segments"]:
        issues.append(f"{a_res['black_segments']} black segment(s)")
    if a_res["long_silences"]:
        issues.append(f"{a_res['long_silences']} long silence(s)")
    return {
        "ok": not issues,
        "issues": issues,
        "duration": round(duration, 3),
        "size_mb": round(path.stat().st_size / 1e6, 2),
        "bitrate_kbps": round(int(info["format"].get("bit_rate", 0)) / 1000),
        **{k: a_res[k] for k in ("integrated_lufs", "true_peak_dbfs")},
    }
