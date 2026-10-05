@echo off
REM One-command start on Windows: creates a venv, installs deps, opens http://127.0.0.1:5000
cd /d "%~dp0"
where ffmpeg >nul 2>nul || (echo Please install ffmpeg first: winget install ffmpeg & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env copy .env.example .env
python -m facelessapp serve %*
