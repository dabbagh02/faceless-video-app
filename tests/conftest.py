import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "LOCAL_MEDIA_DIR"):
        monkeypatch.delenv(k, raising=False)
    from facelessapp.config import get_settings
    return get_settings(output_dir=tmp_path / "out", cache_dir=tmp_path / "cache", tts_engine="espeak",
                        visual_source="procedural", x264_preset="ultrafast", anthropic_api_key="")
