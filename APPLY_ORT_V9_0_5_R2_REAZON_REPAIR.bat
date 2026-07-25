@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
for %%I in ("%~dp0.") do set "PATCH_DIR=%%~fI"
set "ROOT="
if exist "%PATCH_DIR%\VERSION.txt" if exist "%PATCH_DIR%\ORT_App" set "ROOT=%PATCH_DIR%"
if not defined ROOT if exist "%PATCH_DIR%\..\VERSION.txt" if exist "%PATCH_DIR%\..\ORT_App" for %%I in ("%PATCH_DIR%\..") do set "ROOT=%%~fI"
if not defined ROOT (
 echo Project root ORT tidak ditemukan.
 echo Ekstrak folder patch ke dalam root ORT, lalu jalankan BAT ini.
 pause
 exit /b 3
)
set "PY=%ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%ROOT%\ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
if not exist "%PY%" (
 where py >nul 2>nul && set "PY=py -3"
)
echo Project root: %ROOT%
"%PY%" "%PATCH_DIR%\APPLY_ORT_V9_0_5_R2_REAZON_REPAIR.py" --project-root "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
 echo Patch gagal dengan exit code %RC%.
 pause
 exit /b %RC%
)
echo.
echo Patch aktif. Buka Start WebUI.bat lalu ulangi setup CPU terlebih dahulu.
pause
