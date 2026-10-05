import re

from facelessapp.captions import build_ass, build_srt, chunk_words
from facelessapp.models import Scene, WordTiming
from facelessapp.presets import CAPTION_STYLES


def _scene(text, start, step=0.4):
    words = [WordTiming(w, i * step, i * step + step * 0.9) for i, w in enumerate(text.split())]
    s = Scene(narration=text, image_prompt="", search_query="", on_screen_text="BIG {TEXT}")
    s.words, s.start, s.duration = words, start, len(words) * step
    return s


def test_chunks_break_on_punctuation_and_size():
    words = [WordTiming(w, i, i + 0.5) for i, w in enumerate("one two three. four five six seven".split())]
    chunks = chunk_words(words, 3)
    assert [len(c) for c in chunks] == [3, 3, 1]


def test_ass_escapes_and_has_no_overlaps():
    scenes = [_scene("Hello {world} back\\slash test, again and again.", 0.1), _scene("Second scene here.", 4.0)]
    for key, style in CAPTION_STYLES.items():
        ass = build_ass(scenes, style, 1080, 1920, "en", 6.0)
        events = [l for l in ass.splitlines() if l.startswith("Dialogue: 0")]
        assert events, key
        text = "".join(re.sub(r"\{\\[^}]*\}", "", e.split(",", 9)[-1]) for e in events)
        assert "{" not in text and "\\" not in text
        def secs(t):
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        spans = sorted((secs(e.split(",")[1]), secs(e.split(",")[2])) for e in events)
        assert all(b[0] >= a[1] - 0.011 for a, b in zip(spans, spans[1:])), key


def test_arabic_captions_use_arabic_font_and_no_letter_spacing():
    s = _scene("لا أحد يتحدث عن هذا", 0.0)
    ass = build_ass([s], CAPTION_STYLES["bold_pop"], 1920, 1080, "ar", 3.0)
    styles = [l for l in ass.splitlines() if l.startswith("Style:")]
    assert all("Noto Sans Arabic" in l for l in styles)
    assert all(l.split(",")[13] == "0" for l in styles)  # Spacing column must be 0 for Arabic shaping
    assert "لا" in ass


def test_srt_format():
    srt = build_srt([_scene("one two three four five six seven eight nine ten.", 1.0)])
    assert srt.startswith("1\n00:00:01,000 --> ")
    assert "ten." in srt
