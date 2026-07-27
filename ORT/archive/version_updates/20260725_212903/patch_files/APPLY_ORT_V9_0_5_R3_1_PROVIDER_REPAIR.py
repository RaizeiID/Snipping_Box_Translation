from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PATCH_NAME = "ORT v9.0.5 R3.1 Packaging & Launcher Repair"
PATCH_DIR = Path(__file__).resolve().parent
PAYLOAD_DIR = PATCH_DIR / "payload"
MANIFEST_PATH = PATCH_DIR / "manifest_sha256.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_project_root(path: Path) -> bool:
    return (
        (path / "VERSION.txt").is_file()
        and (path / "ORT_App").is_dir()
        and (path / "ORT_Runtime").is_dir()
        and (path / "ORT").is_dir()
    )


def locate_project_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if is_project_root(root):
            return root
        raise RuntimeError(f"Folder bukan project root ORT: {root}")

    candidates: list[Path] = []
    current = PATCH_DIR
    for _ in range(5):
        candidates.append(current)
        candidates.append(current.parent)
        current = current.parent
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if is_project_root(candidate):
            return candidate.resolve()
    raise RuntimeError(
        "Project root ORT tidak ditemukan. Letakkan folder patch di dalam "
        "D:\\AI TRANSLATOR\\ORT_Translation_v8_8_1 atau gunakan --project-root."
    )


def load_manifest() -> dict[str, str]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise RuntimeError("Manifest patch kosong atau tidak valid")
    result = {str(key): str(value).lower() for key, value in data.items()}
    for rel, expected in result.items():
        source = PAYLOAD_DIR / rel
        if not source.is_file():
            raise FileNotFoundError(f"Payload tidak ditemukan: {rel}")
        actual = sha256(source)
        if actual != expected:
            raise RuntimeError(f"Checksum payload tidak cocok: {rel}")
    return result


