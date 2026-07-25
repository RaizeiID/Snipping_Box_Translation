@echo off
chcp 65001 >nul
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "ORT_ROOT=%%~fI"
set "PY_EXE=%ORT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
set "VERIFY_PY=%ORT_ROOT%\ORT_App\tools\verify_v9_0_0_install.py"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if exist "%PY_EXE%" (
  "%PY_EXE%" "%VERIFY_PY%" --project-root "%ORT_ROOT%"
) else (
  py -3 "%VERIFY_PY%" --project-root "%ORT_ROOT%"
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
