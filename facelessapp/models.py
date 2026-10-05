"""Plain data structures shared by every pipeline stage."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Scene:
    narration: str
    image_prompt: str
    search_query: str  # short stock-footage query (English)
    on_screen_text: str = ""  # optional big text overlay (keep short)
    # filled in by later stages
    audio_path: Optional[str] = None
    start: float = 0.0
    duration: float = 0.0
    words: list = field(default_factory=list)  # list[WordTiming]
    visual_path: Optional[str] = None
    visual_kind: str = "image"  # image | video


@dataclass
class WordTiming:
    text: str
    start: float
    end: float


@dataclass
class Script:
    title: str
    hook: str
    scenes: list  # list[Scene]
    description: str
    tags: list
    thumbnail_text: str
    chapter_titles: list = field(default_factory=list)  # one per scene ("" = no new chapter)
    language: str = "en"

    @property
    def full_text(self) -> str:
        return " ".join(s.narration for s in self.scenes)

    def to_dict(self) -> dict:
        d = asdict(self)
        for s in d["scenes"]:
            s.pop("words", None)
        return d


@dataclass
class VideoRequest:
    topic: str
    niche: str = "facts"
    format: str = "short"  # short | long
    duration: int = 0  # target seconds (0 = format default)
    language: str = ""  # "" = voice language
    voice: str = ""  # "" = niche default
    art_style: str = ""
    caption_style: str = ""
    visual_source: str = ""  # "" = settings default
    music: bool = True
    music_volume: float = 0.12
    custom_script: str = ""  # optional: user-provided narration, Claude only splits it
    seed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VideoResult:
    video_path: Path
    thumbnail_path: Path
    metadata_path: Path
    srt_path: Path
    duration: float
    script: Script
    report: dict = field(default_factory=dict)
