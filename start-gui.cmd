@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m deepseek_web gui
) else (
    python -m deepseek_web gui
)
if errorlevel 1 (
    echo Install Python 3.11+ with Tcl/Tk, or download the portable Windows release.
    pause
)
