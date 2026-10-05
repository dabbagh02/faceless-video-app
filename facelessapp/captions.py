"""Animated captions (ASS, burned in with libass) and SRT export for YouTube."""
from __future__ import annotations

import re
from pathlib import Path

from .models import Scene, WordTiming
from .presets import CaptionStyle

ARABIC_RE = re.compile(r"[؀-ۿ]")


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _srt_ts(t: float) -> str:
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def all_words(scenes: list[Scene]) -> list[WordTiming]:
    """Word timings on the global (video) timeline."""
    out = []
    for s in scenes:
        for w in s.words:
            out.append(WordTiming(w.text, s.start + w.start, s.start + w.end))
    return out


def chunk_words(words: list[WordTiming], per_chunk: int, max_chars: int = 26, max_gap: float = 0.6) -> list[list[WordTiming]]:
    """Group words into caption chunks, breaking on punctuation, long pauses and length."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        if cur:
            gap = w.start - cur[-1].end
            chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
            if len(cur) >= per_chunk or gap > max_gap or chars > max_chars:
                chunks.append(cur)
                cur = []
        cur.append(w)
        if re.search(r"[.!?؟,;:،]$", w.text):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(scenes: list[Scene], style: CaptionStyle, width: int, height: int, language: str,
              total_duration: float, emphasis: bool = True) -> str:
    vertical = height > width
    arabic = language == "ar"
    font = style.font_arabic if arabic else style.font
    size = int(height * style.size_ratio * (1.0 if vertical else 1.25) * (1.05 if arabic else 1.0))
    margin_v = int(height * (0.30 if vertical else 0.075))
    align = 2
    border_style = 3 if style.box else 1
    back = style.outline if style.box else "&H80000000"
    outline = max(6, int(size * 0.18)) if style.box else style.outline_px * height / 1920
    shadow = style.shadow_px * height / 1920
    bold = -1
    emph_size = int(size * 1.35)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{style.primary},{style.highlight},{style.outline},{back},{bold},0,0,0,100,100,{1 if not arabic else 0},0,{border_style},{outline:.1f},{shadow:.1f},{align},{int(width * 0.08)},{int(width * 0.08)},{margin_v},1
Style: Emph,{font},{emph_size},{style.highlight},{style.primary},&H00000000,&H80000000,-1,0,0,0,100,100,{0 if arabic else 2},0,1,{max(4.0, outline * 1.2):.1f},{max(2.0, shadow):.1f},8,{int(width * 0.06)},{int(width * 0.06)},{int(height * (0.12 if vertical else 0.08))},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    words = all_words(scenes)
    chunks = chunk_words(words, style.words_per_chunk, max_chars=22 if vertical else 42)
    for ci, chunk in enumerate(chunks):
        chunk_start = chunk[0].start
        next_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else total_duration
        chunk_end = min(next_start, chunk[-1].end + 0.6)
        texts = [w.text.upper() if style.uppercase and not arabic else w.text for w in chunk]
        texts = [_esc(t) for t in texts]
        # one event per active word so the highlight follows the voice
        for wi, w in enumerate(chunk):
            start = chunk_start if wi == 0 else w.start
            end = chunk[wi + 1].start if wi + 1 < len(chunk) else chunk_end
            if end - start < 0.02:
                continue
            parts = []
            for k, t in enumerate(texts):
                if k == wi and style.highlight != style.primary:
                    pop = r"\fscx112\fscy112\t(0,90,\fscx100\fscy100)" if style.pop else ""
                    parts.append(r"{\c" + style.highlight + pop + "}" + t + r"{\r}")
                else:
                    parts.append(t)
            intro = r"{\fad(60,0)}" if wi == 0 else ""
            if wi == 0 and style.pop:
                intro = r"{\fscx85\fscy85\t(0,80,\fscx100\fscy100)}"
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{intro}{' '.join(parts)}")

    if emphasis:
        for s in scenes:
            if s.on_screen_text:
                txt = _esc(s.on_screen_text.upper() if not arabic else s.on_screen_text)
                end = s.start + min(s.duration, 2.8)
                anim = r"{\fad(150,250)\fscx70\fscy70\t(0,180,\fscx100\fscy100)}"
                lines.append(f"Dialogue: 1,{_ts(s.start + 0.05)},{_ts(end)},Emph,,0,0,0,,{anim}{txt}")
    return header + "\n".join(lines) + "\n"


def build_srt(scenes: list[Scene], max_words: int = 8) -> str:
    words = all_words(scenes)
    chunks = chunk_words(words, max_words, max_chars=48, max_gap=0.8)
    out = []
    for i, c in enumerate(chunks, 1):
        out.append(f"{i}\n{_srt_ts(c[0].start)} --> {_srt_ts(c[-1].end + 0.2)}\n{' '.join(w.text for w in c)}\n")
    return "\n".join(out)


def write_captions(path_ass: Path, path_srt: Path, scenes, style, width, height, language, total) -> None:
    path_ass.write_text(build_ass(scenes, style, width, height, language, total), encoding="utf-8")
    path_srt.write_text(build_srt(scenes), encoding="utf-8")
