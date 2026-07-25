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

PATCH_ID = "ORT_V9_0_3_STABILITY_REALTIME_DIAGNOSTICS"
TARGET_VERSION = "v9.0.3"
ALLOWED_SOURCE_VERSIONS = {"v9.0.2", "v9.0.3"}
RELEASE_NAME = "Stability Recovery & Realtime Diagnostics"


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
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def payload_manifest(payload_root: Path) -> dict[str, str]:
    manifest_path = payload_root / "PAYLOAD_SHA256.json"
    data = json.loads(read_text(manifest_path))
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
            raise RuntimeError(f"Payload checksum gagal: {rel}")
    return {str(k): str(v) for k, v in files.items()}


def backup_targets(root: Path, targets: list[Path]) -> tuple[Path, dict[Path, bool]]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / "ORT" / "backups" / f"{PATCH_ID}_{stamp}"
    existed: dict[Path, bool] = {}
    for target in targets:
        existed[target] = target.exists()
        if target.is_file():
            rel = target.relative_to(root)
            dst = backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dst)
    return backup_root, existed


def restore_backup(root: Path, backup_root: Path, targets: list[Path], existed: dict[Path, bool]) -> None:
    for target in targets:
        rel = target.relative_to(root)
        backup = backup_root / rel
        if backup.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        elif not existed.get(target, False):
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass


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


