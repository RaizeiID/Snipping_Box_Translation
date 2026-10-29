@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_APP=%~dp0ORT_App"
if not exist "%ORT_APP%\Start_ORT_Translation.bat" set "ORT_APP=%~dp0ORT\runtime_app"
if not exist "%ORT_APP%\Start_ORT_Translation.bat" (
  echo [ORT] Installer runtime tidak ditemukan.
  echo Jalankan "Repair Struktur ORT.bat" atau periksa kelengkapan paket aplikasi.
  pause
  exit /b 2
)
echo ============================================================
echo  ORT - Instalasi Pertama / Setup Runtime dan Dependensi
echo ============================================================
echo Siapkan Python 3 dan koneksi internet untuk mengunduh dependensi.
echo Pilih [1] ORT_Runtime pada menu berikut untuk lokasi rekomendasi.
echo Setup menyiapkan environment Python, PyTorch, dan dependensi dasar.
echo Setelah selesai, WebUI akan dijalankan.
echo Model OCR/terjemahan/provider disiapkan sesuai pilihan melalui WebUI.
echo Untuk pemakaian berikutnya, cukup buka "Start WebUI.bat".
echo.
call "%ORT_APP%\Start_ORT_Translation.bat"
set "ORT_RC=%ERRORLEVEL%"
if not "%ORT_RC%"=="0" (
  echo [ORT] Setup atau aplikasi berhenti dengan kode %ORT_RC%. Periksa pesan di atas.
  pause
)
endlocal & exit /b %ORT_RC%