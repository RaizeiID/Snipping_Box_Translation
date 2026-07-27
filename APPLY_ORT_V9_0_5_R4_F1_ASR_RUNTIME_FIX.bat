@echo off
setlocal
chcp 65001 >nul
title ORT v9.0.5 R4-F1 - ASR Runtime Binding Fix

echo ============================================================
echo  ORT v9.0.5 R4-F1 - ASR Runtime Binding Fix
echo ============================================================
echo.
echo Tutup WebUI dan Audio Lab sebelum melanjutkan.
echo Fix ini tidak mengunduh ulang model.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0APPLY_ORT_V9_0_5_R4_F1_ASR_RUNTIME_FIX.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo FIX: GAGAL dengan exit code %EXIT_CODE%
    echo Source asli otomatis dipulihkan bila perubahan sudah dibuat.
) else (
    echo FIX: PASS
    echo Jalankan kembali Start WebUI.bat dan uji mode CPU lalu Hybrid.
)
echo.
pause
exit /b %EXIT_CODE%
