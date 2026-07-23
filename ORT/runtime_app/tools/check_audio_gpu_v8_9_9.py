#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from install_audio_gpu_v8_9_9_r2 import _runtime_paths, _validate_gpu, _write_marker


def main() -> int:
    paths = _runtime_paths()
    try:
        payload = _validate_gpu(paths["model_root"], "small")
        marker = _write_marker(paths, payload)
        report = {
            "passed": True,
            "gpu_python": sys.executable,
            "model": payload.get("model"),
            "device": payload.get("device"),
            "compute_type": payload.get("compute_type"),
            "load_ms": payload.get("load_ms"),
            "warmup_ms": payload.get("warmup_ms"),
            "steady_ms": payload.get("steady_ms"),
            "validation_marker": str(marker),
            "cuda": payload.get("cuda"),
            "recommendation": "GPU Audio siap. Pilih GPU atau Hybrid lalu gunakan profil Normal.",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "passed": False,
            "gpu_python": sys.executable,
            "error": str(exc),
            "recommendation": "Jalankan INSTALL_AUDIO_GPU_V8_9_9_R2.bat, lalu buka ulang WebUI.",
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
