@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_APP=%~dp0ORT_App"
if not exist "%ORT_APP%\webui.py" set "ORT_APP=%~dp0ORT\runtime_app"
if not exist "%ORT_APP%\webui.py" (
  echo [ORT] Folder aplikasi tidak ditemukan.
  echo Jalankan "Repair Struktur ORT.bat" untuk memeriksa struktur instalasi.
  pause
  exit /b 2
)
if not exist "%ORT_APP%\RUNTIME.bat" (
  echo [ORT] Launcher runtime tidak ditemukan. Periksa kelengkapan paket aplikasi.
  pause
  exit /b 2
)
echo [ORT] Membuka WebUI. Biarkan terminal ini terbuka selama memakai aplikasi.
echo [ORT] Alamat web: http://127.0.0.1:7860
call "%ORT_APP%\RUNTIME.bat"
set "ORT_RC=%ERRORLEVEL%"
if "%ORT_RC%"=="2" (
  echo [ORT] Runtime belum siap. Jalankan "Instalation First.bat" terlebih dahulu.
  pause
) else if not "%ORT_RC%"=="0" (
  echo [ORT] Aplikasi berhenti dengan kode %ORT_RC%. Periksa pesan di atas.
  pause
)
endlocal & exit /b %ORT_RC%