@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0ORT\runtime_app"
echo [ORT v8.8.1] Membuka WebUI dari struktur baru: %CD%
call "Start_ORT_Translation.bat"
endlocal
