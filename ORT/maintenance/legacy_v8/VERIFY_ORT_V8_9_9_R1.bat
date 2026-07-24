@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ROOT%ORT\runtime_app\tools\verify_v8_9_9_r1_install.py"
echo.
pause
