#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
EXPECTED = "v8.9.8"


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
        ROOT / "tools" / "setup_japanese_specialist_v8_9_8.py",
        ROOT / "tools" / "check_audio_gpu_v8_9_8.py",
        ROOT / "tools" / "v8_9_8_multilingual_instant_integration_test.py",
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.is_file()]
    mismatches = {key: value for key, value in versions.items() if value != EXPECTED}
    self_test = subprocess.run(
        [sys.executable, str(ROOT / "audio_realtime_local_sidecar.py"), "--self-test-json"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    try:
        self_test_payload = json.loads(self_test.stdout)
    except Exception:
        self_test_payload = {"passed": False, "output": self_test.stdout[-2000:]}
    passed = not missing and not mismatches and self_test.returncode == 0 and bool(self_test_payload.get("passed"))
    report = {
        "passed": passed,
        "expected": EXPECTED,
        "versions": versions,
        "missing": missing,
        "mismatches": mismatches,
        "realtime_self_test": self_test_payload,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if passed:
        print("\nORT v8.9.8 siap. Log Audio harus memperlihatkan source_lang, bridge=en, dan task translate/transcribe.")
    else:
        print("\nINSTALASI BELUM KONSISTEN. Tutup semua proses ORT, ekstrak ulang patch, dan pilih Replace/Timpa semua.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
