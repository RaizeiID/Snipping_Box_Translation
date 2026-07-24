@echo off
setlocal
cd /d "%~dp0"
set "VERIFY_SCRIPT=%~dp0ORT\runtime_app\tools\verify_v8_9_7_install.py"
set "AUDIO_PY=%~dp0ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"

if exist "%AUDIO_PY%" (
  "%AUDIO_PY%" "%VERIFY_SCRIPT%"
  goto :done
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%VERIFY_SCRIPT%"
  goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python "%VERIFY_SCRIPT%"
  goto :done
)

echo Python tidak ditemukan. Jalankan Siapkan Audio terlebih dahulu atau jalankan:
echo "ORT_Runtime\audio_cpu\.venv\Scripts\python.exe" "%VERIFY_SCRIPT%"
exit /b 1

:done
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%
