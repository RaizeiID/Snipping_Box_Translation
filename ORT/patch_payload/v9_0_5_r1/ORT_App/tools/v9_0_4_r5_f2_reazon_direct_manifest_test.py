from __future__ import annotations

import ast
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SETUP = APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py"
REGISTRY = APP_ROOT / "app" / "audio" / "asr_provider_registry.py"
ADAPTER = APP_ROOT / "app" / "audio" / "locked_asr_adapter.py"


def main() -> int:
    for path in (SETUP, REGISTRY, ADAPTER):
        py_compile.compile(str(path), doraise=True)
    setup_text = SETUP.read_text(encoding="utf-8")
    registry_text = REGISTRY.read_text(encoding="utf-8")
    adapter_text = ADAPTER.read_text(encoding="utf-8")
    required_setup = [
        'REAZON_REVISION = "291488c8151be24d7da4bf7af26e533fad96e407"',
        'def _download_reazon_static(',
        'def _download_static_file(',
        'headers["Range"]',
        'metadata_preflight=False',
        '"download_strategy": "direct_static_manifest"',
        '_reazon_local_warmup_script(',
        'device=target_device, model_root=model_root',
    ]
    required_registry = [
        'REAZON_LOCAL_DIR = "reazonspeech-k2-v2"',
        'return [root / REAZON_LOCAL_DIR]',
        'File Reazon belum lengkap:',
    ]
    required_adapter = [
        'create_offline_transducer(',
        'decoder-epoch-99-avg-1.int8.onnx',
        'decoder-epoch-99-avg-1.onnx',
        'self.model_path = str(location)',
    ]
    errors = []
    for label, text, tokens in (
        ("setup", setup_text, required_setup),
        ("registry", registry_text, required_registry),
        ("adapter", adapter_text, required_adapter),
    ):
        missing = [token for token in tokens if token not in text]
        if missing:
            errors.append(f"{label} missing: {missing}")
    # Reazon path must not call snapshot dry-run.
    tree = ast.parse(setup_text)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_download_reazon_static")
    segment = ast.get_source_segment(setup_text, function) or ""
    if "snapshot_download" in segment or "dry_run" in segment:
        errors.append("Reazon direct path still uses snapshot/dry-run")
    result = subprocess.run(
        [sys.executable, str(SETUP), "--self-test"], cwd=str(APP_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.stdout.strip(): print(result.stdout.strip())
    if result.stderr.strip(): print(result.stderr.strip())
    if result.returncode != 0 or '"reazon_static_manifest": "PASS"' not in result.stdout:
        errors.append("setup self-test failed")
    payload = {
        "passed": not errors,
        "version": "v9.0.4-R5-F2",
        "snapshot_dry_run_removed_for_reazon": "PASS" if "snapshot_download" not in segment else "FAIL",
        "pinned_static_manifest": "PASS" if "REAZON_FILE_MANIFEST" in setup_text else "FAIL",
        "range_resume": "PASS" if 'headers["Range"]' in setup_text else "FAIL",
        "local_cpu_gpu_load": "PASS" if "create_offline_transducer(" in adapter_text else "FAIL",
        "device_specific_status": "PASS" if "REAZON_DEVICE_FILES" in registry_text else "FAIL",
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
