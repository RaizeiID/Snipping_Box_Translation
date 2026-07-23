@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\audio_gpu\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Runtime Audio GPU tidak ditemukan: %PY%
  echo Jalankan INSTALL_AUDIO_GPU_V8_9_9_R2.bat terlebih dahulu.
  pause
  exit /b 1
)
"%PY%" "%~dp0ORT\runtime_app\tools\check_audio_gpu_v8_9_9.py"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo GPU belum siap. Jalankan INSTALL_AUDIO_GPU_V8_9_9_R2.bat.
pause
exit /b %RC%
