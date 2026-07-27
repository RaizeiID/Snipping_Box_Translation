@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

for %%I in ("%~dp0.") do set "PATCH_DIR=%%~fI"
set "PROJECT_ROOT="

if exist "%PATCH_DIR%\VERSION.txt" if exist "%PATCH_DIR%\ORT_App" set "PROJECT_ROOT=%PATCH_DIR%"
if not defined PROJECT_ROOT if exist "%PATCH_DIR%\..\VERSION.txt" if exist "%PATCH_DIR%\..\ORT_App" for %%I in ("%PATCH_DIR%\..") do set "PROJECT_ROOT=%%~fI"

if not defined PROJECT_ROOT (
  echo Project root ORT tidak ditemukan otomatis.
  echo Letakkan folder patch ini di dalam root ORT, misalnya:
  echo D:\AI TRANSLATOR\ORT_Translation_v8_8_1\ORT_v9.0.5_R3_Offline_Argos_CUDA_Repair
  pause
  exit /b 3
)

set "PY_EXE=%PROJECT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=%PROJECT_ROOT%\ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=%PROJECT_ROOT%\ORT_Runtime\audio_gpu\.venv\Scripts\python.exe"

if not exist "%PY_EXE%" (
  where py >nul 2>nul
  if not errorlevel 1 set "PY_EXE=py -3"
)
if not defined PY_EXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_EXE=python"
)
if not defined PY_EXE (
  echo Python tidak ditemukan.
  pause
  exit /b 4
)

echo ============================================================
echo  ORT v9.0.5 R3 - Offline Argos ^& Native CUDA DLL Repair
echo ============================================================
echo Patch folder : %PATCH_DIR%
echo Project root : %PROJECT_ROOT%
echo.
echo Tutup WebUI, OCR, Audio Mode, dan seluruh proses Python ORT.
echo.

"%PY_EXE%" "%PATCH_DIR%\APPLY_ORT_V9_0_5_R3_PROVIDER_REPAIR.py" --project-root "%PROJECT_ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Patch gagal dengan exit code %RC%.
  pause
  exit /b %RC%
)

echo.
echo Patch berhasil. Buka Start WebUI.bat.
echo Jalankan setup Reazon CPU terlebih dahulu, kemudian CUDA.
echo Model yang sudah diunduh akan digunakan kembali.
pause
exit /b 0
