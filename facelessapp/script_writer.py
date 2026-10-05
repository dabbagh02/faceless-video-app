"""Script generation.

`ClaudeScriptWriter` asks Claude for a complete YouTube-ready script (hook, scenes
with narration + image prompts, title, description, tags, thumbnail text) using
structured JSON output. `OfflineScriptWriter` builds a deterministic script from
templates so the whole pipeline can run (and be tested) without an API key.
"""
from __future__ import annotations

import json
import logging
import random
import re

from .config import Settings
from .models import Scene, Script, VideoRequest
from .presets import ART_STYLES, FORMATS, VOICES, niche as get_niche

log = logging.getLogger(__name__)

WORDS_PER_SECOND = {"en": 2.5, "ar": 2.0}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "search_query": {"type": "string"},
                    "on_screen_text": {"type": "string"},
                    "chapter_title": {"type": "string"},
                },
                "required": ["narration", "image_prompt", "search_query", "on_screen_text", "chapter_title"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string"},
    },
    "required": ["title", "hook", "scenes", "description", "tags", "thumbnail_text"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a senior scriptwriter for top-performing faceless YouTube channels.
You write narration that is read aloud by a voice-over over AI-generated or stock visuals, with
animated captions. Your scripts maximise retention:
- The first sentence is a scroll-stopping hook (curiosity gap, bold claim or question). No greetings,
  no "in this video", no "welcome back".
- Short, spoken-style sentences. Concrete details, vivid verbs, open loops that pay off later.
- Every scene moves the story forward; end with a satisfying payoff and a short natural call to
  action (subscribe/comment) only at the very end.
- Narration must be plain spoken text only: no emojis, no stage directions, no markdown, no
  speaker labels, numbers written the way they should be spoken.
- Stay factually accurate for non-fiction; never invent quotes attributed to real people.

For each scene also write:
- image_prompt: a detailed English prompt for an AI image generator describing ONE striking,
  well-composed shot for that moment (subject, setting, lighting, camera angle). Never include
  text, captions, logos or watermarks in the image. Keep characters visually consistent across scenes.
- search_query: 2-4 English keywords to find matching stock footage.
- on_screen_text: optional 1-4 word emphasis text (or empty string). Use it sparingly.
- chapter_title: for long videos, a 2-5 word chapter name when this scene starts a new chapter,
  otherwise an empty string. For Shorts always an empty string.

Metadata: an irresistible but honest YouTube title (under 70 characters), an SEO description
(2-3 short paragraphs + 3-5 hashtags at the end), 10-15 tags, and 2-5 word thumbnail_text."""


def target_words(req: VideoRequest, language: str) -> tuple[int, int]:
    fmt = FORMATS[req.format]
    seconds = req.duration or fmt.default_seconds
    seconds = max(15, min(seconds, fmt.max_seconds))
    words = int(seconds * WORDS_PER_SECOND.get(language, 2.4))
    scene_seconds = 5.0 if fmt.vertical else 9.0
    scenes = max(4, round(seconds / scene_seconds))
    return words, scenes


def resolve_language(req: VideoRequest) -> str:
    if req.language:
        return req.language
    voice = VOICES.get(req.voice or get_niche(req.niche).voice)
    return voice.language if voice else "en"


def build_user_prompt(req: VideoRequest, language: str) -> str:
    n = get_niche(req.niche)
    fmt = FORMATS[req.format]
    style = ART_STYLES.get(req.art_style or n.art_style, ART_STYLES["cinematic"])
    words, scenes = target_words(req, language)
    lang_name = {"en": "English", "ar": "Modern Standard Arabic (فصحى)"}.get(language, language)
    parts = [
        f"Topic: {req.topic}",
        f"Channel niche: {n.label}. Tone: {n.tone}.",
        f"Format: {fmt.label}. Target length: about {words} spoken words in total, split into about {scenes} scenes.",
        f"Write the narration, title, description, tags and thumbnail_text in {lang_name}. "
        "image_prompt and search_query must always be in English.",
        f"Visual style for every image_prompt: {style.prompt}.",
    ]
    if fmt.vertical:
        parts.append("This is a vertical Short: hook within the first 2 seconds, fast pacing, a loop-friendly ending.")
    else:
        parts.append("This is a long-form video: give it 3-6 chapters (first scene must have a chapter_title).")
    if req.custom_script.strip():
        parts.append("Use this narration VERBATIM, only split it into scenes and write the other fields:\n"
                     + req.custom_script.strip())
    return "\n".join(parts)


def _clean_narration(text: str) -> str:
    text = re.sub(r"[*_#`]+", "", text)
    text = re.sub(r"\[[^\]]*\]|\([^)]*(pause|music|sfx)[^)]*\)", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def script_from_dict(data: dict, language: str, vertical: bool) -> Script:
    scenes, chapters = [], []
    for raw in data.get("scenes", []):
        narration = _clean_narration(str(raw.get("narration", "")))
        if not narration:
            continue
        scenes.append(Scene(
            narration=narration,
            image_prompt=str(raw.get("image_prompt", "")).strip() or narration[:200],
            search_query=str(raw.get("search_query", "")).strip() or "cinematic landscape",
            on_screen_text=str(raw.get("on_screen_text", "")).strip()[:40],
        ))
        chapters.append("" if vertical else str(raw.get("chapter_title", "")).strip())
    if not scenes:
        raise ValueError("script has no scenes")
    if not vertical and chapters and not chapters[0]:
        chapters[0] = "Intro"
    tags = [str(t).strip().lstrip("#") for t in data.get("tags", []) if str(t).strip()][:20]
    return Script(
        title=str(data.get("title", "")).strip()[:100] or scenes[0].narration[:60],
        hook=str(data.get("hook", "")).strip() or scenes[0].narration,
        scenes=scenes,
        description=str(data.get("description", "")).strip(),
        tags=tags,
        thumbnail_text=str(data.get("thumbnail_text", "")).strip()[:40] or "WATCH THIS",
        chapter_titles=chapters,
        language=language,
    )


class ClaudeScriptWriter:
    """Writes scripts with Claude via the official Anthropic SDK."""

    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None, max_retries=3)
        self.client = client

    def _request(self, prompt: str, use_fallbacks: bool) -> str:
        kwargs = dict(
            model=self.settings.claude_model,
            max_tokens=32000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": self.settings.claude_effort,
                           "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA}},
        )
        if use_fallbacks:
            # Server-side refusal fallback: if the model declines, the API reroutes in-call.
            stream_ctx = self.client.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            stream_ctx = self.client.messages.stream(**kwargs)
        with stream_ctx as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            raise RuntimeError("Claude declined to write this script; try rephrasing the topic.")
        if message.stop_reason == "max_tokens":
            raise RuntimeError("Script was cut off (max_tokens); try a shorter duration.")
        return next(b.text for b in message.content if b.type == "text")

    def write(self, req: VideoRequest) -> Script:
        import anthropic
        language = resolve_language(req)
        prompt = build_user_prompt(req, language)
        try:
            text = self._request(prompt, use_fallbacks=True)
        except anthropic.BadRequestError as e:
            # e.g. a model/platform that does not accept the fallback beta — retry plainly.
            log.warning("Retrying without server-side fallbacks: %s", e)
            text = self._request(prompt, use_fallbacks=False)
        data = json.loads(text)
        return script_from_dict(data, language, FORMATS[req.format].vertical)


# --------------------------------------------------------------------------- offline

_EN_BANK = {
    "hook": [
        "What if everything you knew about {t} was wrong?",
        "Nobody talks about this side of {t}.",
        "This is the story of {t}, and it is stranger than you think.",
        "Stop scrolling. {T} is about to change how you see the world.",
        "There is a secret hidden inside {t}, and almost no one has noticed it.",
    ],
    "body": [
        "It started quietly, with a detail that most people simply ignored.",
        "At first, nothing about {t} seemed unusual at all.",
        "But look closer, and a very different picture begins to appear.",
        "Experts spent years trying to explain what was really going on.",
        "The numbers alone are hard to believe.",
        "And this is exactly where things get interesting.",
        "Every clue pointed in the same surprising direction.",
        "Think about that for a second.",
        "It was not luck. It was a pattern, repeated again and again.",
        "Most people never ask the obvious question.",
        "The answer had been hiding in plain sight the entire time.",
        "What happened next shocked everyone involved.",
        "Small choices, made every single day, added up to something enormous.",
        "History is full of moments like this, but this one is different.",
        "The deeper you dig into {t}, the stranger it becomes.",
        "One tiny change turned the whole story upside down.",
        "Nobody expected the ending, not even the people who lived it.",
        "And yet, the most important part is still to come.",
        "Here is the part that most people get completely wrong.",
        "It sounds impossible, but the evidence is overwhelming.",
    ],
    "outro": [
        "So the next time you hear about {t}, remember what is really going on beneath the surface.",
        "And that is the real story of {t}. Follow for more stories like this.",
        "Now you know the truth about {t}. Subscribe so you never miss the next one.",
    ],
    "queries": ["cinematic landscape", "city night", "mysterious forest", "ocean waves", "night sky stars",
                "ancient ruins", "foggy road", "sunrise mountains", "old library", "storm clouds"],
    "shots": ["wide establishing shot", "close-up detail", "low angle hero shot", "aerial view",
              "silhouette against the light", "over-the-shoulder view", "macro shot", "dramatic portrait"],
}

_AR_BANK = {
    "hook": [
        "ماذا لو كان كل ما تعرفه عن {t} خاطئاً؟",
        "لا أحد يتحدث عن هذا الجانب من {t}.",
        "هذه هي حكاية {t}، وهي أغرب مما تتخيل.",
        "توقف لحظة، فما ستسمعه عن {t} سيغير نظرتك تماماً.",
    ],
    "body": [
        "بدأ كل شيء بهدوء، بتفصيلة صغيرة تجاهلها الجميع.",
        "في البداية، لم يكن هناك ما يثير الشك.",
        "لكن عندما تقترب أكثر، تظهر صورة مختلفة تماماً.",
        "قضى الباحثون سنوات طويلة يحاولون فهم ما حدث.",
        "الأرقام وحدها يصعب تصديقها.",
        "وهنا تحديداً تبدأ القصة الحقيقية.",
        "كل الأدلة كانت تشير إلى اتجاه واحد مدهش.",
        "فكّر في هذا للحظة.",
        "لم يكن الأمر صدفة، بل كان نمطاً يتكرر مرة بعد مرة.",
        "الجواب كان مخفياً أمام أعين الجميع طوال الوقت.",
        "وما حدث بعد ذلك صدم الجميع.",
        "قرارات صغيرة كل يوم صنعت شيئاً عظيماً.",
        "كلما تعمقت في {t}، أصبحت الحكاية أغرب.",
        "تغيير واحد صغير قلب القصة رأساً على عقب.",
        "ومع ذلك، فإن أهم جزء لم يأتِ بعد.",
    ],
    "outro": [
        "والآن عرفت الحقيقة الكاملة عن {t}. اشترك حتى لا تفوتك القصة القادمة.",
        "هذه هي حكاية {t}. اكتب لنا رأيك في التعليقات وتابعنا للمزيد.",
    ],
}


class OfflineScriptWriter:
    """Template-based writer used when no Claude API key is configured (and in tests)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings

    def write(self, req: VideoRequest) -> Script:
        language = resolve_language(req)
        n = get_niche(req.niche)
        fmt = FORMATS[req.format]
        style = ART_STYLES.get(req.art_style or n.art_style, ART_STYLES["cinematic"])
        rng = random.Random(f"{req.topic}|{req.seed}|{req.niche}|{req.format}")
        total_words, n_scenes = target_words(req, language)
        bank = _AR_BANK if language == "ar" else _EN_BANK
        t = req.topic.strip().rstrip(".?!")
        fill = lambda s: s.replace("{t}", t if language == "ar" else t.lower()).replace("{T}", t)

        if req.custom_script.strip():
            sentences = re.split(r"(?<=[.!?؟])\s+", req.custom_script.strip())
        else:
            sentences = [fill(rng.choice(bank["hook"]))]
            body = bank["body"][:]
            rng.shuffle(body)
            words = len(sentences[0].split())
            outro = fill(rng.choice(bank["outro"]))
            budget = total_words - len(outro.split())
            i = 0
            while words < budget:
                s = fill(body[i % len(body)])
                if i >= len(body):
                    rng.shuffle(body)
                sentences.append(s)
                words += len(s.split())
                i += 1
            sentences.append(outro)

        # distribute sentences across scenes
        n_scenes = max(1, min(n_scenes, len(sentences)))
        per = len(sentences) / n_scenes
        groups = [sentences[round(i * per):round((i + 1) * per)] for i in range(n_scenes)]
        groups = [g for g in groups if g]

        queries = _EN_BANK["queries"]
        shots = _EN_BANK["shots"]
        scenes, chapters = [], []
        chapter_names = ["Intro", "The Beginning", "The Turning Point", "The Truth", "Conclusion"]
        for i, g in enumerate(groups):
            q = rng.choice(queries)
            scenes.append(Scene(
                narration=" ".join(g),
                image_prompt=f"{rng.choice(shots)} illustrating {req.topic}, {q}, {style.prompt}",
                search_query=q,
                on_screen_text="" if i else (t.upper()[:28] if language == "en" else t[:28]),
            ))
            if fmt.vertical:
                chapters.append("")
            else:
                idx = round(i * (len(chapter_names) - 1) / max(1, len(groups) - 1))
                prev = [c for c in chapters if c]
                name = chapter_names[idx]
                chapters.append(name if name not in prev else "")

        if language == "ar":
            title = f"{t} | القصة الكاملة"
            desc = f"اكتشف الحقيقة المذهلة وراء {t}.\n\nاشترك في القناة للمزيد من القصص.\n\n#قصص #وثائقي #تاريخ"
            thumb = " ".join(t.split()[:3])
        else:
            title = f"The Untold Story of {t}"[:70]
            desc = (f"Discover the surprising truth behind {t}.\n\n"
                    f"In this {n.label.lower()} video we break down everything you need to know.\n\n"
                    f"#{n.key.replace('_', '')} #shorts #facts")
            thumb = " ".join(t.upper().split()[:4])
        tags = [t, n.label, *t.split()[:5], "faceless", "story", "facts", "youtube"]
        return Script(title=title, hook=sentences[0], scenes=scenes, description=desc, tags=tags,
                      thumbnail_text=thumb, chapter_titles=chapters, language=language)


def get_writer(settings: Settings, force_offline: bool = False):
    if settings.has_claude and not force_offline:
        return ClaudeScriptWriter(settings)
    return OfflineScriptWriter(settings)


IDEAS_SCHEMA = {
    "type": "object",
    "properties": {"topics": {"type": "array", "items": {"type": "string"}}},
    "required": ["topics"],
    "additionalProperties": False,
}


def suggest_topics(settings: Settings, niche_key: str, count: int = 10, language: str = "en",
                   avoid: list[str] | None = None) -> list[str]:
    """Viral topic ideas for a niche (Claude when available, else the niche's samples)."""
    n = get_niche(niche_key)
    if not settings.has_claude:
        return list(n.sample_topics)[:count]
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None, max_retries=3)
    lang_name = {"en": "English", "ar": "Arabic"}.get(language, language)
    prompt = (f"Give {count} specific, high-curiosity video topics for a faceless YouTube channel in the "
              f"'{n.label}' niche (tone: {n.tone}). Each topic is a short working title in {lang_name}. "
              "Prefer concrete stories and surprising angles over generic lists.")
    if avoid:
        prompt += "\nAvoid topics already covered: " + "; ".join(avoid[:50])
    msg = client.messages.create(
        model=settings.claude_model, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": IDEAS_SCHEMA}},
    )
    if msg.stop_reason == "refusal":
        return list(n.sample_topics)[:count]
    text = next(b.text for b in msg.content if b.type == "text")
    return [t.strip() for t in json.loads(text)["topics"] if t.strip()][:count]
