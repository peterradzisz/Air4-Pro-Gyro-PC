@echo off
REM Launcher - uses script directory, works from any folder
cd /d "%~dp0"
python main.py %*
