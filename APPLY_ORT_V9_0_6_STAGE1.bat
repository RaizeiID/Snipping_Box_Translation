@echo off
setlocal
chcp 65001 >nul
title ORT v9.0.6 Stage 1 - Domain Registry

echo ============================================================
echo  ORT v9.0.6 Stage 1 - Domain Registry and Audit Foundation
echo ============================================================
echo.
echo Tutup WebUI dan Audio Lab sebelum melanjutkan.
echo Tidak ada model yang diunduh atau dilatih pada tahap ini.
echo.

set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "CPU_PYTHON=%ROOT%ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"

if not exist "%CPU_PYTHON%" (
    echo [ERROR] Runtime CPU tidak ditemukan:
    echo %CPU_PYTHON%
    pause
    exit /b 1
)

"%CPU_PYTHON%" "%ROOT%APPLY_ORT_V9_0_6_STAGE1.py" "%ROOT%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo UPDATE v9.0.6 STAGE 1: PASS
) else (
    echo UPDATE v9.0.6 STAGE 1: GAGAL
    echo Source otomatis dipulihkan jika patch sempat diterapkan.
)
echo.
pause
exit /b %EXIT_CODE%
