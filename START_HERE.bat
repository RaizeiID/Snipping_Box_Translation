@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "ORT_ROOT=%~dp0"
set "ORT_RUNTIME=%ORT_ROOT%ORT\runtime_app"

:menu
cls
echo ============================================================
echo  ORT Translation v8.8.1 - START HERE
echo ============================================================
echo  [1] Buka WebUI / App Manager
echo  [2] Jalankan OCR Overlay menggunakan runtime terakhir
echo  [3] Setup / pilih Runtime Python
echo  [4] Buka folder logs
echo  [5] Buka README
echo  [6] Keluar
echo ============================================================
choice /c 123456 /n /m "Pilih menu [1-6]: "
if errorlevel 6 goto end
if errorlevel 5 goto readme
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
pushd "%ORT_RUNTIME%"
call "Start_ORT_Translation.bat"
popd
goto menu

:logs
if not exist "%ORT_RUNTIME%\logs" mkdir "%ORT_RUNTIME%\logs" >nul 2>nul
start "" "%ORT_RUNTIME%\logs"
goto menu

:readme
start "" "%ORT_ROOT%README.md"
goto menu

:end
endlocal
