"""ORT Translation v7.9 session log manager.

Keeps full live/session logs on disk while allowing the UI to show a lighter
recent tail.  Reset happens when WebUI starts a new session.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from status_manager import write_status as _write_status
from app.telemetry.atomic_jsonl import append_jsonl
from build_info import version_payload

ROOT = Path(__file__).resolve().parent

class SessionLogManager:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None, game: str = "CUSTOM"):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.game = (game or "CUSTOM").upper()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"{self.game}_{stamp}"
        self.full_log_path = self.log_dir / f"session_{self.session_id}_full.log"
        self.jsonl_path = self.log_dir / f"session_{self.session_id}_events.jsonl"
        # v7.9: expose paths so TITANMAIN.py subprocess can write structured events directly.
        try:
            os.environ["ORT_SESSION_ID"] = self.session_id
            os.environ["ORT_SESSION_FULL_LOG_PATH"] = str(self.full_log_path)
            os.environ["ORT_SESSION_JSONL_PATH"] = str(self.jsonl_path)
        except Exception:
            pass
        self.status_path = self.base_dir / "status" / "session_log.json"
        self.write_status()

    def append_line(self, line: str) -> None:
        line = (line or "").rstrip("\n")
        try:
            with self.full_log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        # v7.8 structured JSONL: keep a machine-readable copy for AI Recap/benchmark.
        try:
            low = line.lower()
            etype = "LOG"
            if "ocr" in low:
                etype = "OCR_LOG"
            elif "translate" in low or "argos" in low or "cache" in low:
                etype = "TRANSLATION_LOG"
            self.append_event(etype, {"line": line})
        except Exception:
            pass

    def append_event(self, event_type: str, payload: Dict[str, Any], source_module: str = "") -> None:
        payload = dict(payload or {})
        item = {"ts": time.time(), "session_id": self.session_id, "type": event_type, "source_module": source_module or payload.pop("source_module", ""), "writer_pid": os.getpid(), "payload": payload}
        try:
            from session_event_paths import make_event_id
            item["event_id"] = payload.get("event_id") or make_event_id(event_type, payload, item.get("source_module", ""))
        except Exception:
            pass
        append_jsonl(self.jsonl_path, item)

    def read_full_text(self, max_chars: int = 300000) -> str:
        try:
            txt = self.full_log_path.read_text(encoding="utf-8-sig")
            if len(txt) > max_chars:
                return txt[-max_chars:]
            return txt
        except Exception:
            return ""


    def append_translation_event(self, event_type: str, source: str = "", translation: str = "", speaker: str = "", engine: str = "", latency_ms: int | float = 0, cache: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "game": self.game,
            "speaker": speaker or "",
            "source": source or "",
            "translation": translation or "",
            "engine": engine or "",
            "latency_ms": latency_ms,
            "cache": cache or "",
        }
        if extra:
            payload.update(extra)
        self.append_event(event_type, payload, source_module="session_log_manager")

    def close(self, reason: str = "closed") -> None:
        self.append_event("SESSION_CLOSE", {"reason": reason}, source_module="session_log_manager")
        self.write_status(state="CLOSED", reason=reason)

    def write_status(self, state: str = "ACTIVE", reason: str = "") -> None:
        data = version_payload(**{
            "state": state,
            "reason": reason,
            "session_id": self.session_id,
            "game": self.game,
            "full_log_path": str(self.full_log_path),
            "jsonl_path": str(self.jsonl_path),
            "event_writer": "atomic_cross_process_jsonl_v2",
        })
        try:
            _write_status("session_log", data, self.base_dir)
        except Exception:
            pass

_SESSION: Optional[SessionLogManager] = None

def start_session(base_dir: str | os.PathLike[str] | None = None, game: str = "CUSTOM") -> SessionLogManager:
    global _SESSION
    _SESSION = SessionLogManager(base_dir, game)
    return _SESSION

def current_session() -> Optional[SessionLogManager]:
    return _SESSION


def close_session(reason: str = "closed") -> None:
    sess = current_session()
    if sess:
        try:
            sess.close(reason)
        except Exception:
            pass
