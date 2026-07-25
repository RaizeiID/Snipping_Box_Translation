@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
for %%I in ("%~dp0.") do set "ORT_ROOT=%%~fI"
set "MIGRATOR=%ORT_ROOT%\ORT_App\tools\migrate_v9_structure.py"
if not exist "%MIGRATOR%" set "MIGRATOR=%ORT_ROOT%\ORT\runtime_app\tools\migrate_v9_structure.py"
if not exist "%MIGRATOR%" (
  echo [ORT v9.0.5] Migrator tidak ditemukan. Terapkan ulang patch v9.0.5.
  pause
  exit /b 2
)
set "PY_EXE=%ORT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if exist "%PY_EXE%" (
  set PY_CMD="%PY_EXE%"
  goto run
)
where py >nul 2>nul && set "PY_CMD=py -3" && goto run
where python >nul 2>nul && set "PY_CMD=python" && goto run
echo Python tidak ditemukan. Install Python 3 atau pertahankan ORT_Runtime.
pause
exit /b 3

:run
echo ============================================================
echo  ORT v9.0.5 R1 - Clean Layout Migration / Repair
echo ============================================================
echo [ORT] Project root: %ORT_ROOT%
%PY_CMD% "%MIGRATOR%" --project-root "%ORT_ROOT%"
if errorlevel 1 (
  echo.
  echo Migrasi gagal. Baca laporan di ORT\logs\migration.
  pause
  exit /b 4
)
echo.
if exist "%ORT_ROOT%\ORT\maintenance\VERIFY_ORT_V9_0_5.bat" call "%ORT_ROOT%\ORT\maintenance\VERIFY_ORT_V9_0_5.bat"
echo.
echo Struktur v9 selesai. Gunakan START_HERE.bat atau Start WebUI.bat.
pause
endlocal
