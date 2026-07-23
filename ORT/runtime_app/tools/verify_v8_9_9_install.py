#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
EXPECTED = "v8.9.9"


def read_version(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception:
        return ""


def main() -> int:
    versions = {
        "root": read_version(PROJECT_ROOT / "VERSION.txt"),
        "ortcore": read_version(ROOT / "ORTCORE_VERSION.txt"),
        "titancore": read_version(ROOT / "TITANCORE_VERSION.txt"),
    }
    required = [
        ROOT / "build_info.py",
        ROOT / "launcher_backend.py",
        ROOT / "webui.py",
        ROOT / "audio_main.py",
        ROOT / "audio_realtime_local_sidecar.py",
        ROOT / "app" / "audio" / "cloud_streaming.py",
        ROOT / "tools" / "install_japanese_specialist_v8_9_9.py",
        ROOT / "tools" / "check_audio_gpu_v8_9_9.py",
        ROOT / "tools" / "v8_9_9_safe_language_integration_test.py",
        PROJECT_ROOT / "INSTALL_JAPANESE_SPECIALIST.bat",
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.is_file()]
    mismatches = {key: value for key, value in versions.items() if value != EXPECTED}
    test = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "v8_9_9_safe_language_integration_test.py")],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(test.stdout[test.stdout.find("{"):])
    except Exception:
        payload = {"status": "FAIL", "output": test.stdout[-4000:]}
    passed = not missing and not mismatches and test.returncode == 0 and payload.get("status") == "PASS"
    report = {
        "passed": passed,
        "expected": EXPECTED,
        "versions": versions,
        "missing": missing,
        "mismatches": mismatches,
        "integration_test": payload,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if passed:
        print("\nORT v8.9.9 siap. Hybrid harus mempertahankan Kotoba pada CPU ketika CUDA tidak siap.")
    else:
        print("\nINSTALASI BELUM KONSISTEN. Tutup seluruh proses ORT, ekstrak ulang patch, dan pilih Replace/Timpa semua.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
