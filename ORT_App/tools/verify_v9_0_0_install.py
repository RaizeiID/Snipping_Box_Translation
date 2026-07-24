from __future__ import annotations

import sys as _ort_sys


def _ort_configure_utf8_stdio() -> None:
    for _name in ("stdout", "stderr"):
        _stream = getattr(_ort_sys, _name, None)
        _reconfigure = getattr(_stream, "reconfigure", None)
        if callable(_reconfigure):
            try:
                _reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


_ort_configure_utf8_stdio()

import argparse
import hashlib
import importlib
import json
import py_compile
import subprocess
import sys
from pathlib import Path


REQUIRED_ROOT = (
    "START_HERE.bat", "Start WebUI.bat", "Start OCR.bat", "Runtime.bat", "ORT v9 Setup.bat", "VERSION.txt",
)
REQUIRED_APP = (
    "webui.py", "build_info.py", "launcher_backend.py", "audio_main.py", "audio_realtime_local_sidecar.py", "audio_translation_sidecar.py",
    "app/audio/asr_provider_registry.py",
    "app/audio/locked_asr_adapter.py",
    "app/audio/provider_benchmark.py",
    "ORTCORE_VERSION.txt", "TITANCORE_VERSION.txt", "RUNTIME.bat", "Start_ORT_Translation.bat",
    "app/open_architecture/__init__.py",
    "app/open_architecture/paths.py",
    "app/open_architecture/registry.py",
    "app/open_architecture/pipeline.py",
    "app/open_architecture/lab.py",
    "app/open_architecture/event_bus.py",
    "app/open_architecture/executor.py",
    "app/open_architecture/runtime_control.py",
    "app/open_architecture/overlay_preview.py",
    "app/runtime/ct2_path_resolver.py",
    "app/open_architecture/streaming/confirmed_prefix.py",
    "tools/migrate_v9_structure.py",
    "tools/export_source_light_v9.py",
    "tools/v9_0_0_open_architecture_layout_test.py",
    "tools/v9_0_1_audio_lab_stability_test.py",
    "tools/v9_0_2_adaptive_turn_overlay_test.py",
    "tools/v9_0_3_stability_realtime_diagnostics_test.py",
    "tools/v9_0_4_cloud_locked_provider_benchmark_test.py",
    "tools/setup_v9_0_4_audio_providers.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_app(project_root: Path) -> Path:
    current = project_root / "ORT_App"
    if (current / "webui.py").is_file():
        return current
    legacy = project_root / "ORT" / "runtime_app"
    return legacy


def load_checksums(project_root: Path) -> dict[str, str]:
    candidates = [
        project_root / "ORT" / "release" / "SHA256SUMS_V9_0_4.json",
        project_root / "ORT" / "release" / "SHA256SUMS_V9_0_3.json",
        project_root / "ORT" / "release" / "SHA256SUMS_V9_0_2.json",
        project_root / "ORT" / "release" / "SHA256SUMS_V9_0_1.json",
        project_root / "ORT" / "release" / "SHA256SUMS_V9_0_0.json",
        project_root / "SHA256SUMS_V9_0_1.json",
        project_root / "SHA256SUMS_V9_0_0.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                return data.get("files", {}) if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def logical_path(project_root: Path, app_root: Path, token: str) -> Path:
    if token.startswith("@APP/"):
        return app_root / token[5:]
    return project_root / token


def verify(project_root: Path) -> dict:
    root = project_root.expanduser().resolve()
    app = resolve_app(root)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    for item in REQUIRED_ROOT:
        path = root / item
        ok = path.is_file()
        checks.append({"check": f"root:{item}", "passed": ok})
        if not ok:
            errors.append(f"missing root file: {item}")
    for item in REQUIRED_APP:
        path = app / item
        ok = path.is_file()
        checks.append({"check": f"app:{item}", "passed": ok})
        if not ok:
            errors.append(f"missing app file: {item}")

    version = (root / "VERSION.txt").read_text(encoding="utf-8-sig").strip() if (root / "VERSION.txt").exists() else ""
    if version != "v9.0.4":
        errors.append(f"version mismatch: {version!r}")

    webui = app / "webui.py"
    if webui.is_file():
        content = webui.read_text(encoding="utf-8-sig")
        for needle in ("Open Architecture Lab", "architecture_apply_preset", "Confirmed Prefix / Local Agreement Demo"):
            if needle not in content:
                errors.append(f"webui marker missing: {needle}")

    compile_targets = [app / item for item in REQUIRED_APP if item.endswith(".py")]
    compile_targets.extend((app / "app" / "open_architecture" / "adapters").glob("*.py"))
    for path in compile_targets:
        if not path.is_file():
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            checks.append({"check": f"compile:{path.relative_to(app)}", "passed": True})
        except Exception as exc:
            errors.append(f"compile {path.relative_to(app)}: {exc}")

    if app.is_dir():
        sys.path.insert(0, str(app))
        try:
            build_info = importlib.import_module("build_info")
            if build_info.APP_VERSION_TAG != "v9.0.4":
                errors.append(f"build_info version: {build_info.APP_VERSION_TAG}")
            lab = importlib.import_module("app.open_architecture.lab")
            initial = lab.architecture_initial_payload()
            if len(initial) != 10 or "production_pipeline_untouched" not in initial[8]:
                errors.append("Open Architecture initial payload invalid")
            table, demo_json = lab.confirmed_prefix_demo("Hello\nHello world\nHello world again", 2)
            demo = json.loads(demo_json)
            if not demo or demo[-1].get("confirmed") != "Hello world again":
                errors.append("Confirmed Prefix deterministic demo failed")
            if "<table" not in table:
                errors.append("Confirmed Prefix HTML missing")
            checks.append({"check": "open_architecture_import_and_demo", "passed": True})
        except Exception as exc:
            errors.append(f"Open Architecture import: {type(exc).__name__}: {exc}")
        finally:
            try:
                sys.path.remove(str(app))
            except ValueError:
                pass

    regression = app / "tools" / "v9_0_0_open_architecture_layout_test.py"
    if regression.is_file():
        result = subprocess.run(
            [sys.executable, str(regression)],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-2000:]
        checks.append({"check": "v9_open_architecture_regression", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("v9 Open Architecture regression failed: " + output)

    sidecar_self_test = app / "audio_realtime_local_sidecar.py"
    if sidecar_self_test.is_file():
        result = subprocess.run(
            [sys.executable, str(sidecar_self_test), "--self-test-json"],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-4000:]
        checks.append({"check": "audio_realtime_sidecar_self_test", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("Audio realtime sidecar self-test failed: " + output)

    stability = app / "tools" / "v9_0_1_audio_lab_stability_test.py"
    if stability.is_file():
        result = subprocess.run(
            [sys.executable, str(stability)],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-4000:]
        checks.append({"check": "v9_0_1_audio_lab_stability", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("v9.0.1 Audio Lab stability failed: " + output)

    adaptive = app / "tools" / "v9_0_2_adaptive_turn_overlay_test.py"
    if adaptive.is_file():
        result = subprocess.run(
            [sys.executable, str(adaptive)],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-5000:]
        checks.append({"check": "v9_0_2_adaptive_turn_overlay", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("v9.0.2 adaptive turn/overlay test failed: " + output)

    stability_v903 = app / "tools" / "v9_0_3_stability_realtime_diagnostics_test.py"
    if stability_v903.is_file():
        result = subprocess.run(
            [sys.executable, str(stability_v903)],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-5000:]
        checks.append({"check": "v9_0_3_stability_realtime_diagnostics", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("v9.0.3 stability/realtime diagnostics test failed: " + output)

    provider_v904 = app / "tools" / "v9_0_4_cloud_locked_provider_benchmark_test.py"
    if provider_v904.is_file():
        result = subprocess.run(
            [sys.executable, str(provider_v904)],
            cwd=str(app),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        output = (result.stdout + result.stderr).strip()[-6000:]
        checks.append({"check": "v9_0_4_cloud_locked_provider_benchmark", "passed": result.returncode == 0, "output": output})
        if result.returncode != 0:
            errors.append("v9.0.4 cloud/locked provider benchmark test failed: " + output)

    checksums = load_checksums(root)
    for token, expected in checksums.items():
        path = logical_path(root, app, token)
        if not path.is_file():
            errors.append(f"checksum missing: {token}")
            continue
        actual = sha256(path)
        if actual.lower() != str(expected).lower():
            errors.append(f"checksum: {token}")

    migrated = app.name == "ORT_App"
    if not migrated:
        warnings.append("Struktur masih kompatibilitas ORT/runtime_app. Jalankan ORT v9 Setup.bat untuk memindahkannya ke ORT_App.")
    else:
        layout = root / "ORT" / "config" / "project_layout.json"
        if not layout.is_file():
            warnings.append("project_layout.json belum tersedia; jalankan ORT v9 Setup.bat sekali lagi.")

    return {
        "passed": not errors,
        "version": version,
        "release": "Cloud & Locked Provider Benchmark Lab",
        "app_root": str(app),
        "migrated_layout": migrated,
        "checked_files": len(REQUIRED_ROOT) + len(REQUIRED_APP),
        "checksum_entries": len(checksums),
        "errors": errors,
        "warnings": warnings,
        "tests": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    result = verify(Path(args.project_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
