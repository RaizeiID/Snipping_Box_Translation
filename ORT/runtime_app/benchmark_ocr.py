"""Safe v7.9 OCR readiness benchmark.

This does not capture the screen. It checks OCR dependencies and writes status/benchmark_ocr.json.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
from status_manager import write_status
BASE_DIR = Path(__file__).resolve().parent

def main() -> int:
    data = {
        "version": "v7.9",
        "easyocr_installed": importlib.util.find_spec("easyocr") is not None,
        "mss_installed": importlib.util.find_spec("mss") is not None,
        "opencv_installed": importlib.util.find_spec("cv2") is not None,
        "requested_engine": os.environ.get("ORT_BOOT_ENGINE", "hybrid"),
        "ocr_resolution": os.environ.get("ORT_OCR_RESOLUTION_PERCENT", "-"),
        "note": "Readiness check only; run real game sessions for true OCR ms.",
    }
    write_status("benchmark_ocr", data, BASE_DIR)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
