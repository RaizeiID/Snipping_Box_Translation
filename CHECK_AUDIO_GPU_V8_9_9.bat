@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\audio_gpu\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Runtime Audio GPU tidak ditemukan: %PY%
  pause
  exit /b 1
)
"%PY%" "%~dp0ORT\runtime_app\tools\check_audio_gpu_v8_9_9.py"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo GPU belum siap. ORT v8.9.9 akan mempertahankan Japanese Specialist dengan berpindah ke Kotoba CPU.
pause
exit /b %RC%
