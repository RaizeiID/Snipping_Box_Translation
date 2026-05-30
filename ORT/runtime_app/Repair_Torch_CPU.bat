\
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY=%CD%\_runtime\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ORT v8.3] Runtime Python tidak ditemukan: %PY%
  pause
  exit /b 1
)
echo [ORT v8.3] Repair Torch CPU stack...
"%PY%" -m pip uninstall -y torch torchvision torchaudio
"%PY%" -m pip install --no-cache-dir --force-reinstall -r "%CD%\requirements_torch_cpu.txt"
"%PY%" -c "import torch, torchvision; print('torch=', torch.__version__); print('torchvision=', torchvision.__version__); print('cuda=', torch.cuda.is_available())"
"%PY%" -c "import easyocr; print('easyocr import OK')"
echo [ORT v8.3] CPU repair selesai.
pause
endlocal
