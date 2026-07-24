@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0ORT\runtime_app\tools\verify_v8_9_8_install.py"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
