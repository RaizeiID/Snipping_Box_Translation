@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "APP_ROOT=%CD%"
for %%I in ("%APP_ROOT%\..") do set "APP_PARENT=%%~fI"
for %%I in ("%APP_PARENT%") do set "APP_PARENT_NAME=%%~nxI"
if /I "%APP_PARENT_NAME%"=="ORT" (
  for %%I in ("%APP_PARENT%\..") do set "PROJECT_ROOT=%%~fI"
) else (
  set "PROJECT_ROOT=%APP_PARENT%"
)
set "CFG=%APP_ROOT%\runtime_paths.json"
set "RUNTIME_ROOT="
set "HAS_LAST="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cfg='%CFG%'; if(Test-Path $cfg){ try{$j=Get-Content $cfg -Raw | ConvertFrom-Json; $rt=[string]$j.runtime_root; if($rt){$py=Join-Path $rt '.venv\Scripts\python.exe'; if(Test-Path $py){Write-Output $rt}} } catch{} }"`) do set "LAST_RUNTIME=%%I"
if defined LAST_RUNTIME set "HAS_LAST=1"

echo ========================================
echo ORT Translation v9.0.0 - Runtime Setup
echo Project: %PROJECT_ROOT%
echo [1] Gunakan folder surface ORT_Runtime ^(rekomendasi^)
echo [2] Pilih folder custom untuk runtime/download
if defined HAS_LAST echo [3] Gunakan runtime terakhir yang valid
 echo ========================================
if defined HAS_LAST (
  choice /c 123 /n /m "Masukkan pilihan [1/2/3]: "
) else (
  choice /c 12 /n /m "Masukkan pilihan [1/2]: "
)
set "SEL=%ERRORLEVEL%"
if defined HAS_LAST if "%SEL%"=="3" goto use_last
if "%SEL%"=="2" goto pick_custom
if "%SEL%"=="1" goto use_local
goto end

:use_local
set "RUNTIME_ROOT=%PROJECT_ROOT%\ORT_Runtime"
goto write_cfg

:pick_custom
for /f "usebackq delims=" %%I in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $f=New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description='Pilih lokasi ORT_Runtime'; if($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$p=$f.SelectedPath; if((Split-Path $p -Leaf) -ieq 'ORT_Runtime'){$p}else{Join-Path $p 'ORT_Runtime'}}"`) do set "RUNTIME_ROOT=%%I"
if not defined RUNTIME_ROOT goto end
goto write_cfg

:use_last
set "RUNTIME_ROOT=%LAST_RUNTIME%"
goto write_cfg

:write_cfg
if not exist "%RUNTIME_ROOT%" mkdir "%RUNTIME_ROOT%" >nul 2>&1
set "RUNTIME_PY=%RUNTIME_ROOT%\.venv\Scripts\python.exe"
if exist "%RUNTIME_PY%" (set "VALID=true") else (set "VALID=false")
powershell -NoProfile -Command "$cfg='%CFG%'; $obj=[ordered]@{layout_version=9; app_root='%APP_ROOT%'; project_root='%PROJECT_ROOT%'; runtime_root='%RUNTIME_ROOT%'; runtime_python='%RUNTIME_PY%'; storage_mode='surface_or_custom'; last_runtime_valid=[bool]::Parse('%VALID%')}; $obj | ConvertTo-Json | Set-Content -Path $cfg -Encoding UTF8"

if not exist "%RUNTIME_PY%" (
  echo [ORT] Membuat virtual environment: %RUNTIME_ROOT%
  py -3 -m venv "%RUNTIME_ROOT%\.venv" 2>nul || python -m venv "%RUNTIME_ROOT%\.venv"
)
if not exist "%RUNTIME_PY%" (
  echo [ORT] Gagal membuat runtime Python.
  pause
  exit /b 3
)

"%RUNTIME_PY%" -m pip install --upgrade pip
nvidia-smi >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  set "TORCH_REQ=requirements_torch_cu121.txt"
  set "TORCH_CONSTRAINT=constraints_runtime_cu121.txt"
) else (
  set "TORCH_REQ=requirements_torch_cpu.txt"
  set "TORCH_CONSTRAINT=constraints_runtime_cpu.txt"
)
if exist "%APP_ROOT%\%TORCH_REQ%" "%RUNTIME_PY%" -m pip install -r "%APP_ROOT%\%TORCH_REQ%"
if exist "%APP_ROOT%\requirements_base.txt" "%RUNTIME_PY%" -m pip install -r "%APP_ROOT%\requirements_base.txt" -c "%APP_ROOT%\%TORCH_CONSTRAINT%"

set "ORT_RUNTIME_ROOT=%RUNTIME_ROOT%"
echo [ORT v9.0.0] Menjalankan WebUI.
"%RUNTIME_PY%" "%APP_ROOT%\webui.py"

:end
endlocal
