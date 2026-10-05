import json
from types import SimpleNamespace

import pytest

from facelessapp.models import VideoRequest
from facelessapp.presets import FORMATS, NICHES
from facelessapp.script_writer import (SCRIPT_SCHEMA, ClaudeScriptWriter, OfflineScriptWriter, build_user_prompt,
                                       script_from_dict, target_words)


@pytest.mark.parametrize("niche", sorted(NICHES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_offline_writer_every_niche(niche, fmt):
    req = VideoRequest(topic=NICHES[niche].sample_topics[0], niche=niche, format=fmt, duration=40)
    s = OfflineScriptWriter().write(req)
    assert len(s.scenes) >= 2
    assert all(sc.narration and sc.image_prompt for sc in s.scenes)
    assert s.title and s.description and s.tags and s.thumbnail_text
    assert len(s.chapter_titles) == len(s.scenes)
    words = len(s.full_text.split())
    target, _ = target_words(req, s.language)
    assert target * 0.6 <= words <= target * 1.6


def test_offline_writer_is_deterministic():
    req = VideoRequest(topic="Black holes", niche="science", seed=3)
    assert OfflineScriptWriter().write(req).full_text == OfflineScriptWriter().write(req).full_text


def test_custom_script_used_verbatim():
    text = "First sentence here. Second one! And a third?"
    s = OfflineScriptWriter().write(VideoRequest(topic="x", custom_script=text))
    assert s.full_text == text


def test_script_from_dict_cleans_markdown_and_stage_directions():
    data = {"title": "T", "hook": "", "description": "d", "tags": ["#a", " b "], "thumbnail_text": "",
            "scenes": [{"narration": "**Bold** [music swells] text", "image_prompt": "", "search_query": "",
                        "on_screen_text": "", "chapter_title": ""},
                       {"narration": "   ", "image_prompt": "p", "search_query": "q", "on_screen_text": "",
                        "chapter_title": "Ch"}]}
    s = script_from_dict(data, "en", vertical=False)
    assert len(s.scenes) == 1
    assert s.scenes[0].narration == "Bold text"
    assert s.tags == ["a", "b"]
    assert s.chapter_titles == ["Intro"]  # first chapter forced for long-form
    assert s.thumbnail_text


def test_prompt_mentions_language_and_style():
    p = build_user_prompt(VideoRequest(topic="الأهرامات", niche="arabic_stories", format="long"), "ar")
    assert "Arabic" in p and "chapters" in p and "image_prompt" in p


class _FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


def _fake_client(payload, calls, stop_reason="end_turn"):
    msg = SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    def stream(**kw):
        calls.append(kw)
        return _FakeStream(msg)

    return SimpleNamespace(messages=SimpleNamespace(stream=stream), beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


PAYLOAD = {
    "title": "The Ocean's Deepest Secret", "hook": "The ocean hides a mountain taller than Everest.",
    "scenes": [{"narration": f"Scene {i} narration.", "image_prompt": f"prompt {i}", "search_query": "ocean",
                "on_screen_text": "", "chapter_title": ""} for i in range(5)],
    "description": "desc #ocean", "tags": ["ocean", "facts"], "thumbnail_text": "DEEPER THAN EVEREST",
}


def test_claude_writer_requests_structured_output(settings):
    calls = []
    w = ClaudeScriptWriter(settings, client=_fake_client(PAYLOAD, calls))
    s = w.write(VideoRequest(topic="ocean", niche="facts"))
    assert s.title == PAYLOAD["title"] and len(s.scenes) == 5
    kw = calls[0]
    assert kw["model"] == settings.claude_model
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": SCRIPT_SCHEMA}
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_writer_refusal_raises(settings):
    w = ClaudeScriptWriter(settings, client=_fake_client(PAYLOAD, [], stop_reason="refusal"))
    with pytest.raises(RuntimeError, match="declined"):
        w.write(VideoRequest(topic="x"))


def test_claude_writer_retries_without_fallbacks_on_400(settings):
    import anthropic
    import httpx
    calls = []
    good = _fake_client(PAYLOAD, calls)

    def beta_stream(**kw):
        resp = httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        raise anthropic.BadRequestError("unsupported", response=resp, body=None)

    client = SimpleNamespace(messages=good.messages, beta=SimpleNamespace(messages=SimpleNamespace(stream=beta_stream)))
    s = ClaudeScriptWriter(settings, client=client).write(VideoRequest(topic="x"))
    assert len(s.scenes) == 5 and "fallbacks" not in calls[0]


def test_offline_writer_handles_very_long_topics():
    topic = ("The extraordinarily long and winding title about the incredibly detailed history of the tiny "
             "village that accidentally changed the course of European trade routes forever")
    req = VideoRequest(topic=topic, niche="mythology", format="short", duration=15)
    s = OfflineScriptWriter().write(req)
    target, _ = target_words(req, "en")
    assert len(s.full_text.split()) <= target * 1.4
