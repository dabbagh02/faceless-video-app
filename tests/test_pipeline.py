import json

from facelessapp.models import Scene, Script, VideoRequest
from facelessapp.pipeline import build_chapters, build_description, generate_video, slugify
from facelessapp.visuals import fetch_visuals


def _script(starts, titles):
    scenes = []
    for s in starts:
        sc = Scene("n", "p", "q")
        sc.start, sc.duration = s, 12
        scenes.append(sc)
    return Script("t", "h", scenes, "desc", ["a"], "T", titles)


def test_chapters_follow_youtube_rules():
    s = _script([0.1, 5, 20, 40, 60], ["Intro", "Too soon", "Two", "Three", "Four"])
    ch = build_chapters(s)
    assert ch[0] == (0.0, "Intro")
    assert [c[1] for c in ch] == ["Intro", "Two", "Three", "Four"]
    assert all(b[0] - a[0] >= 10 for a, b in zip(ch, ch[1:]))
    assert "0:00 Intro" in build_description(s, ch)


def test_too_few_chapters_are_dropped():
    assert build_chapters(_script([0, 30], ["A", "B"])) == []


def test_slugify_unicode():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("أسرار الأهرامات") == "أسرار-الأهرامات"
    assert slugify("!!!") == "video"


def test_visual_fallback_to_procedural(settings):
    class Boom:
        name = "ai"

        def fetch(self, *a):
            raise RuntimeError("offline")
    import facelessapp.visuals as v
    orig = v.build_chain
    v.build_chain = lambda st, src, pal: [Boom(), v.ProceduralProvider(st, pal)]
    try:
        scenes = [Scene("n", "p", "q"), Scene("n2", "p2", "q2")]
        usage = fetch_visuals(settings, scenes, 320, 568, "auto", ("#000000", "#333333", "#ffffff"))
    finally:
        v.build_chain = orig
    assert usage == {"procedural": 2}
    assert all(s.visual_path for s in scenes)


def test_end_to_end_short_video(settings, tmp_path):
    stages = []
    r = generate_video(VideoRequest(topic="Why the sky is blue", niche="science", format="short", duration=15, seed=1),
                       settings, progress=lambda s, f: stages.append(s), out_dir=tmp_path / "v")
    assert r.report["ok"], r.report
    assert r.video_path.exists() and r.thumbnail_path.exists() and r.srt_path.exists()
    meta = json.loads(r.metadata_path.read_text())
    assert meta["resolution"] == "1080x1920" and "#shorts" in meta["description"]
    assert stages[-1] == "Done"
    assert not (tmp_path / "v" / "work").exists()
