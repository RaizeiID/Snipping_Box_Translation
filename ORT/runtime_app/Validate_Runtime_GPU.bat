\
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY=%CD%\_runtime\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Runtime Python tidak ditemukan: %PY%
  pause
  exit /b 1
)
echo [ORT v8.8.1] Runtime GPU validation
"%PY%" -c "import torch, torchvision; print('torch=', torch.__version__); print('torchvision=', torchvision.__version__); print('cuda=', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA OFF')"
echo.
echo [ORT v8.8.1] EasyOCR import validation
"%PY%" -c "import easyocr, torch; print('easyocr import OK'); print('cuda=', torch.cuda.is_available())"
pause
endlocal
