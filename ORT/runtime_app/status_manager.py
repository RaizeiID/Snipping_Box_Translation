"""ORT Translation v8.1 unified status manager.

Runtime status is now canonical under ``status/``.  Active modules no longer
write canonical status files under status/. Mixed legacy status filenames are archived only for migration evidence, not used as active runtime sources.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
STATUS_DIR_NAME = "status"
STATUS_KEYS = [
    "strategy", "runtime_health", "runtime_actions", "core_bridge", "core_profile",
    "cache", "fast_engine", "online_assist", "translation_engine", "shutdown",
    "session_log", "benchmark", "benchmark_ocr", "benchmark_translation",
    "benchmark_profiles", "benchmark_real_translation", "benchmark_cache_hit", "benchmark_session",
    "fast_setup", "online_config",
]
LEGACY_STATUS_NAMES = {
    "v72_strategy_status.json", "v74_runtime_health.json", "v72_runtime_health.json",
    "v74_runtime_actions.json", "v73_runtime_actions.json", "v72_core_status.json",
    "v73_core_profile_status.json", "v74_cache_status.json", "v73_cache_status.json",
    "v73_fast_engine_status.json", "v74_online_assist_status.json", "v73_online_assist_status.json",
    "v74_translation_engine_status.json", "v74_shutdown_status.json",
    "v74_session_log_status.json", "v73_session_log_status.json", "v74_benchmark_report.json",
    "v72_bridge_events.log", "v74_benchmark_report.txt",
}

def status_dir(base_dir: str | os.PathLike[str] | None = None) -> Path:
    base = Path(base_dir or ROOT).resolve()
    path = base / STATUS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def status_path(name: str, base_dir: str | os.PathLike[str] | None = None) -> Path:
    token = (name or "status").strip().lower().replace(" ", "_")
    token = token[:-5] if token.endswith(".json") else token
    return status_dir(base_dir) / f"{token}.json"

def write_status(name: str, payload: Dict[str, Any], base_dir: str | os.PathLike[str] | None = None) -> Path:
    data = dict(payload or {})
    data.setdefault("version", "v8.1")
    data.setdefault("ts", time.time())
    path = status_path(name, base_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
    return path

def read_status(name: str, base_dir: str | os.PathLike[str] | None = None, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    default = default if default is not None else {}
    path = status_path(name, base_dir)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return dict(default)

def cleanup_legacy_status_files(base_dir: str | os.PathLike[str] | None = None) -> int:
    """Move old mixed-version status files into status/_legacy_aliases."""
    base = Path(base_dir or ROOT).resolve()
    archive = status_dir(base) / "_legacy_aliases"
    archive.mkdir(parents=True, exist_ok=True)
    moved = 0
    for name in sorted(LEGACY_STATUS_NAMES):
        src = base / name
        if src.exists():
            dst = archive / name
            try:
                if dst.exists(): dst.unlink()
                src.replace(dst)
                moved += 1
            except Exception:
                pass
    return moved

def status_summary(base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    base = Path(base_dir or ROOT).resolve()
    out = {"version": "v8.1", "status_dir": str(status_dir(base)), "items": {}}
    for key in STATUS_KEYS:
        p = status_path(key, base)
        out["items"][key] = {"exists": p.exists(), "path": str(p)}
    return out
