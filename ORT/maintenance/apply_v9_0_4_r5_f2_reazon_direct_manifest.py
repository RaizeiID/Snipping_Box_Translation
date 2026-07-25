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

PATCH_ID = "ORT_V9_0_4_R5_F2_REAZON_DIRECT_MANIFEST"
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


def normalize_project_root(raw: str | os.PathLike[str] | None) -> Path:
    token = str(raw or ".").strip()
    # Windows cmd can pass a literal trailing quote when an argument ends in
    # a backslash immediately before the closing quote. Remove only wrapper or
    # orphan quote characters, then normalize the resulting path.
    token = token.strip('"').strip("'").strip()
    while token.endswith(('"', "'")):
        token = token[:-1].rstrip()
    if not token:
        token = "."
    return Path(token).expanduser().resolve(strict=False)


def project_root_parser_self_test() -> None:
    base = Path.cwd().resolve(strict=False)
    samples = (
        str(base),
        f'"{base}"',
        str(base) + '"',
        str(base) + os.sep + '"',
    )
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


def run_checked(command: list[str], cwd: Path, label: str, timeout: int = 240) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
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
    output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
    if output:
        print(output)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")
    return output


def run_import_smoke(root: Path) -> None:
    app = root / "ORT_App"
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(app)!r}); "
        "import webui; "
        "print('WEBUI_IMPORT_SMOKE: PASS')"
    )
    run_checked([sys.executable, "-c", script], app, "WebUI import startup smoke", timeout=120)


def run_verifier(root: Path, verifier: Path) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    log_path = root / "ORT" / "logs" / "verify_v9_0_4_r5_f2.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print("[VERIFY] Memulai verifier v9.0.4 R5 F2. Jangan tekan Ctrl+C selama heartbeat berjalan.", flush=True)
    print(f"[VERIFY] Log: {log_path}", flush=True)
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


def validate_test_plan(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Installer contract gagal; file test tidak ditemukan:\n- " + "\n- ".join(missing)
        )
    print("Installer test contract: PASS")
    for path in paths:
        print(f"  - {path.name}")


def main() -> int:
    configure_utf8()
    project_root_parser_self_test()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    raw_project_root = args.project_root
    root = normalize_project_root(raw_project_root)
    version_path = root / "VERSION.txt"
    print(f"Project root argument: {raw_project_root!r}")
    print(f"Project root normalized: {root}")
    if not version_path.is_file():
        raise RuntimeError(
            "Project root tidak valid; VERSION.txt tidak ditemukan.\n"
            f"Argumen asli: {raw_project_root!r}\n"
            f"Path setelah normalisasi: {root}\n"
            f"File yang dicari: {version_path}"
        )
    version = read_text(version_path).strip()
    if version != TARGET_VERSION:
        raise RuntimeError(f"Hotfix memerlukan v9.0.4, ditemukan {version}")

    payload_root = Path(__file__).resolve().parents[1] / "patch_payload" / "v9_0_4_r5_f2"
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
        callback_audit = app / "tools" / "v9_0_4_r4_f3_webui_callback_audit_test.py"
        provider_regression = app / "tools" / "v9_0_4_r4_provider_setup_progress_test.py"
        resilient_download = app / "tools" / "v9_0_4_r5_resumable_provider_download_test.py"
        direct_manifest = app / "tools" / "v9_0_4_r5_f2_reazon_direct_manifest_test.py"
        verifier = app / "tools" / "verify_v9_0_0_install.py"
        validate_test_plan([callback_audit, provider_regression, resilient_download, direct_manifest, verifier])
        run_checked(
            [sys.executable, str(callback_audit)],
            app,
            "v9.0.4 R4 F3 callback audit regression",
        )
        run_checked(
            [sys.executable, str(provider_regression)],
            app,
            "v9.0.4 R4 provider setup regression",
        )
        run_checked(
            [sys.executable, str(resilient_download)],
            app,
            "v9.0.4 R5 resumable provider download test",
        )
        run_checked(
            [sys.executable, str(direct_manifest)],
            app,
            "v9.0.4 R5 F2 Reazon direct manifest test",
        )
        run_import_smoke(root)
        manifest_path = update_manifest(root, targets)
        print(f"Manifest: {manifest_path}")
        run_verifier(root, verifier)
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
