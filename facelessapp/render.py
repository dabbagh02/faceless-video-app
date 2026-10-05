"""Video rendering: Ken Burns motion, transitions, grading, captions and final H.264 encode.

Frames are composed in Python (PIL, sub-pixel smooth camera moves) and piped as raw RGB
into ffmpeg, which adds grading/grain, burns the ASS captions and muxes the mastered audio.
"""
from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageOps

from .config import FONTS_DIR, Settings
from .models import Scene

MOTIONS = ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down")


def _ease(x: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, x)))


class ImageSource:
    """Still image with a slow cinematic camera move (Ken Burns)."""

    def __init__(self, path: str, width: int, height: int, motion: str, strength: float = 0.12):
        self.w, self.h = width, height
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        # cover-fit into a canvas (1+strength) larger than the frame
        scale = max(width * (1 + strength) / img.width, height * (1 + strength) / img.height)
        self.img = img.resize((max(width, round(img.width * scale)), max(height, round(img.height * scale))),
                              Image.LANCZOS)
        self.motion = motion
        self.strength = strength

    def frame(self, p: float) -> Image.Image:
        """p in [0, 1] = progress through this source's on-screen time."""
        e = 0.15 * p + 0.85 * _ease(p)  # mostly eased, never fully stopped
        W, H = self.img.size
        fit_w = min(W, H * self.w / self.h)  # largest crop with the frame's aspect ratio
        if self.motion in ("zoom_in", "zoom_out"):
            z = e if self.motion == "zoom_in" else 1 - e
            cw = fit_w / (1 + self.strength * z)
            ch = cw * self.h / self.w
            cx, cy = W / 2, H / 2
        else:
            cw = fit_w / (1 + self.strength * 0.15)
            ch = cw * self.h / self.w
            span_x, span_y = W - cw, H - ch
            cx, cy = W / 2, H / 2
            if self.motion == "pan_left":
                cx = cw / 2 + span_x * (1 - e)
            elif self.motion == "pan_right":
                cx = cw / 2 + span_x * e
            elif self.motion == "pan_up":
                cy = ch / 2 + span_y * (1 - e)
            elif self.motion == "pan_down":
                cy = ch / 2 + span_y * e
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        return self.img.resize((self.w, self.h), Image.BILINEAR, box=box)

    def close(self):
        pass


class VideoSource:
    """Stock video clip, cover-cropped to the frame and looped if shorter than needed."""

    def __init__(self, path: str, width: int, height: int, fps: int, seconds: float):
        self.path, self.w, self.h, self.fps = path, width, height, fps
        self.frames_needed = int(seconds * fps) + 2
        self.proc = None
        self.last = Image.new("RGB", (width, height))
        self.index = -1
        self._open()

    def _open(self):
        if self.proc:
            self.proc.kill()
        vf = (f"fps={self.fps},scale={self.w}:{self.h}:force_original_aspect_ratio=increase:flags=bicubic,"
              f"crop={self.w}:{self.h},setsar=1")
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", self.path, "-an", "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _read(self) -> Image.Image | None:
        n = self.w * self.h * 3
        buf = self.proc.stdout.read(n)
        if len(buf) < n:
            return None
        return Image.frombuffer("RGB", (self.w, self.h), buf, "raw", "RGB", 0, 1)

    def frame(self, p: float) -> Image.Image:
        target = min(self.frames_needed - 1, int(p * (self.frames_needed - 1)))
        while self.index < target:
            img = self._read()
            if img is None:  # loop
                self._open()
                img = self._read()
                if img is None:
                    break
            self.last = img
            self.index += 1
        return self.last

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc = None


def vignette_mask(width: int, height: int, strength: float = 0.35) -> Image.Image:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    d = np.sqrt(((xx - width / 2) / (width / 2)) ** 2 + ((yy - height / 2) / (height / 2)) ** 2) / math.sqrt(2)
    m = 1 - strength * np.clip((d - 0.35) / 0.65, 0, 1) ** 1.6
    a = (m * 255).astype(np.uint8)
    return Image.fromarray(np.stack([a, a, a], -1))


def plan_transitions(n: int, vertical: bool, dark: bool, seed: int) -> list[str]:
    rng = random.Random(seed)
    if vertical:
        choices, weights = ["crossfade", "slide", "zoom", "flash"], [4, 3, 3, 1]
    else:
        choices, weights = ["crossfade", "dip", "slide", "zoom"], [6, 2, 1, 1]
    if dark:
        choices = [c if c != "flash" else "dip" for c in choices]
    return [rng.choices(choices, weights)[0] for _ in range(max(0, n - 1))]


