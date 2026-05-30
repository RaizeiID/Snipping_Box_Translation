@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "CONFIG_FILE=%~dp0runtime_paths.json"

echo ========================================
echo ORT Translation v8.8.1 - Runtime Cleaner
echo ========================================
echo Tool ini hanya membersihkan runtime/cache sementara.
echo Folder project TIDAK akan dihapus.
echo.

if not exist "%CONFIG_FILE%" (
  echo runtime_paths.json tidak ditemukan. Tidak ada runtime eksternal yang perlu dibersihkan.
  goto clean_local
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$j=Get-Content -Raw '%CONFIG_FILE%' ^| ConvertFrom-Json; [Console]::WriteLine($j.runtime_root)"`) do set "ORT_RUNTIME_ROOT=%%I"
if defined ORT_RUNTIME_ROOT (
  echo Runtime root terdeteksi: %ORT_RUNTIME_ROOT%
  choice /c YN /n /m "Hapus runtime root tersebut? [Y/N]: "
  if errorlevel 2 goto clean_local
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Test-Path '%ORT_RUNTIME_ROOT%' -and (Test-Path '%ORT_RUNTIME_ROOT%\ort_runtime.marker')){Remove-Item -LiteralPath '%ORT_RUNTIME_ROOT%' -Recurse -Force -ErrorAction SilentlyContinue; Write-Output 'Runtime root dihapus.'} else {Write-Output 'Marker runtime tidak ditemukan. Penghapusan dibatalkan demi keamanan.'}"
)

:clean_local
echo.
echo Membersihkan file runtime sementara...
del /f /q "%CONFIG_FILE%" >nul 2>nul
del /f /q "%~dp0runtime_stop_request.json" >nul 2>nul
del /f /q "%~dp0status\*.tmp" >nul 2>nul
for /d %%D in ("%~dp0__pycache__" "%~dp0app\__pycache__" "%~dp0app\*\__pycache__" "%~dp0tools\__pycache__") do if exist "%%~fD" rmdir /s /q "%%~fD" >nul 2>nul

echo Selesai. Project tidak dihapus.
pause
