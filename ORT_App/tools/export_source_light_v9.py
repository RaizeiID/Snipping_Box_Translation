from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import time
import zipfile
from pathlib import Path


SKIP_DIR_NAMES = {
    "ORT_Runtime", ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    "logs", "cache", "status", "sessions", "backups", "debug_bundles", "exports",
    "user_data", "legacy_payload", "models", "model", "audio_spool",
}
SKIP_FILE_NAMES = {
    "runtime_paths.json", "webui_prefs.json", "runtime_stop_request.json",
    "audio_cloud_credentials.json", ".env",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".bak", ".zip", ".7z", ".rar", ".pt", ".bin", ".onnx"}
MAX_FILE_BYTES = 25 * 1024 * 1024


def is_reparse(path: Path) -> bool:
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def should_skip(path: Path, project_root: Path) -> tuple[bool, str]:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return True, "outside_project"
    parts = relative.parts
    if any(part in SKIP_DIR_NAMES for part in parts[:-1]):
        return True, "runtime_or_generated_dir"
    if path.name in SKIP_FILE_NAMES or path.name.endswith(".runtime.json"):
        return True, "local_config_or_runtime_registry"
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True, "generated_or_binary_suffix"
    if is_reparse(path) or path.is_symlink():
        return True, "junction_or_symlink"
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return True, "large_file"
    except OSError:
        return True, "unreadable"
    # Legacy release/package archives are not necessary for source review.
    lower = "/".join(parts).lower()
    if any(marker in f"/{lower}/" for marker in (
        "/release/legacy_v8/", "/maintenance/legacy_v8/", "/docs/legacy_apply_notes/"
    )):
        return True, "legacy_release_or_apply_notes"
    return False, ""


def iter_source_files(project_root: Path):
    roots = [
        project_root / "START_HERE.bat",
        project_root / "Start WebUI.bat",
        project_root / "Start OCR.bat",
        project_root / "Runtime.bat",
        project_root / "ORT v9 Setup.bat",
        project_root / "VERSION.txt",
        project_root / ".gitignore",
        project_root / "ORT_App",
        project_root / "ORT" / "docs",
        project_root / "ORT" / "plugins",
        project_root / "ORT" / "maintenance",
        project_root / "ORT" / "config",
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            dirs[:] = [
                name for name in dirs
                if name not in SKIP_DIR_NAMES and not is_reparse(current_path / name) and not (current_path / name).is_symlink()
            ]
            for name in files:
                yield current_path / name


def export(project_root: Path) -> tuple[Path, dict]:
    project_root = project_root.expanduser().resolve()
    export_root = project_root / "ORT" / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = export_root / f"ORT_v9_0_0_SOURCE_LIGHT_{stamp}.zip"
    included: list[dict] = []
    skipped: list[dict] = []
    files = sorted(set(iter_source_files(project_root)), key=lambda p: str(p).lower())
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            skip, reason = should_skip(path, project_root)
            relative = path.relative_to(project_root).as_posix()
            if skip:
                skipped.append({"path": relative, "reason": reason})
                continue
            data = path.read_bytes()
            archive.writestr(relative, data)
            included.append({
                "path": relative,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        manifest = {
            "schema": 1,
            "version": "v9.0.0",
            "type": "source_light",
            "project_root": str(project_root),
            "included_count": len(included),
            "skipped_count": len(skipped),
            "included": included,
            "skipped": skipped,
            "excludes": ["ORT_Runtime", "models", "venv", "logs", "cache", "status", "user_data", "credentials", "archives"],
        }
        archive.writestr("SOURCE_EXPORT_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    summary = {
        "passed": True,
        "output": str(target),
        "size_bytes": target.stat().st_size,
        "included_count": len(included),
        "skipped_count": len(skipped),
    }
    return target, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a lightweight ORT source ZIP.")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    _, summary = export(Path(args.project_root))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
