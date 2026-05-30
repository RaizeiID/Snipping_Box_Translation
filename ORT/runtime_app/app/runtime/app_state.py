from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict

DEFAULT_STATE: Dict[str, Any] = {
    "version": "v8.7.2",
    "game": "GFL",
    "settings_mode": "recommended",
    "model": "ORTCore Lite IDN V3",
    "engine": "hybrid",
    "requested_engine": "hybrid",
    "active_engine": "unknown",
    "mode": "auto",
    "requested_mode": "auto",
    "active_mode": "auto",
    "ocr_resolution": 55,
    "requested_ocr_resolution": 55,
    "effective_ocr_resolution": 55,
    "interval_ms": 240,
    "requested_interval_ms": 240,
    "effective_interval_ms": 240,
    "safe_mode": False,
    "online_assist": False,
    "fast_engine_status": "unknown",
    "fast_engine_active": False,
    "dialog_scheduler_profile": "auto_story",
    "image_hash_gate": True,
    "fuzzy_cache_key": True,
    "performance_reason": "",
    "session_id": "",
    "last_updated": 0,
}

def _base(base_dir: str | Path | None = None) -> Path:
    return Path(base_dir or Path(__file__).resolve().parents[2]).resolve()

def state_path(base_dir: str | Path | None = None) -> Path:
    return _base(base_dir) / "configs" / "app_state.json"

def load_state(base_dir: str | Path | None = None) -> Dict[str, Any]:
    p = state_path(base_dir)
    data = dict(DEFAULT_STATE)
    try:
        if p.exists():
            got = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(got, dict):
                data.update(got)
    except Exception:
        pass
    return data

def save_state(updates: Dict[str, Any], base_dir: str | Path | None = None) -> Dict[str, Any]:
    base = _base(base_dir); (base / "configs").mkdir(exist_ok=True)
    data = load_state(base)
    data.update(updates or {})
    data["last_updated"] = time.time()
    p = state_path(base)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return data

def reset_state(base_dir: str | Path | None = None) -> Dict[str, Any]:
    base = _base(base_dir); (base / "configs").mkdir(exist_ok=True)
    data = dict(DEFAULT_STATE); data["last_updated"] = time.time()
    state_path(base).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
