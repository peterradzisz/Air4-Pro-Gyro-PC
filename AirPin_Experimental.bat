@echo off
cd /d "%~dp0"
echo Switching to experimental branch...
git checkout experimental >nul 2>&1
python main.py %*
