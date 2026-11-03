@echo off
rem Daily online data refresh: pipeline -> web snapshot -> rebuild demo.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\run_daily_update.py %*
) else (
    python scripts\run_daily_update.py %*
)
