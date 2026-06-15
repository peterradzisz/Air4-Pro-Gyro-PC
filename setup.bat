@echo off
setlocal

REM ============================================================
REM AirPin Extended - first-time setup
REM Creates a venv and installs all Python dependencies.
REM DLLs are already bundled in lib\ - no extra download needed.
REM ============================================================

cd /d "%~dp0"

echo.
echo === AirPin Extended - Setup ===
echo.

REM --- Check Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo.
    echo Download Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During install, check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Found Python %PY_VER%

REM --- Check version is 3.10+ ---
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python 3.10 or newer required. You have %PY_VER%.
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo [ERROR] Python 3.10 or newer required. You have %PY_VER%.
    pause
    exit /b 1
)

REM --- Create venv if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv\...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists, skipping creation.
)

REM --- Activate venv and install ---
echo.
echo Installing dependencies (this can take a few minutes)...
echo.

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. See messages above.
    echo Common cause: missing Microsoft Visual C++ Build Tools.
    echo Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

REM --- Verify DLLs ---
echo.
echo Verifying bundled DLLs...
if not exist "lib\RayNeoSDK.dll" (
    echo [ERROR] lib\RayNeoSDK.dll is missing.
    echo Re-download the project from the Releases page.
    pause
    exit /b 1
)
if not exist "lib\libusb-1.0.dll" (
    echo [ERROR] lib\libusb-1.0.dll is missing.
    echo Re-download the project from the Releases page.
    pause
    exit /b 1
)
echo   lib\RayNeoSDK.dll    OK
echo   lib\libusb-1.0.dll   OK

echo.
echo === Setup complete! ===
echo.
echo To start AirPin, double-click:  run.bat
echo.
pause
endlocal
