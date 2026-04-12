@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "CFG=%CD%\runtime_paths.json"
set "RUNTIME_ROOT="
set "HAS_LAST="

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cfg='%CFG%'; if(Test-Path $cfg){ try{$j=Get-Content $cfg -Raw | ConvertFrom-Json; $rt=[string]$j.runtime_root; if($rt){$py=Join-Path $rt '.venv\Scripts\python.exe'; if(Test-Path $py){Write-Output $rt}} } catch{} }"`) do set "LAST_RUNTIME=%%I"
if defined LAST_RUNTIME set "HAS_LAST=1"

echo ========================================
echo ORT Translation v6.5 - Pilih lokasi simpan runtime
 echo [1] Simpan di folder project ini
 echo [2] Pilih folder custom untuk runtime/download
if defined HAS_LAST echo [3] Gunakan runtime terakhir yang sudah tersedia
 echo ========================================
if defined HAS_LAST (
  choice /c 123 /n /m "Masukkan pilihan [1/2/3]: "
) else (
  choice /c 12 /n /m "Masukkan pilihan [1/2]: "
)
set "SEL=%ERRORLEVEL%"
if defined HAS_LAST (
  if "%SEL%"=="3" goto use_last
)
if "%SEL%"=="2" goto pick_custom
if "%SEL%"=="1" goto use_local

goto end

:use_local
set "RUNTIME_ROOT=%CD%\_runtime"
goto write_cfg

:pick_custom
for /f "usebackq delims=" %%I in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $f=New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description='Pilih folder custom untuk runtime/download'; if($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$p=$f.SelectedPath; if((Split-Path $p -Leaf) -ieq 'ORT_Runtime'){$p}else{Join-Path $p 'ORT_Runtime'}}"`) do set "RUNTIME_ROOT=%%I"
if not defined RUNTIME_ROOT (
  echo Tidak ada folder yang dipilih.
  pause
  goto end
)
goto write_cfg

:use_last
set "RUNTIME_ROOT=%LAST_RUNTIME%"
goto write_cfg

:write_cfg
if not exist "%RUNTIME_ROOT%" mkdir "%RUNTIME_ROOT%" >nul 2>&1
set "RUNTIME_PY=%RUNTIME_ROOT%\.venv\Scripts\python.exe"
if exist "%RUNTIME_PY%" (
  set "VALID=true"
) else (
  set "VALID=false"
)
if /I "%RUNTIME_ROOT%"=="%CD%\_runtime" (
  set "STORAGE=local"
) else (
  set "STORAGE=custom"
)
powershell -NoProfile -Command "$cfg='%CFG%'; $obj=[ordered]@{runtime_root='%RUNTIME_ROOT%'; project_root='%CD%'; runtime_python='%RUNTIME_PY%'; storage_mode='%STORAGE%'; last_runtime_valid=[bool]::Parse('%VALID%')}; $obj | ConvertTo-Json | Set-Content -Path $cfg -Encoding UTF8"

echo.
if exist "%RUNTIME_PY%" (
  echo [ORT] Folder runtime lama terdeteksi.
  echo [ORT] Environment lama valid dan kompatibel. Tidak perlu unduh ulang.
  echo [ORT] Menggunakan runtime lama. Install dependency dilewati.
) else (
  echo [ORT] Runtime root: %RUNTIME_ROOT%
  echo [ORT] Membuat virtual environment di runtime root...
  py -3 -m venv "%RUNTIME_ROOT%\.venv" 2>nul || python -m venv "%RUNTIME_ROOT%\.venv"
  if not exist "%RUNTIME_PY%" (
    echo [ORT] Gagal membuat runtime Python: %RUNTIME_PY%
    pause
    goto end
  )
  "%RUNTIME_PY%" -m pip install --upgrade pip
  "%RUNTIME_PY%" -m pip install -r "%CD%\requirements_v6_2.txt"
)
set "ORT_RUNTIME_ROOT=%RUNTIME_ROOT%"
echo.
echo [ORT] Menjalankan ORT Translation v6.5...
echo [ORT] Web akan dibuka sekali oleh server. Jika belum muncul, buka manual: http://127.0.0.1:7860
echo.
"%RUNTIME_PY%" "%CD%\webui.py"
echo.
echo [ORT] WebUI berhenti atau terjadi error.
pause

:end
endlocal
