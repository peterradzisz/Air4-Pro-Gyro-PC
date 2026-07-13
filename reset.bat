@echo off
cd /d "%~dp0"

echo ========================================
echo   AirPin Reset
echo ========================================
echo.

REM --- Kill any running AirPin processes ---
echo Stopping AirPin...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM python3.11.exe >nul 2>&1

REM --- Restore system cursor ---
echo Restoring cursor...
python\python.exe -c "import ctypes; ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)" >nul 2>&1
reg add "HKCU\Control Panel\Cursors" /ve /t REG_SZ /d "" /f >nul 2>&1

REM --- Delete settings (fresh start next run) ---
if exist "airpin_settings.json" (
    echo Deleting settings...
    del "airpin_settings.json"
)

REM --- Clear logs ---
if exist "airpin.log" del "airpin.log"

echo.
echo ========================================
echo   Reset complete! All settings cleared.
echo   Double-click run.bat to start fresh.
echo ========================================
pause
