@echo off
setlocal
chcp 65001 >nul
title ORT v9.0.5 R5-F1 - Complete Utterance Streaming Fix

echo ============================================================
echo  ORT v9.0.5 R5-F1 - Complete Utterance Streaming Fix
echo ============================================================
echo.
echo Tutup WebUI dan Audio Lab sebelum melanjutkan.
echo Paket ini tidak mengunduh ulang model.
echo.

set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "CPU_PYTHON=%ROOT%ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"

if not exist "%CPU_PYTHON%" (
    echo [ERROR] Runtime CPU tidak ditemukan:
    echo %CPU_PYTHON%
    echo Ekstrak ZIP ini langsung ke root proyek ORT.
    pause
    exit /b 1
)

"%CPU_PYTHON%" "%ROOT%APPLY_ORT_V9_0_5_R5_F1_COMPLETE_UTTERANCE_FIX.py" "%ROOT%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo FIX R5-F1: GAGAL dengan exit code %EXIT_CODE%
    echo Source asli otomatis dipulihkan jika patch sempat diterapkan.
) else (
    echo FIX R5-F1: PASS
    echo Jalankan kembali Start WebUI.bat.
)
echo.
pause
exit /b %EXIT_CODE%
