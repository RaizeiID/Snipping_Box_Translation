@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_APP=%~dp0ORT_App"
if not exist "%ORT_APP%\webui.py" set "ORT_APP=%~dp0ORT\runtime_app"
if not exist "%ORT_APP%\webui.py" (
  echo [ORT v9.0.0] Folder aplikasi tidak ditemukan.
  echo Jalankan "ORT v9 Setup.bat" untuk migrasi/repair struktur.
  pause
  exit /b 2
)
echo [ORT v9.0.0] App root: %ORT_APP%
call "%ORT_APP%\RUNTIME.bat"
set "ORT_RC=%ERRORLEVEL%"
if "%ORT_RC%"=="2" (
  echo [ORT] Runtime terakhir belum siap. Membuka setup runtime...
  call "%ORT_APP%\Start_ORT_Translation.bat"
)
endlocal
