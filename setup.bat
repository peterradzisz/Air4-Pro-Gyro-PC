@echo off
setlocal

REM ============================================================
REM AirPin Extended - first-time setup
REM Creates a venv and installs all Python dependencies.
REM DLLs are already bundled in lib\ - no extra download needed.
REM ============================================================

cd /d "%~dp0"

REM --- Unblock files downloaded from the internet (MOTW) ---
REM Windows marks downloaded DLLs as untrusted, which can block ctypes loading.
echo Checking for downloaded-file restrictions ^(Mark of the Web^)...
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0' -Recurse -File | Unblock-File" >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Could not auto-unblock files. If DLL load fails later, manually:
    echo   Right-click the .zip ^> Properties ^> check "Unblock" ^> OK, then re-extract.
)

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

REM --- Check for Microsoft Store Python stub (zero-byte file) ---
echo Checking Python is not the Microsoft Store stub...
set IS_STORE_STUB=0
for /f "delims=" %%p in ('where python') do (
    for %%f in ("%%p") do (
        if %%~zf LSS 1000 set IS_STORE_STUB=1
        if %%~zf EQU 0 set IS_STORE_STUB=1
    )
)
if "%IS_STORE_STUB%"=="1" (
    echo [ERROR] Microsoft Store Python stub detected ^(zero-byte python.exe^).
    echo This stub does not actually run Python - it opens the Store.
    echo.
    echo Fix: Uninstall "Python" from Settings ^> Apps, then install real Python:
    echo   https://www.python.org/downloads/release/python-3119/
    echo Check "Add python.exe to PATH" during install.
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

REM --- Check Python is 64-bit ---
echo Checking Python is 64-bit...
python -c "import struct; exit(0 if struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
    echo [ERROR] 64-bit Python required. You have 32-bit Python.
    echo The bundled DLLs ^(RayNeoSDK.dll, libusb-1.0.dll^) are 64-bit only.
    echo.
    echo Fix: Uninstall 32-bit Python, install 64-bit from:
    echo   https://www.python.org/downloads/release/python-3119/
    echo Choose "Windows installer (64-bit)".
    echo.
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

REM --- Install dependencies ---
REM dxcam has no wheels for Python 3.13+. Use --only-binary so pip fails
REM clearly instead of attempting a source build (which needs VS Build Tools).
python -m pip install --upgrade pip --quiet
python -m pip install pygame-ce PyOpenGL numpy pywin32 sounddevice pyusb PyAudioWPatch soxr
if errorlevel 1 goto :pip_failed
python -m pip install --only-binary dxcam dxcam
if errorlevel 1 (
    echo.
    echo [ERROR] dxcam has no pre-built wheel for your Python version.
    echo dxcam 0.0.5 supports Python 3.7-3.12 only.
    echo.
    echo Your Python: %PY_VER%
    echo.
    echo Fix: Uninstall Python %PY_VER%, install Python 3.11 or 3.12 from:
    echo   https://www.python.org/downloads/release/python-3119/
    echo Then re-run setup.bat.
    echo.
    pause
    exit /b 1
)
goto :pip_ok

:pip_failed
    echo.
    echo [ERROR] pip install failed. See messages above.
    echo Common cause: missing Microsoft Visual C++ Build Tools.
    echo Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1

:pip_ok

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
