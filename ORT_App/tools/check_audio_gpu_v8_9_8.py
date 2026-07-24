#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import json
import os
import platform
import sys
from pathlib import Path

DLLS = ("cublas64_12.dll", "cudnn64_9.dll")


def load_dll(name: str) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Pemeriksaan DLL ini ditujukan untuk Windows."
    try:
        ctypes.WinDLL(name)
        return True, "loaded"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    dlls = {name: dict(zip(("available", "detail"), load_dll(name))) for name in DLLS}
    ct2 = {"available": False, "cuda_device_count": 0, "detail": ""}
    try:
        import ctranslate2
        ct2["available"] = True
        try:
            ct2["cuda_device_count"] = int(ctranslate2.get_cuda_device_count())
        except Exception as exc:
            ct2["detail"] = str(exc)
    except Exception as exc:
        ct2["detail"] = str(exc)

    passed = bool(ct2["available"] and ct2["cuda_device_count"] > 0 and all(v["available"] for v in dlls.values()))
    report = {
        "passed": passed,
        "python": sys.executable,
        "platform": platform.platform(),
        "path_entries": len(os.environ.get("PATH", "").split(os.pathsep)),
        "dlls": dlls,
        "ctranslate2": ct2,
        "recommendation": (
            "GPU Audio siap untuk Faster-Whisper/Kotoba."
            if passed
            else "Pasang cuBLAS CUDA 12 dan cuDNN 9 yang cocok, pastikan folder DLL berada di PATH, lalu buka ulang ORT."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
