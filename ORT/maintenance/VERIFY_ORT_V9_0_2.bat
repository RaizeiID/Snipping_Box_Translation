@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONLEGACYWINDOWSSTDIO=0"
for %%I in ("%~dp0..\..\.") do set "ORT_ROOT=%%~fI"
set "ORT_APP=%ORT_ROOT%\ORT_App"
if not exist "%ORT_APP%\tools\verify_v9_0_0_install.py" set "ORT_APP=%ORT_ROOT%\ORT\runtime_app"
set "PY_EXE=%ORT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if exist "%PY_EXE%" goto run_venv
where py >nul 2>nul
if not errorlevel 1 goto run_py
where python >nul 2>nul
if not errorlevel 1 goto run_python
echo Python tidak ditemukan.
pause
exit /b 2
:run_venv
"%PY_EXE%" "%ORT_APP%\tools\verify_v9_0_0_install.py" --project-root "%ORT_ROOT%"
goto done
:run_py
py -3 "%ORT_APP%\tools\verify_v9_0_0_install.py" --project-root "%ORT_ROOT%"
goto done
:run_python
python "%ORT_APP%\tools\verify_v9_0_0_install.py" --project-root "%ORT_ROOT%"
:done
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
  echo.
  echo Validasi ORT v9.0.2 berhasil.
) else (
  echo.
  echo Validasi ORT v9.0.2 gagal. Baca errors di atas.
)
pause
endlocal & exit /b %RC%