def rebuild_release_manifest(root: Path, targets: list[Path]) -> Path:
    release_dir = root / "ORT" / "release"
    candidates = [
        release_dir / "SHA256SUMS_V9_0_2.json",
        release_dir / "SHA256SUMS_V9_0_1.json",
        release_dir / "SHA256SUMS_V9_0_0.json",
    ]
    data = {"schema": 1, "version": TARGET_VERSION, "release": RELEASE_NAME, "files": {}}
    for candidate in candidates:
        if candidate.is_file():
            try:
                loaded = json.loads(read_text(candidate))
                if isinstance(loaded, dict):
                    data["files"] = dict(loaded.get("files") or {})
                    break
            except Exception:
                pass

    files = data.setdefault("files", {})
    # Installer/finalizer files are one-time utilities and must not be permanent
    # checksum requirements. The inherited manifest can also contain hashes from a
    # retained template or an earlier local migration. Normalize every surviving
    # inherited entry against the actual pre-update installation before writing the
    # v9.0.3 manifest. Payload files are independently verified by PAYLOAD_SHA256.
    normalized_inherited = 0
    for token in list(files):
        upper = token.upper()
        temporary = (
            upper.startswith("APPLY_ORT_")
            or upper.startswith("FINALIZE_ORT_")
            or "APPLY_V9_0_" in upper
            or "PATCH_PAYLOAD/" in upper
            or "README_APPLY_PATCH" in upper
            or "CHANGED_FILES_MANIFEST" in upper
            or "UTF8_VERIFIER_HOTFIX" in upper
        )
        path = logical_path(root, token)
        if temporary or not path.is_file():
            files.pop(token, None)
            continue
        actual = sha256(path)
        if str(files.get(token) or "").lower() != actual.lower():
            normalized_inherited += 1
        files[token] = actual

    for target in targets:
        if target.is_file():
            files[logical_token(root, target)] = sha256(target)

    print(
        f"Manifest inherited checksums normalized: {normalized_inherited}",
        flush=True,
    )

    data["schema"] = 1
    data["version"] = TARGET_VERSION
    data["release"] = RELEASE_NAME
    output = release_dir / "SHA256SUMS_V9_0_3.json"
    write_text(output, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return output


def run_checked(command: list[str], cwd: Path, label: str, timeout: int = 120) -> None:
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
        timeout=timeout,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")


def run_verifier(root: Path, verifier: Path) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    log_path = root / "ORT" / "logs" / "verify_v9_0_3_apply.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    print("[VERIFY] Memulai verifier final v9.0.3.", flush=True)
    print("[VERIFY] Tidak perlu menekan Ctrl+C; heartbeat muncul mulai detik pertama.", flush=True)
    print(f"[VERIFY] Log: {log_path}", flush=True)

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    process = subprocess.Popen(
        [sys.executable, str(verifier), "--project-root", str(root)],
        cwd=str(root / "ORT_App"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    lines: list[str] = []

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)

    thread = threading.Thread(target=reader, daemon=True, name="ort-v903-verifier")
    thread.start()
    started = time.monotonic()
    next_heartbeat = 1
    timeout_seconds = 180

    try:
        while process.poll() is None:
            elapsed = int(time.monotonic() - started)
            if elapsed >= next_heartbeat:
                print(
                    f"[VERIFY HEARTBEAT] aktif {elapsed}s / batas {timeout_seconds}s",
                    flush=True,
                )
                next_heartbeat = 5 if elapsed < 5 else next_heartbeat + 5
            if elapsed >= timeout_seconds:
                try:
                    process.kill()
                except Exception:
                    pass
                raise TimeoutError(
                    f"Verifier melewati {timeout_seconds} detik. Log parsial: {log_path}"
                )
            time.sleep(0.25)
    except KeyboardInterrupt:
        print(
            "[VERIFY] Dibatalkan pengguna. Installer akan memulihkan backup v9.0.2.",
            flush=True,
        )
        try:
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
        raise

    thread.join(timeout=5)
    output = "".join(lines)
    write_text(log_path, output)

    print("\n===== VERIFIER OUTPUT =====")
    print(output.rstrip())
    print("===== END VERIFIER OUTPUT =====\n")

    if process.returncode != 0:
        raise RuntimeError(
            f"Verifier v9.0.3 gagal dengan exit code {process.returncode}. "
            f"Log: {log_path}"
        )
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"JSON verifier tidak ditemukan. Log: {log_path}")
    result = json.loads(output[start:end + 1])
    if not result.get("passed"):
        raise RuntimeError(
            f"Verifier passed=false: errors={result.get('errors')} "
            f"warnings={result.get('warnings')}"
        )
    print(
        f"[VERIFY] PASS | checked_files={result.get('checked_files')} | "
        f"checksum_entries={result.get('checksum_entries')}",
        flush=True,
    )


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    payload_root = Path(__file__).resolve().parents[1] / "patch_payload" / "v9_0_3"

    version_path = root / "VERSION.txt"
    if not version_path.is_file():
        raise RuntimeError(f"VERSION.txt tidak ditemukan: {version_path}")
    current = read_text(version_path).strip()
    if current not in ALLOWED_SOURCE_VERSIONS:
        raise RuntimeError(f"Patch memerlukan v9.0.2/v9.0.3, ditemukan {current}")
    if not (root / "ORT_App" / "app" / "open_architecture" / "executor.py").is_file():
        raise RuntimeError("Open Architecture Audio Lab belum terpasang")

    payload_files = payload_manifest(payload_root)
    targets = [root / rel for rel in payload_files]
    existing_manifest = root / "ORT" / "release" / "SHA256SUMS_V9_0_3.json"
    backup_items = list(targets)
    if existing_manifest not in backup_items:
        backup_items.append(existing_manifest)
    backup_root, existed = backup_targets(root, backup_items)
    print(f"Project root: {root}")
    print(f"Source version: {current}")
    print(f"Backup: {backup_root}")

    try:
        for rel in payload_files:
            src = payload_root / rel
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        for target in targets:
            if target.suffix == ".py":
                py_compile.compile(str(target), doraise=True)
        print("Python compile: PASS")

        app = root / "ORT_App"
        run_checked(
            [sys.executable, str(app / "tools" / "v9_0_2_adaptive_turn_overlay_test.py")],
            app,
            "v9.0.2 adaptive turn/overlay regression",
        )
        run_checked(
            [sys.executable, str(app / "tools" / "v9_0_3_stability_realtime_diagnostics_test.py")],
            app,
            "v9.0.3 stability/realtime diagnostics test",
        )
        run_checked(
            [sys.executable, str(app / "audio_realtime_local_sidecar.py"), "--self-test-json"],
            app,
            "Audio realtime sidecar self-test",
        )

        manifest_path = rebuild_release_manifest(root, targets)
        print(f"Manifest: {manifest_path}")
        run_verifier(root, app / "tools" / "verify_v9_0_0_install.py")

        try:
            shutil.rmtree(payload_root)
            print("Payload sementara dibersihkan.")
        except Exception:
            pass

        print(f"{PATCH_ID}: PASS")
        print("Buka WebUI → Open Architecture Lab → pilih resource/box → Preview atau Validasi → Preload & Mulai Audio Lab.")
        return 0
    except BaseException:
        print("Penerapan gagal; memulihkan backup...", flush=True)
        restore_backup(root, backup_root, backup_items, existed)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
