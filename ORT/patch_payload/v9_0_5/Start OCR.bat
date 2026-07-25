@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_APP=%~dp0ORT_App"
if not exist "%ORT_APP%\RUNTIME.bat" set "ORT_APP=%~dp0ORT\runtime_app"
if not exist "%ORT_APP%\RUNTIME.bat" (
  echo [ORT v9.0.5] Runtime aplikasi tidak ditemukan. Jalankan ORT v9 Setup.bat.
  pause
  exit /b 2
)
echo [ORT v9.0.5] Menjalankan ORT dengan runtime terakhir.
call "%ORT_APP%\RUNTIME.bat"
endlocal
