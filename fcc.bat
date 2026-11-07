@echo off
REM Double-click launcher for Windows source checkouts.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.10+ from https://python.org
  pause
  exit /b 1
)
python run.py %*
if errorlevel 1 pause
