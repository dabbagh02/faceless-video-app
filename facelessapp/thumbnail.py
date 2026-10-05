"""YouTube thumbnail (1280x720) with bold, high-contrast text."""
from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .config import FONTS_DIR
from .visuals import VIDEO_EXT

TW, TH = 1280, 720


def _frame_from_video(path: str) -> Image.Image:
    import subprocess
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", path, "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(out))


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def make_thumbnail(visual_path: str, text: str, accent: str, out: Path, language: str = "en") -> Path:
    if Path(visual_path).suffix.lower() in VIDEO_EXT:
        img = _frame_from_video(visual_path)
    else:
        img = Image.open(visual_path)
    img = ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), (TW, TH), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.2)

    # dark gradient on the text side for readability
    arabic = language == "ar"
    grad = np.linspace(0.78, 0.0, TW, dtype=np.float32)
    if arabic:
        grad = grad[::-1]
    shade = Image.fromarray((np.tile(grad, (TH, 1)) * 255).astype(np.uint8))
    img = Image.composite(Image.new("RGB", (TW, TH)), img, shade)

    font_file = FONTS_DIR / ("NotoSansArabic-Black.ttf" if arabic else "Anton-Regular.ttf")
    text = text.strip() if arabic else text.strip().upper()
    lines = textwrap.wrap(text, width=12 if not arabic else 16)[:3] or ["WATCH"]
    size = 150 if len(lines) == 1 else 128 if len(lines) == 2 else 104
    font = ImageFont.truetype(str(font_file), size)
    draw = ImageDraw.Draw(img)
    while max(draw.textlength(l, font=font) for l in lines) > TW * 0.64 and size > 50:
        size -= 6
        font = ImageFont.truetype(str(font_file), size)
    line_h = int(size * (1.15 if not arabic else 1.5))
    y = (TH - line_h * len(lines)) // 2
    accent_rgb = _hex(accent)
    shadow = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    positions = []
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x = TW - 84 - w if arabic else 84
        positions.append((x, y + i * line_h, line, i))
        sd.text((x + 8, y + i * line_h + 10), line, font=font, fill=(0, 0, 0, 200))
    img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
    draw = ImageDraw.Draw(img)
    for x, yy, line, i in positions:
        fill = accent_rgb if i == len(lines) - 1 and len(lines) > 1 else (255, 255, 255)
        draw.text((x, yy), line, font=font, fill=fill, stroke_width=max(4, size // 22), stroke_fill=(0, 0, 0))
    # accent bar
    bx = TW - 56 if arabic else 44
    draw.rectangle([bx, y + 10, bx + 12, y + line_h * len(lines) - 10], fill=accent_rgb)
    img.save(out, quality=92)
    return out
