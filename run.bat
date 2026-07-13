@echo off
setlocal

REM ============================================================
REM AirPin Extended - launcher
REM Uses bundled Python if available, else falls back to system Python.
REM ============================================================

cd /d "%~dp0"

REM --- Portable mode: use bundled Python (no install needed) ---
if exist "python\python.exe" (
    "python\python.exe" main.py %*
    endlocal
    exit /b
)

REM --- System Python fallback (source code users) ---
if not exist ".venv\Scripts\python.exe" (
    echo Portable Python not found. Running setup first...
    echo.
    call setup.bat
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python main.py %*
endlocal
