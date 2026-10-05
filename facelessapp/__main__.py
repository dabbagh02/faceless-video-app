"""Command line interface.

  python -m facelessapp serve                       # web app on http://127.0.0.1:5000
  python -m facelessapp generate "topic" --niche history --format long --duration 300
  python -m facelessapp batch topics.txt --niche facts --workers 2
  python -m facelessapp ideas --niche scary_stories
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import get_settings
from .models import VideoRequest
from .presets import ART_STYLES, CAPTION_STYLES, FORMATS, NICHES, VOICES


def _add_video_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--niche", default="facts", choices=sorted(NICHES))
    p.add_argument("--format", default="short", choices=sorted(FORMATS))
    p.add_argument("--duration", type=int, default=0, help="target seconds (0 = format default)")
    p.add_argument("--voice", default="", choices=[""] + sorted(VOICES))
    p.add_argument("--language", default="", help="en | ar (default: voice language)")
    p.add_argument("--art-style", default="", choices=[""] + sorted(ART_STYLES))
    p.add_argument("--captions", default="", choices=[""] + sorted(CAPTION_STYLES))
    p.add_argument("--visuals", default="", help="auto | ai | stock | local | procedural")
    p.add_argument("--no-music", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--offline-script", action="store_true", help="use templates instead of Claude")


def _req(args, topic: str, seed_offset: int = 0) -> VideoRequest:
    return VideoRequest(topic=topic, niche=args.niche, format=args.format, duration=args.duration,
                        voice=args.voice, language=args.language, art_style=args.art_style,
                        caption_style=args.captions, visual_source=args.visuals, music=not args.no_music,
                        seed=args.seed + seed_offset)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="facelessapp", description="Faceless YouTube video generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=5000)

    g = sub.add_parser("generate", help="make one video")
    g.add_argument("topic")
    _add_video_args(g)

    b = sub.add_parser("batch", help="make one video per line of a text file")
    b.add_argument("file")
    b.add_argument("--workers", type=int, default=0)
    _add_video_args(b)

    i = sub.add_parser("ideas", help="topic ideas from Claude")
    i.add_argument("--niche", default="facts", choices=sorted(NICHES))
    i.add_argument("--count", type=int, default=10)
    i.add_argument("--language", default="en")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    if args.cmd == "serve":
        from .web import serve
        serve(args.host, args.port)
        return 0

    if args.cmd == "ideas":
        from .script_writer import suggest_topics
        for t in suggest_topics(settings, args.niche, args.count, args.language):
            print(t)
        return 0

    from .pipeline import generate_video

    def progress(stage, frac):
        print(f"\r[{frac * 100:5.1f}%] {stage:<30}", end="", file=sys.stderr, flush=True)

    if args.cmd == "generate":
        r = generate_video(_req(args, args.topic), settings, progress=progress,
                           force_offline_script=args.offline_script)
        print(file=sys.stderr)
        print(json.dumps({"video": str(r.video_path), "thumbnail": str(r.thumbnail_path),
                          "title": r.script.title, "duration": r.duration, "qa": r.report},
                         ensure_ascii=False, indent=2))
        return 0 if r.report.get("ok", True) else 1

    if args.cmd == "batch":
        with open(args.file, encoding="utf-8") as f:
            topics = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        workers = args.workers or settings.workers
        failed = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(generate_video, _req(args, t, k), settings, None, None, args.offline_script): t
                    for k, t in enumerate(topics)}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    print(f"✔ {futs[fut]} -> {r.video_path} ({r.duration:.0f}s, QA {'ok' if r.report.get('ok') else r.report.get('issues')})")
                except Exception as e:
                    failed += 1
                    print(f"✘ {futs[fut]}: {e}")
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
