@echo off
setlocal

cd /d "%~dp0"

REM --- Portable mode: use bundled Python (no install needed) ---
if exist "python\python.exe" (
    "python\python.exe" main.py %*
    if errorlevel 1 (
        echo.
        echo ========================================
        echo  AirPin exited with an error. See above.
        echo ========================================
        pause
    )
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
if errorlevel 1 pause
endlocal
