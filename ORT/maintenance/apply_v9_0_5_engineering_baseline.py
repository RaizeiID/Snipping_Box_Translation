from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PATCH_ID = "ORT_V9_0_5_ENGINEERING_BASELINE"
TARGET_VERSION = "v9.0.5"
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


def normalize_project_root(raw: str | os.PathLike[str] | None) -> Path:
    token = os.path.expandvars(str(raw or ".")).strip().replace("\x00", "")
    token = token.strip('"').strip("'").strip()
    while token.endswith(('"', "'")):
        token = token[:-1].rstrip()
    if not token:
        token = "."
    return Path(token).expanduser().resolve(strict=False)


def project_root_parser_self_test() -> None:
    base = Path.cwd().resolve(strict=False)
    samples = (str(base), f'"{base}"', str(base) + '"', str(base) + os.sep + '"')
    failures = []
    for raw in samples:
        parsed = normalize_project_root(raw)
        if parsed != base:
            failures.append({"raw": raw, "parsed": str(parsed), "expected": str(base)})
    if failures:
        raise RuntimeError(f"Project-root parser self-test gagal: {failures}")
    print("Project root parser self-test: PASS")


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
    manifest_path = payload_root / "PAYLOAD_SHA256.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Payload manifest tidak ditemukan: {manifest_path}")
    data = json.loads(read_text(manifest_path))
    if data.get("version") != TARGET_VERSION:
        raise RuntimeError(f"Payload version mismatch: {data.get('version')!r}")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError("PAYLOAD_SHA256.json tidak memiliki daftar file")
    normalized: dict[str, str] = {}
    for rel, expected in files.items():
        token = str(rel).replace("\\", "/").lstrip("/")
        source = payload_root / token
        if not source.is_file():
            raise RuntimeError(f"Payload file hilang: {token}")
        actual = sha256(source)
        if actual.lower() != str(expected).lower():
            raise RuntimeError(
                f"Payload checksum gagal: {token}\nexpected={expected}\nactual={actual}"
            )
        normalized[token] = str(expected)
    return normalized


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


def run_checked(command: list[str], cwd: Path, label: str, timeout: int = 240) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
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


def write_release_manifest(root: Path, relative_files: list[str]) -> Path:
    files: dict[str, str] = {}
    for rel in sorted(set(relative_files)):
        path = root / rel
        if path.is_file():
            files[rel.replace("\\", "/")] = sha256(path)
    payload = {
        "schema": 1,
        "version": TARGET_VERSION,
        "release": RELEASE_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    path = root / "ORT" / "release" / "SHA256SUMS_V9_0_5.json"
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def write_receipt(root: Path, backup_folder: Path, files: list[str], manifest: Path) -> Path:
    payload: dict[str, Any] = {
        "patch_id": PATCH_ID,
        "version": TARGET_VERSION,
        "release": RELEASE_NAME,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "backup": str(backup_folder),
        "manifest": str(manifest),
        "changed_files": sorted(files),
        "provider_setup_started": False,
        "note": "Setup/download model sengaja tidak dijalankan oleh updater.",
    }
    path = root / "ORT" / "release" / "INSTALL_RECEIPT_V9_0_5.json"
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> int:
    configure_utf8()
    project_root_parser_self_test()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = normalize_project_root(args.project_root)
    version_path = root / "VERSION.txt"
    if not version_path.is_file():
        raise RuntimeError(f"Project root tidak valid; VERSION.txt tidak ditemukan: {root}")
    source_version = read_text(version_path).strip()
    if source_version not in SUPPORTED_SOURCE_VERSIONS:
        raise RuntimeError(
            f"Updater v9.0.5 memerlukan {sorted(SUPPORTED_SOURCE_VERSIONS)}, ditemukan {source_version!r}"
        )

    payload_root = Path(__file__).resolve().parents[1] / "patch_payload" / "v9_0_5"
    payload_files = load_payload(payload_root)
    targets = [root / rel for rel in payload_files]
    manifest_path = root / "ORT" / "release" / "SHA256SUMS_V9_0_5.json"
    receipt_path = root / "ORT" / "release" / "INSTALL_RECEIPT_V9_0_5.json"
    backup_targets = list(targets)
    for extra in (manifest_path, receipt_path):
        if extra not in backup_targets:
            backup_targets.append(extra)

    backup_folder, existed = backup(root, backup_targets)
    print("============================================================")
    print(" ORT v9.0.5 - Engineering Baseline Update")
    print("============================================================")
    print(f"Project root : {root}")
    print(f"Versi sumber : {source_version}")
    print(f"Backup       : {backup_folder}")
    print("Model setup  : tidak dijalankan oleh updater")
    print()

    try:
        for rel in payload_files:
            source = payload_root / rel
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        print(f"File diterapkan: {len(payload_files)}")

        python_targets = [root / rel for rel in payload_files if rel.endswith(".py")]
        for target in python_targets:
            py_compile.compile(str(target), doraise=True)
        print(f"Python compile: PASS ({len(python_targets)} file)")

        app = root / "ORT_App"
        regression = app / "tools" / "v9_0_5_engineering_baseline_test.py"
        verifier = app / "tools" / "verify_v9_0_5_install.py"
        run_checked([sys.executable, str(regression)], app, "Regression v9.0.5", timeout=180)

        release_manifest = write_release_manifest(root, list(payload_files))
        print(f"Release manifest: {release_manifest}")
        run_checked(
            [sys.executable, str(verifier), "--project-root", str(root)],
            app,
            "Verifier v9.0.5",
            timeout=420,
        )
        receipt = write_receipt(root, backup_folder, list(payload_files), release_manifest)
        print(f"Install receipt: {receipt}")
        print()
        print(f"{PATCH_ID}: PASS")
        print("Update aplikasi selesai. Setup model dapat dilanjutkan dari WebUI bila diperlukan.")
        return 0
    except Exception:
        print("Update gagal; seluruh file yang disentuh sedang dipulihkan...", flush=True)
        restore(root, backup_folder, backup_targets, existed)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
