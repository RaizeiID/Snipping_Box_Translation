@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" "%~dp0ORT\runtime_app\tools\verify_v8_9_9_r2_f1_install.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo ORT v8.9.9 R2 F1 tervalidasi.) else (echo Validasi R2 F1 gagal. Terapkan ulang hotfix.)
pause
exit /b %RC%
