@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_ROOT=%~dp0"
set "ORT_APP=%ORT_ROOT%ORT_App"
if not exist "%ORT_APP%\webui.py" set "ORT_APP=%ORT_ROOT%ORT\runtime_app"
set "ORT_SUPPORT=%ORT_ROOT%ORT"

:menu
cls
echo ============================================================
echo  ORT Translation v9.0.0 - START HERE
echo ============================================================
echo  [1] Buka WebUI / App Manager
echo  [2] Jalankan OCR menggunakan runtime terakhir
echo  [3] Setup / Repair Runtime Python
echo  [4] Buka folder Logs dan Status
echo  [5] Buka dokumentasi v9.0.0
echo  [6] Export source ringan untuk dibagikan
echo  [7] Verifikasi instalasi v9.0.0
echo  [8] Keluar
echo ============================================================
choice /c 12345678 /n /m "Pilih menu [1-8]: "
if errorlevel 8 goto end
if errorlevel 7 goto verify
if errorlevel 6 goto export
if errorlevel 5 goto docs
if errorlevel 4 goto logs
if errorlevel 3 goto setup
if errorlevel 2 goto ocr
if errorlevel 1 goto webui

:webui
call "%ORT_ROOT%Start WebUI.bat"
goto menu

:ocr
call "%ORT_ROOT%Start OCR.bat"
goto menu

:setup
call "%ORT_ROOT%ORT v9 Setup.bat"
goto menu

:logs
if not exist "%ORT_SUPPORT%\logs" mkdir "%ORT_SUPPORT%\logs" >nul 2>nul
start "" "%ORT_SUPPORT%\logs"
goto menu

:docs
if exist "%ORT_SUPPORT%\docs\README.md" (
  start "" "%ORT_SUPPORT%\docs\README.md"
) else if exist "%ORT_ROOT%README.md" (
  start "" "%ORT_ROOT%README.md"
) else (
  start "" "%ORT_SUPPORT%\docs"
)
goto menu

:export
if exist "%ORT_SUPPORT%\maintenance\EXPORT_ORT_SOURCE_LIGHT.bat" call "%ORT_SUPPORT%\maintenance\EXPORT_ORT_SOURCE_LIGHT.bat"
goto menu

:verify
if exist "%ORT_SUPPORT%\maintenance\VERIFY_ORT_V9_0_0.bat" call "%ORT_SUPPORT%\maintenance\VERIFY_ORT_V9_0_0.bat"
goto menu

:end
endlocal
