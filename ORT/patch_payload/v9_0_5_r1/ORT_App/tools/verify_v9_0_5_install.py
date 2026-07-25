from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Any

TARGET_VERSION = "v9.0.5"
TARGET_RELEASE = "Engineering Baseline & Resilient Provider Setup"

REQUIRED_ROOT = (
    "START_HERE.bat",
    "Start WebUI.bat",
    "Start OCR.bat",
    "Runtime.bat",
    "ORT v9 Setup.bat",
    "VERSION.txt",
)
REQUIRED_APP = (
    "webui.py",
    "build_info.py",
    "launcher_backend.py",
    "audio_main.py",
    "audio_realtime_local_sidecar.py",
    "audio_translation_sidecar.py",
    "RUNTIME.bat",
    "Start_ORT_Translation.bat",
    "app/audio/asr_provider_registry.py",
    "app/audio/locked_asr_adapter.py",
    "app/audio/sherpa_compat.py",
    "app/open_architecture/pipeline.py",
    "tools/setup_v9_0_4_audio_providers.py",
    "tools/setup_v9_0_5_audio_providers.py",
    "tools/v9_0_5_engineering_baseline_test.py",
    "tools/v9_0_5_r1_sherpa_api_repair_test.py",
    "tools/verify_v9_0_5_install.py",
)
REGRESSION_TESTS = (
    "tools/v9_0_4_r4_f3_webui_callback_audit_test.py",
    "tools/v9_0_4_r4_provider_setup_progress_test.py",
    "tools/v9_0_4_r5_resumable_provider_download_test.py",
    "tools/v9_0_4_r5_f2_reazon_direct_manifest_test.py",
    "tools/v9_0_5_engineering_baseline_test.py",
    "tools/v9_0_5_r1_sherpa_api_repair_test.py",
)


def _configure_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_app(root: Path) -> Path:
    current = root / "ORT_App"
    if (current / "webui.py").is_file():
        return current
    return root / "ORT" / "runtime_app"


def logical_path(root: Path, app: Path, token: str) -> Path:
    if token.startswith("@APP/"):
        return app / token[5:]
    return root / token


def load_checksums(root: Path) -> tuple[Path | None, dict[str, str]]:
    candidates = (
        root / "ORT" / "release" / "SHA256SUMS_V9_0_5_R1.json",
        root / "ORT" / "release" / "SHA256SUMS_V9_0_5.json",
        root / "ORT" / "release" / "SHA256SUMS_V9_0_4.json",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            files = payload.get("files", {}) if isinstance(payload, dict) else {}
            return path, {str(key): str(value) for key, value in files.items()}
        except Exception:
            return path, {}
    return None, {}


def run_test(app: Path, relative: str, timeout: int = 180) -> dict[str, Any]:
    path = app / relative
    if not path.is_file():
        return {"test": relative, "passed": False, "output": "missing test file"}
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(app),
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
    return {"test": relative, "passed": result.returncode == 0, "output": output[-8000:]}


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve(strict=False)
    app = resolve_app(root)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    for item in REQUIRED_ROOT:
        path = root / item
        passed = path.is_file()
        checks.append({"check": f"root:{item}", "passed": passed})
        if not passed:
            errors.append(f"missing root file: {item}")
    for item in REQUIRED_APP:
        path = app / item
        passed = path.is_file()
        checks.append({"check": f"app:{item}", "passed": passed})
        if not passed:
            errors.append(f"missing app file: {item}")

    version_path = root / "VERSION.txt"
    version = version_path.read_text(encoding="utf-8-sig").strip() if version_path.is_file() else ""
    if version != TARGET_VERSION:
        errors.append(f"version mismatch: {version!r}; expected {TARGET_VERSION!r}")

    compile_targets = [app / item for item in REQUIRED_APP if item.endswith(".py")]
    for path in compile_targets:
        if not path.is_file():
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            checks.append({"check": f"compile:{path.relative_to(app)}", "passed": True})
        except Exception as exc:
            errors.append(f"compile {path.relative_to(app)}: {type(exc).__name__}: {exc}")

    if app.is_dir():
        sys.path.insert(0, str(app))
        try:
            build_info = importlib.import_module("build_info")
            if build_info.APP_VERSION_TAG != TARGET_VERSION:
                errors.append(f"build_info version: {build_info.APP_VERSION_TAG}")
            if build_info.RELEASE_NAME != TARGET_RELEASE:
                errors.append(f"build_info release: {build_info.RELEASE_NAME}")
            pipeline = importlib.import_module("app.open_architecture.pipeline")
            payload = pipeline.pipeline_payload(
                {
                    "source": "ort_wasapi",
                    "vad": "ort_rms_vad",
                    "asr": "ort_faster_whisper",
                    "streaming": "ort_rolling_context",
                    "translation": "ortcore_fast_v2",
                    "overlay": "ort_overlay",
                },
                preset_id="verify",
                label="Verifier",
            )
            if payload.get("version") != TARGET_VERSION:
                errors.append(f"pipeline version: {payload.get('version')}")
            checks.append({"check": "build_info_and_pipeline_version", "passed": True})
        except Exception as exc:
            errors.append(f"version import: {type(exc).__name__}: {exc}")
        finally:
            try:
                sys.path.remove(str(app))
            except ValueError:
                pass

    for relative in REGRESSION_TESTS:
        result = run_test(app, relative)
        checks.append(result)
        if not result["passed"]:
            errors.append(f"regression failed: {relative}: {result['output'][-1200:]}")

    sidecar = app / "audio_realtime_local_sidecar.py"
    if sidecar.is_file():
        result = subprocess.run(
            [sys.executable, str(sidecar), "--self-test-json"],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )
        output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
        checks.append({"test": "audio_realtime_local_sidecar --self-test-json", "passed": result.returncode == 0, "output": output[-8000:]})
        if result.returncode != 0:
            errors.append("audio realtime sidecar self-test failed: " + output[-1200:])

    manifest_path, checksums = load_checksums(root)
    if manifest_path is None:
        warnings.append("SHA256SUMS_V9_0_5.json belum tersedia; checksum payload tidak diperiksa.")
    elif manifest_path.name != "SHA256SUMS_V9_0_5.json":
        warnings.append(f"Manifest v9.0.5 belum tersedia; memakai fallback {manifest_path.name}.")
    for token, expected in checksums.items():
        path = logical_path(root, app, token)
        if not path.is_file():
            errors.append(f"checksum missing: {token}")
            continue
        actual = sha256(path)
        if actual.lower() != expected.lower():
            errors.append(f"checksum mismatch: {token}")

    return {
        "passed": not errors,
        "version": version,
        "release": TARGET_RELEASE,
        "app_root": str(app),
        "checked_files": len(REQUIRED_ROOT) + len(REQUIRED_APP),
        "checksum_manifest": str(manifest_path) if manifest_path else "",
        "checksum_entries": len(checksums),
        "errors": errors,
        "warnings": warnings,
        "tests": checks,
    }


def main() -> int:
    _configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    result = verify(Path(args.project_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
