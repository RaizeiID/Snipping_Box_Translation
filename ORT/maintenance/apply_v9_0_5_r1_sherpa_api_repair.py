from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PATCH_ID = "ORT_V9_0_5_R1_SHERPA_API_REPAIR"
TARGET_VERSION = "v9.0.5"
PATCH_REVISION = "R1"
SUPPORTED_SOURCE_VERSIONS = {"v9.0.4", "v9.0.5"}
RELEASE_NAME = "Engineering Baseline & Resilient Provider Setup"


def configure_utf8() -> None:
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


def normalize(raw: str | os.PathLike[str] | None) -> Path:
    token = os.path.expandvars(str(raw or ".")).replace("\x00", "").strip()
    token = token.strip('"').strip("'").strip()
    while token.endswith(('"', "'")):
        token = token[:-1].rstrip()
    return Path(token or ".").expanduser().resolve(strict=False)


def valid_root(path: Path) -> bool:
    return (path / "VERSION.txt").is_file() and (path / "ORT_App").is_dir()


def detect_project_root(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(normalize(explicit))
    script_patch_root = Path(__file__).resolve().parents[2]
    candidates.extend([
        Path.cwd().resolve(strict=False),
        script_patch_root,
        script_patch_root.parent,
        script_patch_root.parent.parent,
    ])
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if valid_root(candidate):
            return candidate
    searched = "\n - ".join(str(item) for item in candidates)
    raise RuntimeError(
        "Folder utama ORT tidak ditemukan. Ekstrak patch ke folder yang berisi "
        "VERSION.txt dan ORT_App, atau letakkan folder patch tepat satu tingkat di bawahnya.\n"
        f"Lokasi yang diperiksa:\n - {searched}"
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_payload(payload_root: Path) -> dict[str, str]:
    manifest = payload_root / "PAYLOAD_SHA256.json"
    data = json.loads(read_text(manifest))
    if data.get("version") != TARGET_VERSION or data.get("revision") != PATCH_REVISION:
        raise RuntimeError(f"Manifest patch tidak cocok: {data}")
    result: dict[str, str] = {}
    for rel, expected in data.get("files", {}).items():
        token = str(rel).replace("\\", "/").lstrip("/")
        source = payload_root / token
        if not source.is_file():
            raise RuntimeError(f"Payload hilang: {token}")
        actual = sha256(source)
        if actual.lower() != str(expected).lower():
            raise RuntimeError(f"Checksum payload gagal: {token}")
        result[token] = str(expected)
    if not result:
        raise RuntimeError("Payload kosong")
    return result


def backup(root: Path, targets: list[Path]) -> tuple[Path, dict[Path, bool]]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = root / "ORT" / "backups" / f"{PATCH_ID}_{stamp}"
    existed: dict[Path, bool] = {}
    for target in targets:
        existed[target] = target.exists()
        if target.is_file():
            destination = folder / target.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
    return folder, existed


def restore(root: Path, folder: Path, targets: list[Path], existed: dict[Path, bool]) -> None:
    for target in targets:
        saved = folder / target.relative_to(root)
        if saved.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, target)
        elif not existed.get(target, False):
            target.unlink(missing_ok=True)


def run_checked(command: list[str], cwd: Path, label: str, timeout: int = 420) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
    if output:
        print(output)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")
    return output


def clear_stale_bytecode(root: Path) -> None:
    locations = (
        root / "ORT_App" / "tools" / "__pycache__",
        root / "ORT_App" / "app" / "audio" / "__pycache__",
        root / "ORT_App" / "__pycache__",
    )
    for location in locations:
        if location.is_dir():
            shutil.rmtree(location, ignore_errors=True)


def write_release_files(root: Path, files: list[str], backup_folder: Path) -> None:
    checksums = {
        rel: sha256(root / rel)
        for rel in sorted(set(files))
        if (root / rel).is_file()
    }
    manifest = {
        "schema": 1,
        "version": TARGET_VERSION,
        "revision": PATCH_REVISION,
        "patch_id": PATCH_ID,
        "release": RELEASE_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": checksums,
    }
    write_text(
        root / "ORT" / "release" / "SHA256SUMS_V9_0_5_R1.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    receipt: dict[str, Any] = {
        "patch_id": PATCH_ID,
        "version": TARGET_VERSION,
        "revision": PATCH_REVISION,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "backup": str(backup_folder),
        "changed_files": sorted(set(files)),
        "provider_setup_started": False,
        "note": "WebUI wajib ditutup dan dibuka ulang sebelum setup provider.",
    }
    write_text(
        root / "ORT" / "release" / "INSTALL_RECEIPT_V9_0_5_R1.json",
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
    )


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default="")
    args = parser.parse_args()

    root = detect_project_root(args.project_root or None)
    source_version = read_text(root / "VERSION.txt").strip()
    if source_version not in SUPPORTED_SOURCE_VERSIONS:
        raise RuntimeError(
            f"Patch mendukung {sorted(SUPPORTED_SOURCE_VERSIONS)}, ditemukan {source_version!r}"
        )

    payload_root = Path(__file__).resolve().parents[1] / "patch_payload" / "v9_0_5_r1"
    payload = load_payload(payload_root)
    targets = [root / rel for rel in payload]
    release_targets = [
        root / "ORT" / "release" / "SHA256SUMS_V9_0_5_R1.json",
        root / "ORT" / "release" / "INSTALL_RECEIPT_V9_0_5_R1.json",
    ]
    backup_targets = targets + release_targets
    backup_folder, existed = backup(root, backup_targets)

    print("============================================================")
    print(" ORT v9.0.5 R1 - Sherpa API & Corrected Installer Repair")
    print("============================================================")
    print(f"Project root : {root}")
    print(f"Versi sumber : {source_version}")
    print(f"Backup       : {backup_folder}")
    print("Model cache  : dipertahankan")
    print()

    try:
        for rel in payload:
            source = payload_root / rel
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        clear_stale_bytecode(root)

        python_files = [root / rel for rel in payload if rel.endswith(".py")]
        for path in python_files:
            py_compile.compile(str(path), doraise=True)
        print(f"Python compile: PASS ({len(python_files)} file)")

        app = root / "ORT_App"
        run_checked(
            [sys.executable, str(app / "tools" / "v9_0_5_engineering_baseline_test.py")],
            app,
            "Regression baseline v9.0.5",
        )
        run_checked(
            [sys.executable, str(app / "tools" / "v9_0_5_r1_sherpa_api_repair_test.py")],
            app,
            "Regression Sherpa API R1",
        )
        write_release_files(root, list(payload), backup_folder)
        run_checked(
            [sys.executable, str(app / "tools" / "verify_v9_0_5_install.py"), "--project-root", str(root)],
            app,
            "Verifier v9.0.5 R1",
            timeout=600,
        )
        print()
        print(f"{PATCH_ID}: PASS")
        print("Tutup seluruh proses ORT lama, lalu buka Start WebUI.bat kembali.")
        return 0
    except Exception:
        print("Patch gagal; file yang disentuh sedang dipulihkan...", flush=True)
        restore(root, backup_folder, backup_targets, existed)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
