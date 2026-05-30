@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "CFG=%CD%\runtime_paths.json"
set "RUNTIME_ROOT="
set "HAS_LAST="

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cfg='%CFG%'; if(Test-Path $cfg){ try{$j=Get-Content $cfg -Raw | ConvertFrom-Json; $rt=[string]$j.runtime_root; if($rt){$py=Join-Path $rt '.venv\Scripts\python.exe'; if(Test-Path $py){Write-Output $rt}} } catch{} }"`) do set "LAST_RUNTIME=%%I"
if defined LAST_RUNTIME set "HAS_LAST=1"

echo ========================================
echo ORT Translation v8.8.1 - Pilih lokasi runtime
 echo [1] Simpan runtime di folder project ini
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
  echo [ORT] Environment lama valid. Dependency base akan dicek ringan.
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
)

echo [ORT] Memastikan Torch stack terkunci v8.8.1
nvidia-smi >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  set "TORCH_REQ=requirements_torch_cu121.txt"
  set "TORCH_CONSTRAINT=constraints_runtime_cu121.txt"
  echo [ORT] NVIDIA GPU terdeteksi. Menggunakan Torch CUDA 12.1 locked stack.
) else (
  set "TORCH_REQ=requirements_torch_cpu.txt"
  set "TORCH_CONSTRAINT=constraints_runtime_cpu.txt"
  echo [ORT] NVIDIA GPU tidak terdeteksi oleh nvidia-smi. Menggunakan Torch CPU locked stack.
)
"%RUNTIME_PY%" -m pip install -r "%CD%\%TORCH_REQ%"

echo [ORT] Memastikan dependency base v8.8.1 dengan constraint Torch...
"%RUNTIME_PY%" -m pip install -r "%CD%\requirements_base.txt" -c "%CD%\%TORCH_CONSTRAINT%"

echo.
echo [ORT] Optional dependency:
echo [1] Lewati optional dependency
echo [2] Install Fast Engine dependency ^(ctranslate2 + sentencepiece^)
echo [3] Install Online Assist dependency
echo [4] Install Fast + Online optional dependency
choice /c 1234 /n /m "Pilihan optional [1/2/3/4]: "
set "OPT=%ERRORLEVEL%"
if "%OPT%"=="2" "%RUNTIME_PY%" -m pip install -r "%CD%\requirements_fast_optional.txt"
if "%OPT%"=="3" "%RUNTIME_PY%" -m pip install -r "%CD%\requirements_online_optional.txt"
if "%OPT%"=="4" (
  "%RUNTIME_PY%" -m pip install -r "%CD%\requirements_fast_optional.txt"
  "%RUNTIME_PY%" -m pip install -r "%CD%\requirements_online_optional.txt"
)

set "ORT_RUNTIME_ROOT=%RUNTIME_ROOT%"
echo.
echo [ORT] Menjalankan ORT Translation v8.8.1
echo [ORT] Clean launcher aktif v8.8.1: locked Torch stack, Fast CT2 status, app/, status/, runtime_bridge.py.
echo [ORT] Web akan dibuka sekali oleh server. Jika belum muncul, buka manual: http://127.0.0.1:7860
echo.
"%RUNTIME_PY%" "%CD%\webui.py"
echo.
echo [ORT] WebUI berhenti atau terjadi error.
pause

:end
endlocal
