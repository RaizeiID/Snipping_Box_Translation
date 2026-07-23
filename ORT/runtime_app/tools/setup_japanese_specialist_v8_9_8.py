#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ID = "kotoba-tech/kotoba-whisper-bilingual-v1.0-faster"
MODEL_FOLDER = "kotoba-whisper-bilingual-v1.0-faster"
RUNTIME_APP = Path(__file__).resolve().parents[1]
PROJECT_ROOT = RUNTIME_APP.parents[1]


def default_model_root() -> Path:
    explicit = str(os.environ.get("ORT_AUDIO_MODEL_ROOT", "") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    runtime_root = str(os.environ.get("ORT_RUNTIME_ROOT", "") or "").strip()
    if runtime_root:
        return Path(runtime_root).expanduser().resolve() / "audio_cpu" / "models"
    return PROJECT_ROOT / "ORT_Runtime" / "audio_cpu" / "models"


def verify_model(path: Path) -> tuple[bool, list[str]]:
    required_groups = [
        ("model.bin",),
        ("config.json",),
        ("tokenizer.json", "vocabulary.json"),
    ]
    missing: list[str] = []
    for group in required_groups:
        if not any((path / name).is_file() for name in group):
            missing.append(" atau ".join(group))
    return not missing, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Unduh model Japanese Specialist ORT v8.9.8")
    parser.add_argument("--model-root", default=str(default_model_root()))
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    model_root = Path(args.model_root).expanduser().resolve()
    target = model_root / MODEL_FOLDER
    model_root.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        report = {
            "passed": False,
            "stage": "dependency",
            "message": "huggingface_hub belum tersedia pada runtime Audio.",
            "detail": str(exc),
            "install_command": f'"{sys.executable}" -m pip install --upgrade huggingface_hub',
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
        snapshot_download(
            repo_id=REPO_ID,
            local_dir=str(target),
            local_files_only=bool(args.local_files_only),
        )
    except Exception as exc:
        print(json.dumps({
            "passed": False,
            "stage": "download",
            "repo_id": REPO_ID,
            "target": str(target),
            "message": str(exc),
        }, ensure_ascii=False, indent=2))
        return 3

    passed, missing = verify_model(target)
    print(json.dumps({
        "passed": passed,
        "repo_id": REPO_ID,
        "target": str(target),
        "missing": missing,
        "next_step": "Pilih Japanese Specialist atau Smart Auto, lalu mulai ulang Audio ORT.",
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