def _compose_transition(kind: str, a: Image.Image, b: Image.Image, x: float) -> Image.Image:
    """x in [0,1]: 0 = all A, 1 = all B."""
    e = _ease(x)
    if kind == "dip":
        if x < 0.5:
            return Image.blend(a, Image.new("RGB", a.size), _ease(x * 2))
        return Image.blend(Image.new("RGB", a.size), b, _ease((x - 0.5) * 2))
    if kind == "flash":
        white = Image.new("RGB", a.size, (255, 255, 255))
        base = a if x < 0.5 else b
        return Image.blend(base, white, 0.85 * (1 - abs(x - 0.5) * 2) ** 2)
    if kind == "slide":
        w, h = a.size
        off = int(round(w * e))
        out = Image.new("RGB", a.size)
        out.paste(a, (-off, 0))
        out.paste(b, (w - off, 0))
        return out
    if kind == "zoom":
        w, h = a.size
        if x < 0.5:  # punch into A ...
            z, src = 1 + 0.25 * _ease(x * 2), a
        else:  # ... and settle out of a zoomed B
            z, src = 1 + 0.25 * (1 - _ease((x - 0.5) * 2)), b
        cw, ch = w / z, h / z
        return src.resize((w, h), Image.BILINEAR, box=((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2))
    return Image.blend(a, b, e)


def render_video(settings: Settings, scenes: list[Scene], total: float, width: int, height: int,
                 audio_wav: Path, ass_path: Path, out_path: Path, grade: dict, dark: bool = False,
                 seed: int = 0, on_progress=None, transition: float = 0.45) -> None:
    fps = settings.fps
    vertical = height > width
    n_frames = int(round(total * fps))
    rng = random.Random(seed)

    # visual segments: scene i is on screen from its start to the next scene's start
    bounds = [s.start for s in scenes] + [total]
    bounds[0] = 0.0
    kinds = plan_transitions(len(scenes), vertical, dark, seed)
    motions, last = [], None
    for _ in scenes:
        m = rng.choice([x for x in MOTIONS if x != last])
        motions.append(m)
        last = m

    sources: dict[int, object] = {}

    def source(i: int):
        if i not in sources:
            s = scenes[i]
            seg = bounds[i + 1] - bounds[i] + transition
            if s.visual_kind == "video":
                sources[i] = VideoSource(s.visual_path, width, height, fps, seg)
            else:
                sources[i] = ImageSource(s.visual_path, width, height, motions[i])
        return sources[i]

    def scene_frame(i: int, t: float) -> Image.Image:
        start = bounds[i] - (transition / 2 if i else 0)
        end = bounds[i + 1] + transition / 2
        return source(i).frame((t - start) / max(0.001, end - start))

    vig = vignette_mask(width, height, 0.38 if dark else 0.28)
    eq = ":".join(f"{k}={v}" for k, v in {"contrast": 1.05, "saturation": 1.05, **grade}.items())
    fonts = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")
    ass = str(ass_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    vf = (f"eq={eq},"
          f"ass='{ass}':fontsdir='{fonts}',"
          f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
           "-i", str(audio_wav),
           "-vf", vf, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", settings.x264_preset, "-crf", str(settings.crf),
           "-profile:v", "high", "-g", str(fps * 2), "-bf", "2",
           "-maxrate", "16M", "-bufsize", "32M",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        cur = 0
        for f in range(n_frames):
            t = f / fps
            while cur + 1 < len(scenes) and t >= bounds[cur + 1] + transition / 2:
                done = sources.pop(cur, None)
                if done:
                    done.close()
                cur += 1
            nxt = cur + 1
            if nxt < len(scenes) and t >= bounds[nxt] - transition / 2:
                x = (t - (bounds[nxt] - transition / 2)) / transition
                frame = _compose_transition(kinds[cur], scene_frame(cur, t), scene_frame(nxt, t), x)
            else:
                frame = scene_frame(cur, t)
            frame = ImageChops.multiply(frame, vig)
            proc.stdin.write(frame.tobytes())
            if on_progress and f % fps == 0:
                on_progress(f / n_frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg encode failed:\n{err[-3000:]}")
    except BrokenPipeError:
        err = proc.stderr.read().decode(errors="replace")
        proc.wait()
        raise RuntimeError(f"ffmpeg encode failed:\n{err[-3000:]}")
    finally:
        for s in sources.values():
            s.close()
        if proc.poll() is None:
            proc.kill()
