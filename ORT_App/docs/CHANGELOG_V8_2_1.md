# ORT Translation v8.2.1

## Fixed
- Fixed v8.2 Interval mode holding forever at `TYPING:text_changed_wait_stable`.
- Added bounded max-wait commit for growing/typing dialog text.
- Kept growing OCR text under one candidate window instead of resetting the stable timer on every frame.
- Allowed Fast GFL2 interval floor to go down to 45ms when requested by WebUI/launcher.

## Notes
- `AUTO_GPU -> CPU (no GPU detected)` means the runtime Python environment does not expose CUDA to Torch/EasyOCR. Install/Repair GPU/Torch CUDA is still required for GPU OCR.
