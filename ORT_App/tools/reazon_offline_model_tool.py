from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from setup_v9_0_4_audio_providers import (
    REAZON_FILE_MANIFEST,
    REAZON_LOCAL_DIR,
    _download_reazon_static,
    _reazon_required_files,
    _valid_static_file,
    human_bytes,
)


def find_project_root(explicit: str = "") -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve(strict=False))
    here = Path(__file__).resolve()
    candidates.extend([Path.cwd(), *here.parents])
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.resolve(strict=False)
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if (candidate / "VERSION.txt").is_file() and (candidate / "ORT_App").is_dir():
            return candidate
    raise RuntimeError("Project root ORT tidak ditemukan.")


def verify_model(model_dir: Path, devices: list[str]) -> dict[str, Any]:
    names: list[str] = []
    for device in devices:
        for name in _reazon_required_files(device):
            if name not in names:
                names.append(name)
    files: dict[str, Any] = {}
    missing: list[str] = []
    total = 0
    complete = 0
    for name in names:
        entry = REAZON_FILE_MANIFEST[name]
        size = int(entry["size"])
        total += size
        path = model_dir / name
        valid = _valid_static_file(path, entry)
        if valid:
            complete += size
        else:
            missing.append(name)
        files[name] = {
            "path": str(path),
            "expected_size": size,
            "actual_size": path.stat().st_size if path.is_file() else 0,
            "valid": valid,
        }
    return {
        "model_dir": str(model_dir),
        "devices": devices,
        "total_bytes": total,
        "complete_bytes": complete,
        "total_human": human_bytes(total),
        "complete_human": human_bytes(complete),
        "missing": missing,
        "files": files,
        "passed": not missing,
    }


def import_from_directory(source: Path, destination: Path, devices: list[str]) -> None:
    source = source.expanduser().resolve(strict=False)
    if not source.is_dir():
        raise FileNotFoundError(f"Folder sumber tidak ditemukan: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for device in devices:
        for name in _reazon_required_files(device):
            if name not in names:
                names.append(name)
    for name in names:
        entry = REAZON_FILE_MANIFEST[name]
        candidates = [source / name, *source.rglob(name)]
        found = next((item for item in candidates if _valid_static_file(item, entry)), None)
        if found is None:
            raise RuntimeError(f"File model tidak ditemukan atau tidak valid: {name}")
        target = destination / name
        if target.resolve(strict=False) != found.resolve(strict=False):
            shutil.copy2(found, target)
        print(f"IMPORT: {name} -> {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unduh, impor, atau verifikasi model ReazonSpeech K2 tanpa Hugging Face dry-run.")
    parser.add_argument("action", choices=["download", "import", "verify"])
    parser.add_argument("--project-root", default="")
    parser.add_argument("--device", choices=["cpu", "cuda", "both"], default="both")
    parser.add_argument("--source-dir", default="")
    args = parser.parse_args()

    root = find_project_root(args.project_root)
    devices = ["cpu", "cuda"] if args.device == "both" else [args.device]
    model_root = root / "ORT_Runtime" / "audio_cpu" / "models"
    model_dir = model_root / REAZON_LOCAL_DIR
    cache_dir = Path.home() / ".cache" / "huggingface"

    if args.action == "download":
        for device in devices:
            print(f"DIRECT DOWNLOAD: {device.upper()} (tanpa snapshot dry-run)")
            _download_reazon_static(device=device, model_root=model_root, cache_dir=cache_dir)
    elif args.action == "import":
        if not args.source_dir:
            parser.error("--source-dir wajib untuk action import")
        import_from_directory(Path(args.source_dir), model_dir, devices)

    report = verify_model(model_dir, devices)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
