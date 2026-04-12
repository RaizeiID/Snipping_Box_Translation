@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "CONFIG_FILE=%~dp0runtime_paths.json"
if not exist "%CONFIG_FILE%" (
  echo runtime_paths.json tidak ditemukan.
  pause
  exit /b 1
)
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$j=Get-Content -Raw '%CONFIG_FILE%' ^| ConvertFrom-Json; [Console]::WriteLine($j.runtime_root)"`) do set "ORT_RUNTIME_ROOT=%%I"
if defined ORT_RUNTIME_ROOT (
  echo Menghapus runtime root: %ORT_RUNTIME_ROOT%
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Test-Path '%ORT_RUNTIME_ROOT%' -and (Test-Path '%ORT_RUNTIME_ROOT%\ort_runtime.marker')){Remove-Item -LiteralPath '%ORT_RUNTIME_ROOT%' -Recurse -Force -ErrorAction SilentlyContinue}"
)
del /f /q "%CONFIG_FILE%" >nul 2>nul
set "PARENT=%~dp0"
set "KILLER=%TEMP%\ort_cleanup_%RANDOM%.cmd"
> "%KILLER%" echo @echo off
>> "%KILLER%" echo timeout /t 2 /nobreak ^>nul
>> "%KILLER%" echo rmdir /s /q "%PARENT%"
>> "%KILLER%" echo del /f /q "%%~f0"
start "" cmd /c "%KILLER%"
exit
