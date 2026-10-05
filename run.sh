#!/usr/bin/env bash
# One-command start: creates a venv, installs deps, opens the web app on http://127.0.0.1:5000
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Please install ffmpeg first (https://ffmpeg.org/download.html)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
python -m facelessapp serve "$@"
