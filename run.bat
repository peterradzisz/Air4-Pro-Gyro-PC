@echo off
setlocal

REM ============================================================
REM AirPin Extended - launcher
REM Runs the app. If venv doesn't exist, calls setup.bat first.
REM ============================================================

cd /d "%~dp0"

REM First-run: forward to setup.bat
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup first...
    echo.
    call setup.bat
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python main.py %*
endlocal
