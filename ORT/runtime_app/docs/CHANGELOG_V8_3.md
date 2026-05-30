# ORT Translation v8.3 - Runtime Repair & Fast CT2 Setup

Base: v8.2.1  
Type: patch / runtime repair / Fast CT2 activation preparation

## Added
- Locked Torch runtime files:
  - `requirements_torch_cu121.txt`
  - `requirements_torch_cpu.txt`
  - `constraints_runtime_cu121.txt`
  - `constraints_runtime_cpu.txt`
- Repair scripts:
  - `Repair_Torch_CUDA.bat`
  - `Repair_Torch_CPU.bat`
  - `Validate_Runtime_GPU.bat`
- Fast CT2 folder README generation through Fast Engine Setup Wizard.
- Fast CT2 candidate folder validation and missing-file report.
- OCR region status report when snipping region is locked.
- Story voice-hold tuning for GFL2 Fast Interval mode.

## Changed
- `Start_ORT_Translation.bat` now installs a locked Torch stack before base requirements.
- `requirements_base.txt` no longer lets pip freely choose the Torch stack.
- `fast_model_manager.py` now reports ACTIVE/FALLBACK_ARGOS with model folder details and missing files.
- `translation_engine.py` uses FastModelManager-detected CT2 model folder.
- `launcher_backend.py` propagates Fast CT2 model path into the runtime environment.
- `TITANMAIN.py` reports v8.3 boot/status and OCR region quality warning.
- `webui.py` labels updated to v8.3.

## Fixed / Prevented
- Prevents recurrence of broken Torch/Torchvision mix such as `torchvision::nms does not exist`.
- Makes Fast CT2 fallback reason more explicit.
- Reduces repeated processing for voiced story where the same text remains on screen while voice continues.

## Known Issues
- Fast CT2 still requires actual converted CT2 model files; dependency alone is not enough.
- Automatic CT2 model download/convert is not included in this patch.
- OCR accuracy/crop diagnostics will be expanded later in v8.4.

## Next Recommendations
- Add v8.4 Diagnose & Repair Center in Runtime & Tools.
- Add OCR Test Panel and Smart Region Quality Assistant.
- Add Fast CT2 model import/convert workflow if model source is available.
