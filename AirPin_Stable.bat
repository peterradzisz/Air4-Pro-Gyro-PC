@echo off
cd /d "%~dp0"
echo Switching to stable branch...
git checkout stable >nul 2>&1
python main.py %*
