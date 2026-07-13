@echo off
setlocal

REM ============================================================
REM AirPin Extended - Portable Python builder
REM
REM Downloads Python 3.11 embeddable, installs all dependencies.
REM Run this before creating a release zip. The resulting python/
REM folder makes run.bat work with zero system Python installation.
REM
REM Output: python/ folder (~190MB uncompressed, ~65MB zipped)
REM ============================================================

cd /d "%~dp0"

set PY_VERSION=3.11.9
set PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-embed-amd64.zip
set PY_DIR=python

echo.
echo === Building Portable Python %PY_VERSION% ===
echo.

REM --- Clean previous build ---
if exist "%PY_DIR%" rmdir /s /q "%PY_DIR%"
mkdir "%PY_DIR%"

REM --- Download embeddable Python ---
echo Downloading Python %PY_VERSION% embeddable...
curl -L -o python-embed.zip "%PY_URL%"
if errorlevel 1 (
    echo [ERROR] Download failed.
    pause
    exit /b 1
)

REM --- Extract ---
echo Extracting...
cd "%PY_DIR%"
tar -xf ..\python-embed.zip
del ..\python-embed.zip

REM --- Enable site-packages (required for pip) ---
echo Enabling site-packages...
powershell -Command "(Get-Content python311._pth) -replace '#import site', 'import site' | Set-Content python311._pth"

REM --- Install pip ---
echo Installing pip...
curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
python.exe get-pip.py --no-warn-script-location
del get-pip.py

REM --- Install dependencies ---
echo.
echo Installing AirPin dependencies...
python.exe -m pip install --no-warn-script-location pygame-ce PyOpenGL numpy pywin32 sounddevice pyusb dxcam PyAudioWPatch soxr
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

REM --- Clean up pip cache and Scripts (not needed at runtime) ---
echo Cleaning up...
rmdir /s /q Scripts 2>nul
python.exe -m pip cache purge 2>nul

REM --- Verify ---
echo.
echo Verifying imports...
python.exe -c "import pygame, numpy, dxcam, OpenGL.GL, sounddevice, usb.core, pyaudiowpatch, soxr, win32api; print('All imports OK')"

cd ..
echo.
echo === Portable Python build complete! ===
echo Folder: %PY_DIR%\ (%~dp0%PY_DIR%)
echo.
echo To create a release zip:
echo   tar -acf AirPin-portable.zip AirPin\ --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=*.log --exclude=screenshots
echo.
pause
endlocal