def choose_python(root: Path) -> list[str]:
    candidates = (
        root / "ORT_Runtime" / ".venv" / "Scripts" / "python.exe",
        root / "ORT_Runtime" / "audio_cpu" / ".venv" / "Scripts" / "python.exe",
        root / "ORT_Runtime" / "audio_gpu" / ".venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate)]
    return [sys.executable]


def run_test(command: list[str], root: Path, label: str) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"[TEST] {label}", flush=True)
    result = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=180,
    )
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.stderr:
        print(result.stderr.rstrip(), flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")


def remove_bytecode(root: Path) -> None:
    for relative in ("ORT_App", "ORT"):
        base = root / relative
        if not base.is_dir():
            continue
        for cache in base.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        for pyc in base.rglob("*.pyc"):
            pyc.unlink(missing_ok=True)


def validate_active_files(root: Path) -> dict[str, bool]:
    setup = (root / "ORT_App" / "tools" / "setup_v9_0_4_audio_providers.py").read_text(encoding="utf-8")
    wrapper = (root / "ORT_App" / "tools" / "setup_v9_0_5_audio_providers.py").read_text(encoding="utf-8")
    bridge = (root / "ORT_App" / "app" / "audio" / "argos_offline.py").read_text(encoding="utf-8")
    resolver = (root / "ORT_App" / "app" / "audio" / "windows_dll_resolver.py").read_text(encoding="utf-8")
    build = (root / "ORT_App" / "build_info.py").read_text(encoding="utf-8")
    offline_tool = (root / "ORT_App" / "tools" / "reazon_offline_model_tool.py").read_text(encoding="utf-8")
    checks = {
        "version_file": (root / "VERSION.txt").read_text(encoding="utf-8").strip().lower() == "v9.0.5",
        "setup_r3": "R3 Offline Argos & Native CUDA DLL Repair" in setup,
        "direct_manifest": "_download_reazon_static" in setup and "metadata_preflight=False" in setup,
        "argos_minisbd": "ARGOS_CHUNK_TYPE'] = 'MINISBD'" in setup and "offline_functional_test" in setup,
        "argos_cache_first": "akses package index dilewati" in setup and "_argos_runtime_probe" in setup,
        "cuda_dll_packages": "nvidia-cufft-cu12" in setup and "NVIDIA_CUDA12_DLL_PACKAGES" in setup,
        "cuda_missing_dll_probe": "_cuda_missing_dlls_from_probe" in setup,
        "dll_resolver": "cufft64_11.dll" in resolver and "os.add_dll_directory" in resolver,
        "argos_helper": "MINISBD" in bridge and "get_translation_pair" in bridge,
        "wrapper_r3": "v9.0.5 R3 provider-setup entry point" in wrapper,
        "build_info_r3": "VERSION = (9, 0, 5)" in build and "R3 Offline Argos" in build,
        "offline_model_tool": "_download_reazon_static" in offline_tool and "import_from_directory" in offline_tool,
    }
    return checks


def rollback(root: Path, backup: Path, copied: list[str], created: list[str]) -> None:
    for rel in created:
        target = root / rel
        if target.is_file() or target.is_symlink():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
    for rel in reversed(copied):
        saved = backup / rel
        if saved.is_file():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=PATCH_NAME)
    parser.add_argument("--project-root")
    args = parser.parse_args()

    root = locate_project_root(args.project_root)
    manifest = load_manifest()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = root / "ORT" / "backups" / f"ORT_V9_0_5_R3_1_PROVIDER_REPAIR_{stamp}"
    receipt = root / "ORT" / "status" / "v9_0_5_r3_1_provider_repair_receipt.json"
    copied: list[str] = []
    created: list[str] = []

    print(f"Patch       : {PATCH_NAME}")
    print(f"Project root: {root}")
    print(f"Backup      : {backup}")

    try:
        for rel in sorted(manifest):
            source = PAYLOAD_DIR / rel
            target = root / rel
            if target.exists():
                saved = backup / rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                copied.append(rel)
            else:
                created.append(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha256(target) != manifest[rel]:
                raise RuntimeError(f"Verifikasi hasil salin gagal: {rel}")
            print(f"[COPY] {rel}")

        remove_bytecode(root)
        checks = validate_active_files(root)
        for name, passed in checks.items():
            print(f"{name}: {'PASS' if passed else 'FAIL'}")
        if not all(checks.values()):
            raise RuntimeError("Validasi source aktif gagal: " + ", ".join(name for name, ok in checks.items() if not ok))

        python_cmd = choose_python(root)
        py_files = [str(root / rel) for rel in manifest if rel.endswith(".py")]
        run_test(python_cmd + ["-m", "py_compile", *py_files], root, "Kompilasi file patch")
        run_test(
            python_cmd + [str(root / "ORT_App" / "tools" / "setup_v9_0_4_audio_providers.py"), "--self-test"],
            root,
            "Provider setup self-test",
        )
        for test_name in (
            "v9_0_5_r1_sherpa_api_repair_test.py",
            "v9_0_5_r2_reazon_offline_cuda_repair_test.py",
            "v9_0_5_r3_provider_regression_test.py",
        ):
            run_test(
                python_cmd + [str(root / "ORT_App" / "tools" / test_name)],
                root,
                test_name,
            )

        payload = {
            "passed": True,
            "patch": PATCH_NAME,
            "project_root": str(root),
            "backup": str(backup),
            "checks": checks,
            "files": sorted(manifest),
            "active_hashes": {rel: sha256(root / rel) for rel in sorted(manifest)},
            "updated_at": time.time(),
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ORT_V9_0_5_R3_1_PROVIDER_REPAIR: PASS")
        print(f"Receipt: {receipt}")
        return 0
    except Exception as exc:
        print(f"ORT_V9_0_5_R3_1_PROVIDER_REPAIR: FAIL · {type(exc).__name__}: {exc}", file=sys.stderr)
        rollback(root, backup, copied, created)
        remove_bytecode(root)
        print("Source sebelumnya sudah dipulihkan dari backup.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
