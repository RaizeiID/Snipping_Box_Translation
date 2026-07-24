@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=py"
echo.
echo ORT v8.9.9 R2 - Install/Repair Audio GPU
echo Paket CUDA dapat berukuran lebih dari 1 GB. Jangan tutup jendela ini saat instalasi.
echo.
"%PY%" "%~dp0ORT\runtime_app\tools\install_audio_gpu_v8_9_9_r2.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo GPU Audio berhasil divalidasi dengan inferensi nyata.
  echo Tutup seluruh WebUI/Audio ORT, lalu buka kembali.
) else (
  echo GPU belum lulus validasi. Mode Normal CPU tetap tersedia.
)
pause
exit /b %RC%
