@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0ORT\runtime_app"
echo [ORT v8.8.1] Menjalankan ORT memakai runtime terakhir.
echo Jika runtime belum dipilih, jalankan START_HERE.bat lalu pilih Setup / pilih Runtime Python.
call "RUNTIME.bat"
endlocal
