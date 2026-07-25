@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem Normalize project root without a trailing backslash. A trailing backslash
rem immediately before a quote can become a literal quote in Python argv.
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
cd /d "%ROOT%"

 echo ============================================================
 echo  ORT v9.0.4 R5 F1 - Project Root Quoting Repair
 echo ============================================================
 echo Project root: %CD%
 echo.

set "PYTHON=%ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" "%ROOT%\ORT\maintenance\apply_v9_0_4_r5_f1_project_root_repair.py" --project-root "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Hotfix gagal dengan exit code %RC%.
  pause
  exit /b %RC%
)

echo.
echo ORT v9.0.4 R5 F1 berhasil diterapkan.
pause
exit /b 0
