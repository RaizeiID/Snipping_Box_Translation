@echo off
chcp 65001 >nul
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "ORT_ROOT=%%~fI"
set "ORT_APP=%ORT_ROOT%\ORT_App"
if not exist "%ORT_APP%\tools\export_source_light_v9.py" set "ORT_APP=%ORT_ROOT%\ORT\runtime_app"
set "PY_EXE=%ORT_ROOT%\ORT_Runtime\.venv\Scripts\python.exe"
if exist "%PY_EXE%" (
  set PY_CMD="%PY_EXE%"
  goto run
)
where py >nul 2>nul && set "PY_CMD=py -3" && goto run
where python >nul 2>nul && set "PY_CMD=python" && goto run
echo Python tidak ditemukan.
pause
exit /b 2
:run
%PY_CMD% "%ORT_APP%\tools\export_source_light_v9.py" --project-root "%ORT_ROOT%"
echo.
echo ZIP source ringan berada di ORT\exports.
pause
endlocal
