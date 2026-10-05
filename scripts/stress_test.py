#!/usr/bin/env python3
"""Render a large matrix of videos end-to-end and QA every one of them.

    python scripts/stress_test.py --count 110 --workers 3 --out /tmp/stress

Covers every niche, both formats, every caption style, every art style, every voice,
English + Arabic, music on/off, custom scripts and nasty topic strings. Each output is
checked with ffprobe/ffmpeg (resolution, codecs, fps, duration, -14 LUFS loudness, true
peak, decode errors, black frames, long silences) plus caption/metadata sanity checks.
Writes results.json, report.md and a contact sheet of thumbnails + mid-video frames.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import re
import subprocess
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facelessapp.presets import ART_STYLES, CAPTION_STYLES, FORMATS, NICHES, VOICES  # noqa: E402

TRICKY_TOPICS = [
    "Why {curly braces} and \\backslashes break subtitles",
    "100% true: the $1,000,000 mistake & what it cost",
    "\"Quoted\" topics, apostrophes' and colons: part 2",
    "A",
    "The extraordinarily long and winding title about the incredibly detailed history of the tiny "
    "village that accidentally changed the course of European trade routes forever",
    "Emoji test 🚀🔥 rockets and fire",
    "Ünïcödé façade: café, naïve, jalapeño",
]

CUSTOM_SCRIPT = ("In 1969, three astronauts left Earth. Four days later, two of them walked on the Moon. "
                 "But the man who stayed behind, Michael Collins, saw something nobody else ever had. "
                 "Alone, behind the Moon, he was cut off from every human being in the universe. "
                 "He later said he felt not fear, but awareness, and even joy. Remember his name.")


def build_matrix(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    niches = list(NICHES)
    caps = list(CAPTION_STYLES)
    arts = list(ART_STYLES)
    voices = list(VOICES)
    cases = []
    cycle = itertools.count()
    while len(cases) < count:
        i = next(cycle)
        n = NICHES[niches[i % len(niches)]]
        fmt = "long" if i % 4 == 3 else "short"
        lang = "ar" if n.key == "arabic_stories" or i % 13 == 5 else "en"
        voice = rng.choice([v for v in voices if VOICES[v].language == lang])
        topic = rng.choice(n.sample_topics) if lang == ("ar" if n.key == "arabic_stories" else "en") else (
            rng.choice(NICHES["arabic_stories"].sample_topics))
        if i % 9 == 7:
            topic = TRICKY_TOPICS[(i // 9) % len(TRICKY_TOPICS)]
            lang, voice = "en", rng.choice([v for v in voices if VOICES[v].language == "en"])
        if fmt == "short":
            duration = rng.choice([15, 25, 35, 45, 55, 60, 0])
        else:
            duration = rng.choice([60, 90, 120, 150, 180])
        if i in (40, 80):  # a couple of genuinely long-form videos
            fmt, duration = "long", 420
        case = dict(
            idx=len(cases), topic=topic, niche=n.key, format=fmt, duration=duration, language=lang,
            voice=voice, art_style=arts[i % len(arts)], caption_style=caps[(i // 2) % len(caps)],
            visual_source="auto", music=(i % 6 != 2), seed=i,
            custom_script=CUSTOM_SCRIPT if (i % 17 == 11 and lang == "en") else "",
        )
        cases.append(case)
    return cases


def ass_checks(ass_text: str, words_in_script: int) -> list[str]:
    issues = []
    events = [l for l in ass_text.splitlines() if l.startswith("Dialogue:")]
    if not events:
        return ["no caption events"]
    times = []
    for e in events:
        m = re.match(r"Dialogue: (\d),(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),", e)
        start = int(m[2]) * 3600 + int(m[3]) * 60 + float(m[4])
        end = int(m[5]) * 3600 + int(m[6]) * 60 + float(m[7])
        if end <= start:
            issues.append(f"caption with non-positive duration: {e[:80]}")
        if m[1] == "0":
            times.append((start, end))
    times.sort()
    overlaps = sum(1 for a, b in zip(times, times[1:]) if b[0] < a[1] - 0.011)
    if overlaps:
        issues.append(f"{overlaps} overlapping caption events")
    if "{" in "".join(re.sub(r"\{\\[^}]*\}", "", e.split(",", 9)[-1]) for e in events):
        issues.append("unescaped brace in caption text")
    return issues


def run_case(case: dict, out_root: str) -> dict:
    from facelessapp.config import get_settings
    from facelessapp.models import VideoRequest
    from facelessapp.pipeline import generate_video

    t0 = time.time()
    out_dir = Path(out_root) / f"{case['idx']:03d}-{case['niche']}-{case['format']}"
    settings = get_settings(output_dir=Path(out_root))
    req = VideoRequest(**{k: v for k, v in case.items() if k != "idx"})
    res = dict(case=case, ok=False, issues=[], seconds=0.0, out=str(out_dir))
    try:
        r = generate_video(req, settings, out_dir=out_dir)
        meta = json.loads(r.metadata_path.read_text(encoding="utf-8"))
        issues = list(r.report.get("issues", []))
        issues += ass_checks((out_dir / "captions.ass").read_text(encoding="utf-8"),
                             len(r.script.full_text.split()))
        fmt = FORMATS[case["format"]]
        if case["duration"] and fmt.vertical:
            if r.duration > fmt.max_seconds + 0.05:
                issues.append(f"short too long: {r.duration}")
        # a custom script is read verbatim, so its length (not the requested duration) decides
        if case["duration"] and not case["custom_script"] and \
                abs(r.duration - case["duration"]) > max(12, case["duration"] * 0.35):
            issues.append(f"duration {r.duration:.0f}s far from requested {case['duration']}s")
        if not meta["title"] or not meta["description"] or not meta["tags"]:
            issues.append("missing metadata")
        if case["format"] == "long" and r.duration > 60 and not meta["chapters"]:
            issues.append("long video without chapters")
        if not (out_dir / "thumbnail.jpg").exists() or not (out_dir / "captions.srt").read_text().strip():
            issues.append("missing thumbnail/srt")
        # frame sample for the contact sheet
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{r.duration * 0.4:.2f}", "-i", str(r.video_path),
                        "-frames:v", "1", "-vf", "scale=-2:360", str(out_dir / "sample.jpg")], check=False)
        res.update(ok=not issues, issues=issues, duration=r.duration, title=meta["title"],
                   size_mb=r.report.get("size_mb"), lufs=r.report.get("integrated_lufs"),
                   peak=r.report.get("true_peak_dbfs"), scenes=len(r.script.scenes),
                   tts=meta["tts_engine"], visuals=meta["visual_sources"], render_seconds=meta["render_seconds"])
        if not os.environ.get("KEEP_VIDEOS"):
            r.video_path.unlink()  # keep disk usage sane; artefacts + QA stay
    except Exception as e:
        res["issues"] = [f"EXCEPTION: {e}", traceback.format_exc()[-1500:]]
    res["seconds"] = round(time.time() - t0, 1)
    return res


def contact_sheet(results: list[dict], out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    tiles = []
    for r in results:
        d = Path(r["out"])
        for name in ("sample.jpg",):
            p = d / name
            if p.exists():
                tiles.append((Image.open(p).convert("RGB"), r))
    if not tiles:
        return
    th = 300
    cols = 10
    tw = 200
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (12, 12, 16))
    font = ImageFont.load_default()
    for k, (img, r) in enumerate(tiles):
        img.thumbnail((tw - 6, th - 22))
        x, y = (k % cols) * tw, (k // cols) * th
        sheet.paste(img, (x + (tw - img.width) // 2, y + 2))
        ImageDraw.Draw(sheet).text((x + 4, y + th - 18), f"#{r['case']['idx']} {r['case']['niche'][:12]} "
                                                         f"{'OK' if r['ok'] else 'FAIL'}",
                                   fill=(120, 230, 150) if r["ok"] else (255, 90, 90), font=font)
    sheet.save(out, quality=85)


def thumb_sheet(results: list[dict], out: Path, limit: int = 24) -> None:
    from PIL import Image
    thumbs = [Path(r["out"]) / "thumbnail.jpg" for r in results if (Path(r["out"]) / "thumbnail.jpg").exists()]
    thumbs = thumbs[:limit]
    if not thumbs:
        return
    cols, w, h = 4, 320, 180
    sheet = Image.new("RGB", (cols * w, ((len(thumbs) + cols - 1) // cols) * h))
    for k, p in enumerate(thumbs):
        sheet.paste(Image.open(p).convert("RGB").resize((w, h)), ((k % cols) * w, (k // cols) * h))
    sheet.save(out, quality=85)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=110)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="stress-output")
    ap.add_argument("--report", default="test-results")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--only", default="", help="comma-separated case indexes to (re)run")
    args = ap.parse_args()

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    report_dir = Path(args.report)
    report_dir.mkdir(parents=True, exist_ok=True)
    cases = build_matrix(args.count, args.seed)
    if args.only:
        keep = {int(x) for x in args.only.split(",")}
        cases = [c for c in cases if c["idx"] in keep]
    print(f"Rendering {len(cases)} videos with {args.workers} workers -> {out_root}", flush=True)
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_case, c, str(out_root)) for c in cases]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            c = r["case"]
            status = "OK  " if r["ok"] else "FAIL"
            print(f"[{len(results):3d}/{len(cases)}] {status} #{c['idx']:03d} {c['niche']:<15} {c['format']:<5} "
                  f"{r.get('duration', 0):6.1f}s {r['seconds']:6.1f}s render  {'; '.join(r['issues'])[:160]}",
                  flush=True)
    results.sort(key=lambda r: r["case"]["idx"])
    wall = time.time() - t0
    (report_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    contact_sheet(results, report_dir / "frames.jpg")
    thumb_sheet(results, report_dir / "thumbnails.jpg")

    ok = [r for r in results if r["ok"]]
    total_video = sum(r.get("duration", 0) for r in results)
    lufs = [r["lufs"] for r in results if r.get("lufs") is not None]
    by = lambda key: {k: sum(1 for r in results if r["case"][key] == k) for k in
                      sorted({r["case"][key] for r in results})}
    lines = [
        "# Stress test report", "",
        f"- Videos rendered: **{len(results)}**, passed QA: **{len(ok)}**, failed: **{len(results) - len(ok)}**",
        f"- Total video length: {total_video / 60:.1f} min; wall time {wall / 60:.1f} min with {args.workers} workers",
        f"- Loudness: min {min(lufs):.1f} / max {max(lufs):.1f} LUFS (target -14)" if lufs else "- Loudness: n/a",
        f"- Formats: {by('format')}", f"- Languages: {by('language')}", f"- Niches: {by('niche')}",
        f"- Caption styles: {by('caption_style')}", f"- Art styles: {by('art_style')}", f"- Voices: {by('voice')}",
        "", "| # | niche | format | lang | captions | requested | actual | scenes | LUFS | MB | result |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        c = r["case"]
        lines.append(f"| {c['idx']} | {c['niche']} | {c['format']} | {c['language']} | {c['caption_style']} | "
                     f"{c['duration'] or 'default'} | {r.get('duration', 0):.1f}s | {r.get('scenes', '-')} | "
                     f"{r.get('lufs', '-')} | {r.get('size_mb', '-')} | "
                     f"{'✅' if r['ok'] else '❌ ' + '; '.join(r['issues'])[:120].replace('|', '/')} |")
    (report_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(ok)}/{len(results)} passed. Report: {report_dir / 'report.md'}")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
