@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "CFG=%CD%\runtime_paths.json"
set "RUNTIME_ROOT="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cfg='%CFG%'; if(Test-Path $cfg){ try{$j=Get-Content $cfg -Raw | ConvertFrom-Json; $rt=[string]$j.runtime_root; if($rt){$py=Join-Path $rt '.venv\Scripts\python.exe'; if(Test-Path $py){Write-Output $rt}} } catch{} }"`) do set "RUNTIME_ROOT=%%I"
if not defined RUNTIME_ROOT (
  echo [ORT] Runtime terakhir belum valid:  \.venv\Scripts\python.exe
  echo [ORT] Jalankan Start_ORT_Translation.bat dan pilih runtime yang benar.
  pause
  goto end
)
set "RUNTIME_PY=%RUNTIME_ROOT%\.venv\Scripts\python.exe"
if not exist "%RUNTIME_PY%" (
  echo [ORT] Runtime terakhir belum valid: %RUNTIME_PY%
  echo [ORT] Jalankan Start_ORT_Translation.bat dan pilih runtime yang benar.
  pause
  goto end
)
set "ORT_RUNTIME_ROOT=%RUNTIME_ROOT%"
echo [ORT] Menggunakan runtime terakhir: %RUNTIME_ROOT%
"%RUNTIME_PY%" "%CD%\webui.py"
:end
endlocal
