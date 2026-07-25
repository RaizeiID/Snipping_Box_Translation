from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SETUP = APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py"
WEBUI = APP_ROOT / "webui.py"


def main() -> int:
    py_compile.compile(str(SETUP), doraise=True)
    py_compile.compile(str(WEBUI), doraise=True)
    setup_text = SETUP.read_text(encoding="utf-8")
    webui_text = WEBUI.read_text(encoding="utf-8")

    required_setup = [
        '"HF_HUB_DOWNLOAD_TIMEOUT", "120"',
        '"HF_HUB_ETAG_TIMEOUT", "30"',
        '"HF_HUB_DISABLE_XET", "1"',
        '"max_workers": 1',
        'def _run_with_retry(',
        '"download_retry"',
        '"cache_reuse"',
        '"runtime_reuse"',
        'progress_hook=persist_partial',
        '"download_resumable": True',
    ]
    missing_setup = [token for token in required_setup if token not in setup_text]
    required_webui = [
        'elif kind == "download_retry":',
        'elif kind == "cache_reuse":',
        'elif kind == "runtime_reuse":',
        'elif kind == "hf_auth":',
        'STATUS PEMULIHAN: file yang sudah selesai tetap tersimpan di cache.',
    ]
    missing_webui = [token for token in required_webui if token not in webui_text]

    result = subprocess.run(
        [sys.executable, str(SETUP), "--self-test"],
        cwd=str(APP_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    self_test_passed = result.returncode == 0 and '"hf_single_worker_retry": "PASS"' in result.stdout

    errors = []
    if missing_setup:
        errors.append("setup missing: " + ", ".join(missing_setup))
    if missing_webui:
        errors.append("webui missing: " + ", ".join(missing_webui))
    if not self_test_passed:
        errors.append("setup self-test failed")

    payload = {
        "passed": not errors,
        "version": "v9.0.4-R5",
        "single_worker_hf_metadata": not missing_setup,
        "exponential_retry": "PASS" if "def _run_with_retry(" in setup_text else "FAIL",
        "cache_resume": "PASS" if '"cache_reuse"' in setup_text else "FAIL",
        "partial_manifest": "PASS" if "progress_hook=persist_partial" in setup_text else "FAIL",
        "runtime_reinstall_skip": "PASS" if '"runtime_reuse"' in setup_text else "FAIL",
        "ui_retry_transparency": "PASS" if not missing_webui else "FAIL",
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
