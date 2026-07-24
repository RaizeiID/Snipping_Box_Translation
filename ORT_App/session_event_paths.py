"""ORT Translation v7.9 subprocess-safe session event paths.

WebUI creates the session files, then passes paths to TITANMAIN.py via env.
TITANMAIN/translation_engine can write structured JSONL directly without relying
on an in-memory SessionLogManager object from the parent process.
"""
from __future__ import annotations
import os, time, json, hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from app.telemetry.atomic_jsonl import append_jsonl

ROOT = Path(__file__).resolve().parent

def _env_path(key: str) -> Optional[Path]:
    val = os.environ.get(key, "").strip()
    if not val: return None
    try:
        p = Path(val)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        return None

def session_id() -> str:
    return os.environ.get("ORT_SESSION_ID", "").strip()

def jsonl_path() -> Optional[Path]:
    return _env_path("ORT_SESSION_JSONL_PATH")

def full_log_path() -> Optional[Path]:
    return _env_path("ORT_SESSION_FULL_LOG_PATH")

def make_event_id(event_type: str, payload: Dict[str, Any], source_module: str = "") -> str:
    base = {
        "session": session_id(),
        "type": event_type,
        "source_module": source_module,
        "stage": payload.get("stage") or payload.get("kind") or "",
        "text": (payload.get("source") or payload.get("text") or payload.get("ocr_text") or payload.get("line") or "")[:160],
        "translation": (payload.get("translation") or "")[:160],
        "bucket": int(time.time() * 10),
    }
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:20]

def append_jsonl_event(event_type: str, payload: Optional[Dict[str, Any]] = None, source_module: str = "") -> bool:
    p = jsonl_path()
    if not p: return False
    payload = dict(payload or {})
    item = {
        "ts": time.time(),
        "session_id": session_id(),
        "type": event_type,
        "source_module": source_module or payload.pop("source_module", ""),
        "writer_pid": os.getpid(),
        "payload": payload,
    }
    item["event_id"] = payload.get("event_id") or make_event_id(event_type, payload, item["source_module"])
    return append_jsonl(p, item)

def append_full_log_line(line: str) -> bool:
    p = full_log_path()
    if not p: return False
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write((line or "").rstrip("\n") + "\n")
        return True
    except Exception:
        return False
