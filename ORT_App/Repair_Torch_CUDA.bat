\
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY=%CD%\_runtime\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ORT v8.3] Runtime Python tidak ditemukan: %PY%
  echo Jalankan Start_ORT_Translation.bat terlebih dahulu untuk membuat runtime.
  pause
  exit /b 1
)
echo [ORT v8.3] Repair Torch CUDA 12.1 stack...
"%PY%" -m pip uninstall -y torch torchvision torchaudio
echo.
echo [ORT v8.3] Installing locked CUDA stack: torch 2.5.1 / torchvision 0.20.1 / torchaudio 2.5.1 cu121
"%PY%" -m pip install --no-cache-dir --force-reinstall -r "%CD%\requirements_torch_cu121.txt"
echo.
echo [ORT v8.3] Validating Torch/EasyOCR...
"%PY%" -c "import torch, torchvision; print('torch=', torch.__version__); print('torchvision=', torchvision.__version__); print('cuda=', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA OFF')"
"%PY%" -c "import easyocr, torch; print('easyocr import OK'); print('cuda=', torch.cuda.is_available())"
echo.
echo [ORT v8.3] Repair selesai. Jika cuda=True, jalankan ulang ORT.
pause
endlocal
