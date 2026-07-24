#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

REPO_ID = "kotoba-tech/kotoba-whisper-bilingual-v1.0-faster"
TOKENIZER_REPO = "openai/whisper-tiny"
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


def required_files(path: Path) -> dict[str, bool]:
    return {
        "model.bin": (path / "model.bin").is_file(),
        "config.json": (path / "config.json").is_file(),
        "vocabulary.json": (path / "vocabulary.json").is_file(),
        "preprocessor_config.json": (path / "preprocessor_config.json").is_file(),
        "tokenizer.json": (path / "tokenizer.json").is_file(),
    }


def find_local_tokenizer(model_root: Path) -> Path | None:
    for size in ("small", "base", "tiny"):
        candidate = model_root / f"faster-whisper-{size}" / "tokenizer.json"
        if candidate.is_file():
            return candidate
        candidate = model_root / size / "tokenizer.json"
        if candidate.is_file():
            return candidate
    return None


def ensure_tokenizer(model_root: Path, target: Path, local_files_only: bool) -> tuple[bool, str]:
    destination = target / "tokenizer.json"
    if destination.is_file() and destination.stat().st_size > 100_000:
        return True, "existing"
    local = find_local_tokenizer(model_root)
    if local is not None:
        shutil.copy2(local, destination)
        return True, f"copied:{local}"
    try:
        from huggingface_hub import hf_hub_download

        downloaded = hf_hub_download(
            repo_id=TOKENIZER_REPO,
            filename="tokenizer.json",
            local_files_only=bool(local_files_only),
        )
        shutil.copy2(downloaded, destination)
        return True, f"downloaded:{TOKENIZER_REPO}"
    except Exception as exc:
        return False, str(exc)


def validate_load(target: Path, cpu_threads: int) -> tuple[bool, str]:
    old_hf = os.environ.get("HF_HUB_OFFLINE")
    old_transformers = os.environ.get("TRANSFORMERS_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            str(target),
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, int(cpu_threads)),
            num_workers=1,
        )
        segments, _ = model.transcribe(
            np.zeros(4000, dtype=np.float32),
            language="en",
            task="translate",
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=True,
        )
        list(segments)
        return True, "MODEL_LOAD_SUCCESS"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        if old_hf is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = old_hf
        if old_transformers is None:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            os.environ["TRANSFORMERS_OFFLINE"] = old_transformers


def main() -> int:
    parser = argparse.ArgumentParser(description="Install dan validasi Japanese Specialist ORT v8.9.9")
    parser.add_argument("--model-root", default=str(default_model_root()))
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--skip-load-test", action="store_true")
    parser.add_argument("--cpu-threads", type=int, default=max(1, min(4, os.cpu_count() or 4)))
    args = parser.parse_args()

    model_root = Path(args.model_root).expanduser().resolve()
    target = model_root / MODEL_FOLDER
    model_root.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        print(json.dumps({
            "passed": False,
            "stage": "dependency",
            "message": "huggingface_hub belum tersedia pada runtime Audio CPU.",
            "detail": str(exc),
            "install_command": f'"{sys.executable}" -m pip install --upgrade huggingface_hub',
        }, ensure_ascii=False, indent=2))
        return 2

    download_warning = ""
    try:
        snapshot_download(
            repo_id=REPO_ID,
            local_dir=str(target),
            local_files_only=bool(args.local_files_only),
        )
    except Exception as exc:
        # HF may close a metadata client after the 1.5GB payload is already
        # reconstructed. Continue only when the repository payload is complete.
        download_warning = str(exc)
        payload = required_files(target)
        if not all(payload[name] for name in ("model.bin", "config.json", "vocabulary.json", "preprocessor_config.json")):
            print(json.dumps({
                "passed": False,
                "stage": "download",
                "repo_id": REPO_ID,
                "target": str(target),
                "files": payload,
                "message": str(exc),
            }, ensure_ascii=False, indent=2))
            return 3

    tokenizer_ok, tokenizer_source = ensure_tokenizer(model_root, target, bool(args.local_files_only))
    files = required_files(target)
    if not tokenizer_ok or not all(files.values()):
        print(json.dumps({
            "passed": False,
            "stage": "tokenizer_or_files",
            "repo_id": REPO_ID,
            "target": str(target),
            "files": files,
            "tokenizer_source": tokenizer_source,
            "download_warning": download_warning,
        }, ensure_ascii=False, indent=2))
        return 4

    load_ok, load_detail = (True, "SKIPPED") if args.skip_load_test else validate_load(target, args.cpu_threads)
    passed = bool(load_ok and all(files.values()))
    report = {
        "passed": passed,
        "stage": "complete" if passed else "model_load",
        "repo_id": REPO_ID,
        "target": str(target),
        "files": files,
        "tokenizer_source": tokenizer_source,
        "download_warning": download_warning,
        "model_load": load_detail,
        "next_step": "Pilih Japanese Specialist atau Smart Auto. Hybrid akan mempertahankan Kotoba saat berpindah GPU ke CPU.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 5


if __name__ == "__main__":
    raise SystemExit(main())
