"""ORT Translation v7.8 graceful shutdown helpers.

WebUI no longer needs to kill TITANMAIN immediately.  The launcher writes a
small stop-request file; TITANMAIN polls it, flushes cache/session/core state,
and exits cleanly.  If that fails, launcher still has a hard-kill fallback.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from status_manager import write_status as _write_status

ROOT = Path(__file__).resolve().parent
DEFAULT_STOP_FILE = ROOT / "runtime_stop_request.json"
STATUS_FILE = ROOT / "status" / "shutdown.json"


def stop_file_from_env(base_dir: str | os.PathLike[str] | None = None) -> Path:
    raw = os.environ.get("ORT_STOP_REQUEST_FILE", "").strip()
    if raw:
        return Path(raw)
    return Path(base_dir or ROOT).resolve() / DEFAULT_STOP_FILE.name


def clear_stop_request(base_dir: str | os.PathLike[str] | None = None) -> None:
    path = stop_file_from_env(base_dir)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def request_stop(base_dir: str | os.PathLike[str] | None = None, reason: str = "webui_stop", pid: Optional[int] = None) -> Path:
    path = stop_file_from_env(base_dir)
    payload: Dict[str, Any] = {
        "version": "v7.5",
        "ts": time.time(),
        "reason": reason,
        "pid": pid,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return path


def read_stop_request(base_dir: str | os.PathLike[str] | None = None) -> Optional[Dict[str, Any]]:
    path = stop_file_from_env(base_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        return {"version": "v7.5", "reason": "stop_file_present", "ts": time.time()}
    return None


def write_shutdown_status(base_dir: str | os.PathLike[str] | None = None, state: str = "UNKNOWN", reason: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    base = Path(base_dir or ROOT).resolve()
    payload: Dict[str, Any] = {
        "version": "v7.5",
        "ts": time.time(),
        "state": state,
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    try:
        _write_status("shutdown", payload, base)
    except Exception:
        pass
