"""Runtime settings, loaded from environment variables and an optional `.env` file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS_DIR = ASSETS / "fonts"
MUSIC_DIR = ASSETS / "music"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE per line). Existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    # Claude (script writing)
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-opus-5-5"))
    claude_effort: str = field(default_factory=lambda: _env("CLAUDE_EFFORT", "medium"))

    # Voice-over
    tts_engine: str = field(default_factory=lambda: _env("TTS_ENGINE", "auto"))  # auto|edge|elevenlabs|espeak
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))

    # Visuals
    visual_source: str = field(default_factory=lambda: _env("VISUAL_SOURCE", "auto"))  # auto|ai|stock|procedural|local
    pexels_api_key: str = field(default_factory=lambda: _env("PEXELS_API_KEY"))
    pixabay_api_key: str = field(default_factory=lambda: _env("PIXABAY_API_KEY"))
    local_media_dir: str = field(default_factory=lambda: _env("LOCAL_MEDIA_DIR"))

    # Output / encoding
    output_dir: Path = field(default_factory=lambda: Path(_env("OUTPUT_DIR", str(ROOT / "output"))))
    cache_dir: Path = field(default_factory=lambda: Path(_env("CACHE_DIR", str(ROOT / ".cache"))))
    x264_preset: str = field(default_factory=lambda: _env("X264_PRESET", "fast"))
    crf: int = field(default_factory=lambda: int(_env("VIDEO_CRF", "18")))
    fps: int = field(default_factory=lambda: int(_env("VIDEO_FPS", "30")))
    workers: int = field(default_factory=lambda: int(_env("WORKERS", "2")))

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def has_claude(self) -> bool:
        return bool(self.anthropic_api_key)


def get_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        if v is not None:
            setattr(s, k, Path(v) if k in ("output_dir", "cache_dir") else v)
    s.__post_init__()
    return s
