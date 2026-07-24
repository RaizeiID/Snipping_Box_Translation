@echo off
chcp 65001 >nul
setlocal EnableExtensions

for %%I in ("%~dp0.") do set "ORT_ROOT=%%~fI"
cd /d "%ORT_ROOT%"

set "PATCH_PY=%ORT_ROOT%\ORT\maintenance\apply_v9_0_4_cloud_locked_provider_benchmark.py"
set "PY_EXE=%ORT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONLEGACYWINDOWSSTDIO=0"

echo ============================================================
echo  ORT v9.0.4 - Cloud ^& Locked Provider Benchmark Lab
echo ============================================================
echo Project root: %ORT_ROOT%
echo.

if not exist "%PATCH_PY%" (
  echo Applicator tidak ditemukan: %PATCH_PY%
  pause
  exit /b 2
)

if exist "%PY_EXE%" goto run_venv
where py >nul 2>nul
if not errorlevel 1 goto run_py
where python >nul 2>nul
if not errorlevel 1 goto run_python

echo Python tidak ditemukan.
pause
exit /b 3

:run_venv
echo Python: %PY_EXE%
echo Catatan: verifier memiliki heartbeat dan rollback otomatis. Jangan tekan Ctrl+C selama heartbeat berjalan.
"%PY_EXE%" "%PATCH_PY%" --project-root "%ORT_ROOT%"
goto after_run

:run_py
echo Python: py -3
py -3 "%PATCH_PY%" --project-root "%ORT_ROOT%"
goto after_run

:run_python
echo Python: python
python "%PATCH_PY%" --project-root "%ORT_ROOT%"

:after_run
set "PATCH_EXIT=%ERRORLEVEL%"
if not "%PATCH_EXIT%"=="0" (
  echo.
  echo Update v9.0.4 gagal dengan exit code %PATCH_EXIT%.
  echo Source dipulihkan dari ORT\backups bila backup sudah dibuat.
  pause
  exit /b %PATCH_EXIT%
)

echo.
echo Update ORT v9.0.4 berhasil.
echo Buka Open Architecture Lab, pilih model, tekan Siapkan model yang dipilih, lalu benchmark dan uji runtime.
pause
endlocal
