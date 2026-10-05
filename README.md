# Faceless Studio 🎬

A personal app for making faceless YouTube videos, similar to Faceless Frames, plus:
**Claude writes the script, the app records the voice-over and builds a ready-to-upload video**
(MP4 + thumbnail + title + description + chapters + tags + SRT subtitles).

> تطبيق شخصي لصناعة فيديوهات يوتيوب بدون وجه، بفكرة شبيهة بموقع Faceless Frames، وفيه زيادة:
> **Claude يكتب السكريبت، والتطبيق يعمل الفويس أوفر، ويطلّع فيديو جاهز للرفع** (MP4 + ثمبنيل + عنوان + وصف + فصول + تاغات + ترجمة SRT).

---

## بالعربي: كيف تشغّله

1. ثبّت **Python 3.10+** و **ffmpeg**:
   - ويندوز: `winget install ffmpeg`
   - ماك: `brew install ffmpeg`
   - لينكس: `sudo apt install ffmpeg espeak-ng`
2. انسخ `.env.example` باسم `.env` وحط مفتاح Claude:
   `ANTHROPIC_API_KEY=sk-ant-...` (من https://console.anthropic.com)
3. شغّل:
   - ماك/لينكس: `./run.sh`
   - ويندوز: `run.bat`
4. افتح المتصفح على **http://127.0.0.1:5000**

### كيف تستخدمه
- اكتب الموضوع، أو اضغط **✨ Ideas** ليقترح Claude عليك 10 مواضيع.
- اختار **النيش** (قصص رعب، تاريخ، تحفيز، حقائق، جرائم حقيقية، علوم، مال، أساطير، رواقية، قصص أطفال، قصص عربية).
  كل نيش معه ستايل رسم وألوان وموسيقى وصوت وكابشن مناسبين.
- اختار الصيغة: **Short** (عمودي 9:16) أو **فيديو طويل** (16:9 مع فصول/Chapters).
- اختار اللغة: **إنجليزي أو عربي** (الكابشن العربي يطلع موصول وبالاتجاه الصحيح).
- **Batch**: حط كل موضوع بسطر لحاله، وكل سطر بيطلع فيديو مستقل.
- من **Library** بتلاقي الفيديوهات، وتقدر تنزّل الفيديو والثمبنيل وملف SRT، وتنسخ العنوان والوصف والتاغات بكبسة.

### الجودة: شو بيفرق؟
| الشي | مجاني | أحسن جودة |
|---|---|---|
| السكريبت | — | **Claude** (`ANTHROPIC_API_KEY`) |
| الصوت | أصوات Microsoft Edge العصبية (مجانية وطبيعية جداً) | ElevenLabs (`ELEVENLABS_API_KEY`) |
| الصور/الفيديو | صور AI بستايل النيش (Pollinations، بدون مفتاح) | فيديوهات Pexels / Pixabay (مفاتيح مجانية) أو مجلد ميديا تبعك |
| الموسيقى | موسيقى بتتولّد تلقائياً (بدون حقوق) | حط ملفات MP3 تبعك في `assets/music/` |

> إذا ما في إنترنت أو ما في مفاتيح، التطبيق ما بيوقف: بيرجع لصوت espeak المحلي ولرسومات بيولّدها هو.
> هيك بيضل يطلع فيديو كامل، بس الجودة الاحترافية بتحتاج Claude + صوت Edge أو ElevenLabs + صور AI أو ستوك.

---

## Features

- **Script by Claude**: hook-first, retention-focused narration in 11 niche templates; scene-by-scene image prompts,
  stock search terms and on-screen emphasis text; SEO title, description, tags, thumbnail text and chapters.
  Uses structured JSON output, so the output always parses. **✨ Ideas** suggests topics.
- **Voice-over**: Microsoft Edge neural voices (free), ElevenLabs (premium), or espeak-ng (offline fallback).
  Word-level timings drive the captions. The voice is processed with EQ, compression and a limiter.
- **Visuals**: AI images in a consistent art style (8 styles), Pexels/Pixabay stock video and photos, your own
  media folder, or offline generative art. Providers fall back automatically.
- **Editing**: smooth sub-pixel Ken Burns moves (zoom/pan), transitions (crossfade, slide, zoom punch, dip, flash),
  colour grade and vignette.
- **Captions**: 5 animated styles (word-by-word highlight with "pop", Hormozi, clean box, neon, minimal).
  English and Arabic, with correct Arabic shaping and right-to-left order.
- **Audio**: background music ducked under the voice (sidechain), mastered in two passes to **-14 LUFS / -1.5 dBTP**
  (YouTube's loudness target).
- **Output**: 1080×1920 Shorts (auto-fitted to ≤ 60 s) or 1920×1080 long-form; H.264 High, AAC 192k, +faststart,
  BT.709. Also writes a 1280×720 thumbnail, `description.txt` with chapters, `captions.srt` and `metadata.json`.
- **Automatic QA on every video**: resolution, codecs, fps, duration, loudness, true peak, decode errors,
  black frames and long silences.
- **Web app** with a queue (parallel renders), library, batch mode and a JSON API, plus a CLI.

## CLI

```bash
python -m facelessapp serve                                   # web app
python -m facelessapp generate "How black holes work" --niche science --format short
python -m facelessapp generate "The fall of Constantinople" --niche history --format long --duration 480
python -m facelessapp generate "أسرار الأهرامات" --niche arabic_stories --voice ar_male
python -m facelessapp batch topics.txt --niche scary_stories --workers 2
python -m facelessapp ideas --niche motivation --count 20
```

## JSON API

```
POST /api/generate   {"topic": "...", "niche": "history", "format": "long", "duration": 300, "language": "en"}
GET  /api/jobs       list jobs + progress
GET  /api/jobs/<id>
POST /api/ideas      {"niche": "facts", "count": 10, "language": "ar"}
GET  /api/status     which engines/keys are active
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q                                              # unit + end-to-end tests
python scripts/stress_test.py --count 110 --workers 3  # renders 110 videos and QAs each one
```

The latest stress-test results are in [`test-results/report.md`](test-results/report.md).

## Project layout

```
facelessapp/
  script_writer.py  Claude (structured output) + offline template writer
  tts.py            Edge / ElevenLabs / espeak with word timings
  visuals.py        AI images, Pexels, Pixabay, local folder, generative fallback
  music.py          music library or synthesised mood beds
  audio.py          voice chain, ducking, 2-pass loudness mastering
  captions.py       animated ASS captions + SRT
  render.py         Ken Burns, transitions, grading, x264 encode
  thumbnail.py      1280x720 thumbnail
  quality.py        automatic QA
  pipeline.py       orchestrates everything
  web.py, jobs.py   Flask app + job queue
scripts/stress_test.py
```
