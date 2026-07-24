@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\audio_gpu\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Runtime Audio GPU tidak ditemukan: %PY%
  pause
  exit /b 1
)
"%PY%" "%~dp0ORT\runtime_app\tools\check_audio_gpu_v8_9_8.py"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo GPU belum siap. Jangan mengharapkan mode Japanese Specialist berjalan cepat sebelum pemeriksaan ini lulus.
pause
exit /b %RC%
