@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Easy German Lesson - Local Transcript Runner
echo ==============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  echo Install Python 3.12+ and try again.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [ERROR] .env file is missing.
  echo Copy .env.example to .env and set NOTION_TOKEN.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 goto :fail

  echo [setup] Installing dependencies...
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
)

echo [1/3] Updating repository...
git pull --ff-only
if errorlevel 1 (
  echo [ERROR] git pull failed. Resolve local Git changes first.
  pause
  exit /b 1
)

echo.
echo [2/3] Fetching requested transcripts from Notion...
.venv\Scripts\python.exe fetch_requested_transcripts_local.py
if errorlevel 1 goto :fail

echo.
echo [3/3] Done.
echo GitHub will automatically create the requested lesson from the transcript.
echo You can close this window.
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] The Easy German workflow did not finish successfully.
echo Read the message above, then try again.
echo.
pause
exit /b 1
