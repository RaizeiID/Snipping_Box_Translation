@echo off
setlocal EnableExtensions
chcp 65001 >nul
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
echo ============================================================
echo  ORT v9.0.4 R5 F2 - Reazon Direct Manifest Download
echo ============================================================
echo Project root: %ROOT%
echo.
set "PYTHON=%ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
"%PYTHON%" "%ROOT%\ORT\maintenance\apply_v9_0_4_r5_f2_reazon_direct_manifest.py" --project-root "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Hotfix gagal dengan exit code %RC%.
  pause
  exit /b %RC%
)
echo.
echo ORT v9.0.4 R5 F2 berhasil diterapkan.
pause
exit /b 0
