@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -c "import huggingface_hub" >nul 2>&1
if errorlevel 1 (
  echo Menyiapkan huggingface_hub pada runtime Audio CPU...
  "%PY%" -m pip install --upgrade huggingface_hub
  if errorlevel 1 goto :failed
)
echo Menyiapkan Japanese Specialist dan tokenizer lokal...
"%PY%" "%~dp0ORT\runtime_app\tools\install_japanese_specialist_v8_9_9.py"
if errorlevel 1 goto :failed
echo.
echo Japanese Specialist selesai disiapkan dan lulus uji model CPU offline.
pause
exit /b 0
:failed
echo.
echo Instalasi Japanese Specialist gagal. Periksa output stage, internet, ruang penyimpanan, dan runtime Audio CPU.
pause
exit /b 1
