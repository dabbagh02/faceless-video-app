"""Niche templates, art styles, caption styles, voices and output formats.

A niche bundles everything that makes a faceless channel feel consistent:
narration tone, the art style every scene image is drawn in, colour palette,
music mood, caption style and default voice.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VideoFormat:
    key: str
    label: str
    width: int
    height: int
    default_seconds: int
    max_seconds: int

    @property
    def vertical(self) -> bool:
        return self.height > self.width


FORMATS: dict[str, VideoFormat] = {
    "short": VideoFormat("short", "YouTube Short (9:16, ≤60s)", 1080, 1920, 50, 60),
    "long": VideoFormat("long", "YouTube video (16:9)", 1920, 1080, 300, 1800),
}


@dataclass(frozen=True)
class ArtStyle:
    key: str
    label: str
    prompt: str  # appended to every scene image prompt
    grade: dict = field(default_factory=dict)  # ffmpeg eq params


ART_STYLES: dict[str, ArtStyle] = {
    "cinematic": ArtStyle("cinematic", "Cinematic photo",
                          "cinematic film still, dramatic lighting, shallow depth of field, 35mm, highly detailed",
                          {"contrast": 1.08, "saturation": 1.05}),
    "dark_fantasy": ArtStyle("dark_fantasy", "Dark fantasy",
                             "dark fantasy digital painting, moody fog, volumetric light, eerie atmosphere, highly detailed",
                             {"contrast": 1.12, "saturation": 0.85, "gamma": 0.95}),
    "anime": ArtStyle("anime", "Anime",
                      "anime key visual, vibrant colors, studio quality, detailed background art",
                      {"contrast": 1.04, "saturation": 1.15}),
    "comic": ArtStyle("comic", "Comic book",
                      "comic book illustration, bold ink lines, halftone shading, dynamic composition",
                      {"contrast": 1.1, "saturation": 1.1}),
    "watercolor": ArtStyle("watercolor", "Watercolor",
                           "soft watercolor painting, textured paper, gentle pastel palette",
                           {"contrast": 1.0, "saturation": 1.0}),
    "oil_painting": ArtStyle("oil_painting", "Classical oil painting",
                             "classical oil painting, renaissance style, rich textures, museum quality",
                             {"contrast": 1.06, "saturation": 0.95}),
    "3d_render": ArtStyle("3d_render", "3D render",
                          "3d render, octane, pixar style lighting, clean, highly detailed",
                          {"contrast": 1.05, "saturation": 1.1}),
    "documentary": ArtStyle("documentary", "Documentary photo",
                            "realistic documentary photograph, natural light, national geographic style",
                            {"contrast": 1.04, "saturation": 1.0}),
}


@dataclass(frozen=True)
class CaptionStyle:
    key: str
    label: str
    font: str
    font_arabic: str
    size_ratio: float  # font size relative to video height
    primary: str  # ASS colour &HBBGGRR
    highlight: str
    outline: str
    outline_px: float
    shadow_px: float
    words_per_chunk: int
    uppercase: bool
    box: bool = False  # opaque box behind text
    pop: bool = True  # scale "pop" on the active word


# ASS colours are &HAABBGGRR
CAPTION_STYLES: dict[str, CaptionStyle] = {
    "bold_pop": CaptionStyle("bold_pop", "Bold pop (yellow highlight)", "Montserrat Black", "Noto Sans Arabic Black",
                             0.052, "&H00FFFFFF", "&H0000E5FF", "&H00000000", 7, 3, 3, True),
    "hormozi": CaptionStyle("hormozi", "Hormozi (green highlight)", "Anton", "Noto Sans Arabic Black",
                            0.062, "&H00FFFFFF", "&H0033FF66", "&H00000000", 8, 0, 2, True),
    "clean": CaptionStyle("clean", "Clean subtitle (box)", "Montserrat ExtraBold", "Noto Sans Arabic Bold",
                          0.040, "&H00FFFFFF", "&H0000D7FF", "&H96000000", 0, 0, 6, False, box=True, pop=False),
    "neon": CaptionStyle("neon", "Neon glow", "Montserrat Black", "Noto Sans Arabic Black",
                         0.050, "&H00FFFFFF", "&H00FF55FF", "&H00802080", 5, 6, 3, True),
    "minimal": CaptionStyle("minimal", "Minimal", "Montserrat SemiBold", "Noto Sans Arabic Bold",
                            0.036, "&H00FFFFFF", "&H00FFFFFF", "&H00000000", 3, 2, 5, False, pop=False),
}


@dataclass(frozen=True)
class Voice:
    key: str
    label: str
    language: str  # "en" | "ar" | ...
    edge: str  # Microsoft Edge neural voice id
    elevenlabs: str  # ElevenLabs voice id
    espeak: str  # offline espeak-ng voice


VOICES: dict[str, Voice] = {
    "en_male_deep": Voice("en_male_deep", "English – male, deep narrator", "en",
                          "en-US-ChristopherNeural", "pNInz6obpgDQGcFmaJgB", "en-us+m3"),
    "en_male_story": Voice("en_male_story", "English – male, storyteller", "en",
                           "en-US-AndrewMultilingualNeural", "TxGEqnHWrfWFTfGW9XjX", "en-us+m1"),
    "en_female_warm": Voice("en_female_warm", "English – female, warm", "en",
                            "en-US-AvaMultilingualNeural", "21m00Tcm4TlvDq8ikWAM", "en-us+f3"),
    "en_female_news": Voice("en_female_news", "English – female, documentary", "en",
                            "en-GB-SoniaNeural", "EXAVITQu4vr4xnSDxMaL", "en-gb+f2"),
    "en_male_uk": Voice("en_male_uk", "English – male, British", "en",
                        "en-GB-RyanNeural", "onwK4e9ZLuTAKqWW03F9", "en-gb+m3"),
    "ar_male": Voice("ar_male", "Arabic – male (Hamed)", "ar",
                     "ar-SA-HamedNeural", "pNInz6obpgDQGcFmaJgB", "ar"),
    "ar_female": Voice("ar_female", "Arabic – female (Zariyah)", "ar",
                       "ar-SA-ZariyahNeural", "21m00Tcm4TlvDq8ikWAM", "ar+f3"),
    "ar_male_eg": Voice("ar_male_eg", "Arabic – male, Egyptian (Shakir)", "ar",
                        "ar-EG-ShakirNeural", "pNInz6obpgDQGcFmaJgB", "ar"),
}

LANGUAGES = {"en": "English", "ar": "العربية (Arabic)"}


@dataclass(frozen=True)
class Niche:
    key: str
    label: str
    tone: str
    art_style: str
    caption_style: str
    voice: str
    music_mood: str
    palette: tuple  # 3 RGB hex colours used for procedural art + thumbnails
    speech_rate: str = "+0%"
    sample_topics: tuple = ()


NICHES: dict[str, Niche] = {
    "scary_stories": Niche("scary_stories", "Scary stories", "suspenseful, eerie, slow-burn horror with a twist ending",
                           "dark_fantasy", "bold_pop", "en_male_deep", "dark", ("#0b0f1a", "#3a0d12", "#c21d2b"), "-5%",
                           ("The lighthouse keeper who never left", "The last train out of Blackwood",
                            "The doll that moved every night", "A voicemail from my own number")),
    "history": Niche("history", "History", "authoritative, vivid storytelling with surprising facts",
                     "oil_painting", "bold_pop", "en_male_uk", "epic", ("#1b130b", "#6b4a25", "#e0b062"), "+0%",
                     ("The fall of Constantinople", "How the Library of Alexandria was lost",
                      "The real story of the Trojan Horse", "Why the Roman Empire split in two")),
    "motivation": Niche("motivation", "Motivation", "powerful, energetic, second-person, punchy sentences",
                        "cinematic", "hormozi", "en_male_story", "uplifting", ("#0a0a0a", "#1f2a44", "#f5b301"), "+5%",
                        ("Discipline beats motivation", "Why you should start before you're ready",
                         "The 1% rule that changes everything", "Stop waiting for the perfect moment")),
    "facts": Niche("facts", "Mind-blowing facts", "fast, curious, playful, each sentence delivers a new fact",
                   "3d_render", "bold_pop", "en_female_warm", "playful", ("#081a2e", "#0e5e8a", "#33e1ff"), "+8%",
                   ("Facts about the ocean that sound fake", "Things your brain does without telling you",
                    "Animals with real superpowers", "Space facts that will keep you up at night")),
    "true_crime": Niche("true_crime", "True crime", "serious, investigative, factual and respectful to victims",
                        "documentary", "clean", "en_female_news", "tense", ("#0d0d0f", "#2b2f36", "#9aa5b1"), "-3%",
                        ("The heist nobody solved", "The detective who cracked a 30-year-old case",
                         "The perfect alibi that fell apart", "The great museum art theft")),
    "science": Niche("science", "Science explained", "clear, enthusiastic teacher, uses simple analogies",
                     "3d_render", "clean", "en_female_warm", "ambient", ("#06121f", "#14375e", "#5ad1ff"), "+3%",
                     ("How black holes actually work", "Why the sky is blue", "What happens when you sleep",
                      "How vaccines train your body")),
    "finance": Niche("finance", "Money & finance", "practical, confident, actionable, no hype",
                     "cinematic", "hormozi", "en_male_story", "uplifting", ("#07140d", "#0f4d2c", "#3ddc84"), "+4%",
                     ("Compound interest explained simply", "Five money habits of wealthy people",
                      "Why most people never build wealth", "How inflation quietly steals your money")),
    "mythology": Niche("mythology", "Mythology", "epic, mythic, dramatic narration like an ancient bard",
                       "oil_painting", "neon", "en_male_deep", "epic", ("#120a1f", "#3d1f6b", "#d7a8ff"), "-2%",
                       ("Why Zeus feared Prometheus", "The Norse end of the world: Ragnarok",
                        "Medusa was not the monster", "Anubis and the weighing of the heart")),
    "stoicism": Niche("stoicism", "Stoic philosophy", "calm, wise, reflective, quotes and lessons",
                      "oil_painting", "minimal", "en_male_uk", "ambient", ("#111111", "#3a3530", "#d9c7a7"), "-4%",
                      ("Marcus Aurelius on handling difficult people", "The Stoic secret to inner peace",
                       "What Seneca knew about time", "Epictetus: control what you can")),
    "kids_stories": Niche("kids_stories", "Kids bedtime stories", "gentle, warm, whimsical, simple words",
                          "watercolor", "clean", "en_female_warm", "playful", ("#14213d", "#5c7aea", "#ffd6a5"), "-6%",
                          ("The little star who was afraid of the dark", "The fox who learned to share",
                           "A dragon who loved books", "The moon's secret garden")),
    "arabic_stories": Niche("arabic_stories", "قصص عربية (Arabic stories)", "سرد قصصي مشوّق بأسلوب الحكواتي",
                            "cinematic", "bold_pop", "ar_male", "epic", ("#1a0f05", "#6b3a12", "#f2b544"), "+0%",
                            ("قصة صلاح الدين وتحرير القدس", "أسرار الأهرامات التي لا يعرفها أحد",
                             "حكاية ابن بطوطة ورحلته حول العالم", "لغز مدينة إرم ذات العماد")),
}

MUSIC_MOODS = ("dark", "epic", "uplifting", "playful", "tense", "ambient")


def niche(key: str) -> Niche:
    return NICHES.get(key) or NICHES["facts"]
