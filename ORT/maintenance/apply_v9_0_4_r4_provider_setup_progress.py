from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

PATCH_ID = "ORT_V9_0_4_R4_PROVIDER_SETUP_PROGRESS_STATUS_UI"
TARGET_VERSION = "v9.0.4"
RELEASE_NAME = "Cloud & Locked Provider Benchmark Lab"


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


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


def logical_token(root: Path, path: Path) -> str:
    app = root / "ORT_App"
    try:
        return "@APP/" + path.relative_to(app).as_posix()
    except ValueError:
        return path.relative_to(root).as_posix()


def logical_path(root: Path, token: str) -> Path:
    if token.startswith("@APP/"):
        return root / "ORT_App" / token[5:]
    return root / token


def load_payload(payload_root: Path) -> dict[str, str]:
    data = json.loads(read_text(payload_root / "PAYLOAD_SHA256.json"))
    if data.get("version") != TARGET_VERSION:
        raise RuntimeError(f"Payload version mismatch: {data.get('version')}")
    files = data.get("files") or {}
    if not isinstance(files, dict) or not files:
        raise RuntimeError("PAYLOAD_SHA256.json tidak valid")
    for rel, expected in files.items():
        path = payload_root / rel
        if not path.is_file():
            raise RuntimeError(f"Payload file hilang: {rel}")
        actual = sha256(path)
        if actual.lower() != str(expected).lower():
            raise RuntimeError(f"Payload checksum gagal: {rel}\nexpected={expected}\nactual={actual}")
    return {str(key): str(value) for key, value in files.items()}


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


def update_manifest(root: Path, targets: list[Path]) -> Path:
    path = root / "ORT" / "release" / "SHA256SUMS_V9_0_4.json"
    if path.is_file():
        data = json.loads(read_text(path))
    else:
        data = {"schema": 1, "version": TARGET_VERSION, "release": RELEASE_NAME, "files": {}}
    files = data.setdefault("files", {})
    for token in list(files):
        actual_path = logical_path(root, token)
        if actual_path.is_file():
            files[token] = sha256(actual_path)
        else:
            files.pop(token, None)
    for target in targets:
        if target.is_file():
            files[logical_token(root, target)] = sha256(target)
    data["schema"] = 1
    data["version"] = TARGET_VERSION
    data["release"] = RELEASE_NAME
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return path


def run_checked(command: list[str], cwd: Path, label: str, timeout: int = 240) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command, cwd=str(cwd), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if output:
        print(output)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")


def run_verifier(root: Path, verifier: Path) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    log_path = root / "ORT" / "logs" / "verify_v9_0_4_r4.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print("[VERIFY] Memulai verifier v9.0.4 R4. Jangan tekan Ctrl+C selama heartbeat berjalan.", flush=True)
    print(f"[VERIFY] Log: {log_path}", flush=True)
    process = subprocess.Popen(
        [sys.executable, str(verifier), "--project-root", str(root)],
        cwd=str(root / "ORT_App"), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    lines: list[str] = []

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    started = time.monotonic()
    next_heartbeat = 1
    timeout_seconds = 180
    while process.poll() is None:
        elapsed = int(time.monotonic() - started)
        if elapsed >= next_heartbeat:
            print(f"[VERIFY HEARTBEAT] aktif {elapsed}s / batas {timeout_seconds}s", flush=True)
            next_heartbeat = 5 if elapsed < 5 else next_heartbeat + 5
        if elapsed >= timeout_seconds:
            process.kill()
            raise TimeoutError(f"Verifier timeout. Log: {log_path}")
        time.sleep(0.25)
    thread.join(timeout=5)
    output = "".join(lines)
    write_text(log_path, output)
    if output.strip():
        print(output.rstrip())
    if process.returncode != 0:
        raise RuntimeError(f"Verifier gagal dengan exit code {process.returncode}. Log: {log_path}")
    start = output.find("{")
    end = output.rfind("}")
    result = json.loads(output[start:end + 1]) if start >= 0 and end >= start else {}
    if not result.get("passed"):
        raise RuntimeError(f"Verifier passed=false: {result.get('errors')}")
    print("[VERIFY] PASS", flush=True)


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    version = read_text(root / "VERSION.txt").strip()
    if version != TARGET_VERSION:
        raise RuntimeError(f"Hotfix memerlukan v9.0.4, ditemukan {version}")

    payload_root = Path(__file__).resolve().parents[1] / "patch_payload" / "v9_0_4_r4"
    payload_files = load_payload(payload_root)
    targets = [root / rel for rel in payload_files]
    manifest = root / "ORT" / "release" / "SHA256SUMS_V9_0_4.json"
    backup_targets = list(targets)
    if manifest not in backup_targets:
        backup_targets.append(manifest)
    folder, existed = backup(root, backup_targets)
    print(f"Project root: {root}")
    print(f"Backup: {folder}")

    try:
        for rel in payload_files:
            source = payload_root / rel
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for target in targets:
            if target.suffix == ".py":
                py_compile.compile(str(target), doraise=True)
        print("Python compile: PASS")
        app = root / "ORT_App"
        run_checked([sys.executable, str(app / "tools" / "v9_0_4_cloud_locked_provider_benchmark_test.py")], app, "v9.0.4 regression")
        run_checked([sys.executable, str(app / "tools" / "v9_0_4_r3_reazon_bridge_preview_test.py")], app, "v9.0.4 R3 bridge preview test")
        run_checked([sys.executable, str(app / "tools" / "v9_0_4_r4_provider_setup_progress_test.py")], app, "v9.0.4 R4 provider setup test")
        manifest_path = update_manifest(root, targets)
        print(f"Manifest: {manifest_path}")
        run_verifier(root, app / "tools" / "verify_v9_0_0_install.py")
        try:
            shutil.rmtree(payload_root)
        except Exception:
            pass
        print(f"{PATCH_ID}: PASS")
        return 0
    except BaseException:
        print("Hotfix gagal; memulihkan backup...", flush=True)
        restore(root, folder, backup_targets, existed)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
