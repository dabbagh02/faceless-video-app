"""Scene visuals.

Providers (tried in order, each falls back to the next):
- ai:         AI-generated images in the niche's art style (Pollinations, free, no key)
- pexels:     stock videos / photos (free API key)
- pixabay:    stock videos / photos (free API key)
- local:      your own folder of images/videos, matched by filename keywords
- procedural: offline generative art (always works; used for tests and as a last resort)
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
import urllib.parse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .config import Settings
from .models import Scene

log = logging.getLogger(__name__)
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}


def _hash(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def _download(url: str, dest: Path, headers: dict | None = None, timeout: float = 90) -> Path:
    import httpx
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, headers=headers or {}, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    if tmp.stat().st_size < 2000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"download too small: {url}")
    tmp.rename(dest)
    return dest


def _verify_image(path: Path) -> None:
    with Image.open(path) as im:
        im.verify()


class PollinationsProvider:
    """Free AI image generation endpoint (no key)."""
    name = "ai"

    def __init__(self, settings: Settings):
        self.cache = settings.cache_dir / "ai"
        self.cache.mkdir(parents=True, exist_ok=True)

    def fetch(self, scene: Scene, width: int, height: int, seed: int) -> tuple[Path, str]:
        prompt = scene.image_prompt + ", no text, no watermark"
        dest = self.cache / f"{_hash(prompt, width, height, seed)}.jpg"
        if not dest.exists():
            q = urllib.parse.quote(prompt[:900])
            url = (f"https://image.pollinations.ai/prompt/{q}?width={width}&height={height}"
                   f"&seed={seed}&nologo=true&model=flux")
            _download(url, dest, timeout=180)
            _verify_image(dest)
        return dest, "image"


class PexelsProvider:
    name = "pexels"

    def __init__(self, settings: Settings):
        self.key = settings.pexels_api_key
        self.cache = settings.cache_dir / "pexels"
        self.cache.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        return bool(self.key)

    def fetch(self, scene: Scene, width: int, height: int, seed: int) -> tuple[Path, str]:
        import httpx
        orientation = "portrait" if height > width else "landscape"
        h = {"Authorization": self.key}
        r = httpx.get("https://api.pexels.com/videos/search", headers=h, timeout=30,
                      params={"query": scene.search_query, "orientation": orientation, "per_page": 15})
        r.raise_for_status()
        videos = r.json().get("videos", [])
        rng = random.Random(seed)
        rng.shuffle(videos)
        for v in videos:
            files = [f for f in v.get("video_files", []) if f.get("width") and f.get("height")
                     and f.get("file_type") == "video/mp4"]
            # smallest file that still covers the output resolution
            good = sorted([f for f in files if min(f["width"], f["height"]) >= min(width, height) * 0.9],
                          key=lambda f: f["width"] * f["height"])
            if good and v.get("duration", 0) >= 3:
                dest = self.cache / f"v{v['id']}_{good[0]['width']}.mp4"
                if not dest.exists():
                    _download(good[0]["link"], dest)
                return dest, "video"
        r = httpx.get("https://api.pexels.com/v1/search", headers=h, timeout=30,
                      params={"query": scene.search_query, "orientation": orientation, "per_page": 15})
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            raise RuntimeError(f"no pexels results for {scene.search_query!r}")
        p = rng.choice(photos)
        dest = self.cache / f"p{p['id']}.jpg"
        if not dest.exists():
            _download(p["src"]["original"] + "?auto=compress&w=2400", dest)
        return dest, "image"


class PixabayProvider:
    name = "pixabay"

    def __init__(self, settings: Settings):
        self.key = settings.pixabay_api_key
        self.cache = settings.cache_dir / "pixabay"
        self.cache.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        return bool(self.key)

    def fetch(self, scene: Scene, width: int, height: int, seed: int) -> tuple[Path, str]:
        import httpx
        rng = random.Random(seed)
        r = httpx.get("https://pixabay.com/api/videos/", timeout=30,
                      params={"key": self.key, "q": scene.search_query[:100], "per_page": 20, "safesearch": "true"})
        r.raise_for_status()
        hits = r.json().get("hits", [])
        rng.shuffle(hits)
        for hit in hits:
            for size in ("large", "medium"):
                f = hit.get("videos", {}).get(size) or {}
                if f.get("url") and min(f.get("width", 0), f.get("height", 0)) >= min(width, height) * 0.6:
                    dest = self.cache / f"v{hit['id']}_{size}.mp4"
                    if not dest.exists():
                        _download(f["url"], dest)
                    return dest, "video"
        r = httpx.get("https://pixabay.com/api/", timeout=30,
                      params={"key": self.key, "q": scene.search_query[:100], "image_type": "photo",
                              "orientation": "vertical" if height > width else "horizontal", "per_page": 20})
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            raise RuntimeError(f"no pixabay results for {scene.search_query!r}")
        hit = rng.choice(hits)
        dest = self.cache / f"p{hit['id']}.jpg"
        if not dest.exists():
            _download(hit["largeImageURL"], dest)
        return dest, "image"


class LocalProvider:
    name = "local"

    def __init__(self, settings: Settings):
        self.dir = Path(settings.local_media_dir) if settings.local_media_dir else None

    def available(self) -> bool:
        return bool(self.dir and self.dir.is_dir())

    def fetch(self, scene: Scene, width: int, height: int, seed: int) -> tuple[Path, str]:
        files = [p for p in self.dir.rglob("*") if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT]
        if not files:
            raise RuntimeError("local media folder is empty")
        words = set(scene.search_query.lower().split()) | set(scene.image_prompt.lower().split()[:12])
        scored = sorted(files, key=lambda p: (-len(words & set(p.stem.lower().replace("_", " ").replace("-", " ").split())),
                                              _hash(p, seed)))
        best = scored[0]
        return best, "video" if best.suffix.lower() in VIDEO_EXT else "image"


# --------------------------------------------------------------------------- procedural art

def _hex(c: str) -> np.ndarray:
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _fractal_noise(rng: np.random.Generator, w: int, h: int, octaves: int = 5) -> np.ndarray:
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = 2 ** (o + 2)
        grid = rng.random((cells, max(2, int(cells * w / h)))).astype(np.float32)
        layer = np.asarray(Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                           np.float32) / 255
        out += layer * amp
        total += amp
        amp *= 0.5
    out /= total
    return (out - out.min()) / (np.ptp(out) + 1e-6)


def procedural_art(width: int, height: int, palette: tuple, seed: int, text_hint: str = "") -> Image.Image:
    """Layered generative 'matte painting': gradient sky, nebula fog, glow, bokeh and a silhouette layer."""
    rng = np.random.default_rng(seed)
    prng = random.Random(seed)
    c0, c1, c2 = (_hex(c) for c in palette)
    # work at a lower resolution then upscale — everything here is soft anyway
    sw, sh = max(64, width // 3), max(64, height // 3)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    ang = prng.uniform(0, math.pi)
    g = (np.cos(ang) * xx / sw + np.sin(ang) * yy / sh)
    g = (g - g.min()) / (np.ptp(g) + 1e-6)
    img = c0[None, None] * (1 - g[..., None]) + c1[None, None] * g[..., None]

    fog = _fractal_noise(rng, sw, sh) ** 2.2
    img = img * (1 - fog[..., None] * 0.55) + c2[None, None] * fog[..., None] * 0.55

    # glow (sun / moon / light source)
    gx, gy = prng.uniform(0.2, 0.8) * sw, prng.uniform(0.15, 0.55) * sh
    d = np.sqrt((xx - gx) ** 2 + (yy - gy) ** 2) / max(sw, sh)
    glow = np.exp(-(d / prng.uniform(0.12, 0.3)) ** 2)
    tint = (c2 * 0.6 + 255 * 0.4)
    img = img + tint[None, None] * glow[..., None] * 0.65

    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((width, height), Image.BICUBIC)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # bokeh / stars
    for _ in range(prng.randint(25, 70)):
        r = prng.uniform(0.003, 0.025) * width
        x, y = prng.uniform(0, width), prng.uniform(0, height * 0.75)
        col = tuple(int(v) for v in (c2 * 0.5 + 255 * 0.5)) + (prng.randint(25, 90),)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(width * 0.004))
    base = Image.alpha_composite(base.convert("RGBA"), layer)

    # silhouette foreground
    sil = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sil)
    dark = tuple(int(v * 0.25) for v in c0) + (255,)
    kind = prng.choice(["mountains", "city", "forest", "waves", "hills", "none"])
    horizon = prng.uniform(0.62, 0.8) * height
    if kind in ("mountains", "hills"):
        for layer_i, (shade, amp) in enumerate([(0.55, 0.22), (0.3, 0.14), (0.0, 0.08)]):
            n = 9 if kind == "mountains" else 4
            pts = [(0, height)]
            for i in range(n + 1):
                x = width * i / n
                y = horizon + layer_i * height * 0.06 - prng.uniform(0.2, 1) * amp * height * (0.6 if kind == "hills" else 1)
                pts.append((x, y))
            pts.append((width, height))
            col = tuple(int(dark[k] + (c1[k] * 0.5 - dark[k]) * shade) for k in range(3)) + (255,)
            sd.polygon(pts, fill=col)
        if kind == "hills":
            sil = sil.filter(ImageFilter.GaussianBlur(2))
    elif kind == "city":
        x = 0.0
        while x < width:
            bw = prng.uniform(0.04, 0.11) * width
            bh = prng.uniform(0.08, 0.35) * height
            sd.rectangle([x, horizon + height * 0.12 - bh, x + bw, height], fill=dark)
            for wy in range(int(horizon + height * 0.14 - bh), int(height), max(8, int(height * 0.02))):
                for wx in range(int(x + 4), int(x + bw - 6), max(8, int(width * 0.025))):
                    if prng.random() < 0.18:
                        sd.rectangle([wx, wy, wx + 3, wy + 5], fill=tuple(int(v) for v in c2) + (200,))
            x += bw + prng.uniform(0, 0.01) * width
    elif kind == "forest":
        for _ in range(prng.randint(14, 30)):
            tx = prng.uniform(0, width)
            th = prng.uniform(0.15, 0.4) * height
            tw = th * prng.uniform(0.25, 0.4)
            base_y = horizon + prng.uniform(0.05, 0.12) * height
            sd.polygon([(tx, base_y - th), (tx - tw / 2, base_y), (tx + tw / 2, base_y)], fill=dark)
        sd.rectangle([0, horizon + 0.04 * height, width, height], fill=dark)
    elif kind == "waves":
        for i in range(5):
            y0 = horizon + i * height * 0.05
            pts = [(0, height)] + [(x, y0 + math.sin(x / width * math.pi * prng.uniform(2, 5) + i) * height * 0.012)
                                   for x in np.linspace(0, width, 40)] + [(width, height)]
            shade = 0.5 - i * 0.1
            sd.polygon(pts, fill=tuple(int(dark[k] + (c2[k] * 0.4 - dark[k]) * max(0, shade)) for k in range(3)) + (255,))
    base = Image.alpha_composite(base, sil)

    # subtle grain baked in so flat areas don't band after compression
    arr = np.asarray(base.convert("RGB"), np.float32)
    arr += rng.normal(0, 3.0, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


class ProceduralProvider:
    name = "procedural"

    def __init__(self, settings: Settings, palette: tuple):
        self.cache = settings.cache_dir / "procedural"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.palette = palette

    def fetch(self, scene: Scene, width: int, height: int, seed: int) -> tuple[Path, str]:
        dest = self.cache / f"{_hash(self.palette, width, height, seed, scene.image_prompt)}.jpg"
        if not dest.exists():
            img = procedural_art(width, height, self.palette, seed, scene.search_query)
            img.save(dest, quality=93)
        return dest, "image"


def build_chain(settings: Settings, source: str, palette: tuple) -> list:
    source = (source or settings.visual_source or "auto").lower()
    ai = PollinationsProvider(settings)
    pexels, pixabay, local = PexelsProvider(settings), PixabayProvider(settings), LocalProvider(settings)
    procedural = ProceduralProvider(settings, palette)
    stock = [p for p in (pexels, pixabay) if p.available()]
    chains = {
        "ai": [ai] + stock,
        "stock": stock + [ai],
        "local": ([local] if local.available() else []) + stock,
        "procedural": [],
        "auto": ([local] if local.available() else []) + [ai] + stock,
    }
    return chains.get(source, chains["auto"]) + [procedural]


def fetch_visuals(settings: Settings, scenes: list[Scene], width: int, height: int, source: str,
                  palette: tuple, seed: int = 0, on_progress=None) -> dict:
    """Fill scene.visual_path/visual_kind. Returns a {provider: count} usage summary."""
    chain = build_chain(settings, source, palette)
    dead: set[str] = set()  # providers that failed with a network error — skip for the rest of the job
    usage: dict[str, int] = {}
    # ask for images a bit larger than the frame so Ken Burns moves don't reveal edges
    iw, ih = int(width * 1.2) // 8 * 8, int(height * 1.2) // 8 * 8
    for i, scene in enumerate(scenes):
        for provider in chain:
            if provider.name in dead:
                continue
            try:
                path, kind = provider.fetch(scene, iw, ih, seed * 1000 + i)
                scene.visual_path, scene.visual_kind = str(path), kind
                usage[provider.name] = usage.get(provider.name, 0) + 1
                break
            except Exception as e:
                log.warning("visual provider %s failed for scene %d: %s", provider.name, i, e)
                if provider.name != "procedural" and _is_network_error(e):
                    dead.add(provider.name)
        if on_progress:
            on_progress(i + 1, len(scenes))
    return usage


def _is_network_error(e: Exception) -> bool:
    try:
        import httpx
        if isinstance(e, (httpx.ConnectError, httpx.ProxyError, httpx.ConnectTimeout)):
            return True
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403, 429):
            return True
    except ImportError:
        pass
    return False
