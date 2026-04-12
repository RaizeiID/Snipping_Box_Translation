@echo off
setlocal
cd /d "%~dp0"
py -3 TITAN_LAUNCHER.py
if errorlevel 1 (
  echo.
  echo [!] Launcher keluar dengan error.
)
echo.
pause
