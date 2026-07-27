@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

for %%I in ("%~dp0.") do set "PATCH_DIR=%%~fI"
set "PROJECT_ROOT="
if exist "%PATCH_DIR%\VERSION.txt" set "PROJECT_ROOT=%PATCH_DIR%"
if not defined PROJECT_ROOT if exist "%PATCH_DIR%\..\VERSION.txt" for %%I in ("%PATCH_DIR%\..") do set "PROJECT_ROOT=%%~fI"

echo ============================================================
echo  ORT v9.0.5 R1 - Sherpa API Repair
echo ============================================================
echo Patch folder : %PATCH_DIR%
if defined PROJECT_ROOT echo Project root: %PROJECT_ROOT%
echo.

echo Pastikan WebUI, OCR, Audio Mode, dan terminal ORT sudah ditutup.
echo.

set "PYTHON="
if defined PROJECT_ROOT if exist "%PROJECT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe" set "PYTHON=%PROJECT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%PATCH_DIR%\ORT_Runtime\.venv\Scripts\python.exe" set "PYTHON=%PATCH_DIR%\ORT_Runtime\.venv\Scripts\python.exe"
if not defined PYTHON (
  where py >nul 2>nul && set "PYTHON=py -3"
)
if not defined PYTHON (
  where python >nul 2>nul && set "PYTHON=python"
)
if not defined PYTHON (
  echo Python tidak ditemukan.
  pause
  exit /b 3
)

if defined PROJECT_ROOT (
  %PYTHON% "%PATCH_DIR%\ORT\maintenance\apply_v9_0_5_r1_sherpa_api_repair.py" --project-root "%PROJECT_ROOT%"
) else (
  %PYTHON% "%PATCH_DIR%\ORT\maintenance\apply_v9_0_5_r1_sherpa_api_repair.py"
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Patch v9.0.5 R1 gagal dengan exit code %RC%.
  pause
  exit /b %RC%
)

echo.
echo Patch v9.0.5 R1 berhasil diterapkan.
echo Buka Start WebUI.bat dan ulangi Siapkan model yang dipilih.
pause
exit /b 0
