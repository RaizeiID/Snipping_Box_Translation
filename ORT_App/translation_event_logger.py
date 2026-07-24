"""ORT Translation v7.9 structured session event logger.

Works both inside the WebUI process and inside TITANMAIN.py subprocess.
If the in-memory SessionLogManager is unavailable, events are written directly
to ORT_SESSION_JSONL_PATH passed through environment variables.
"""
from __future__ import annotations
from typing import Any, Dict, Optional


def append_event(event_type: str, payload: Optional[Dict[str, Any]] = None, source_module: str = "") -> None:
    payload = dict(payload or {})
    if source_module:
        payload.setdefault("source_module", source_module)
    # 1) Parent process session object, if available.
    try:
        from session_log_manager import current_session
        sess = current_session()
        if sess:
            sess.append_event(event_type, payload, source_module=source_module)
            return
    except Exception:
        pass
    # 2) Subprocess-safe direct JSONL path.
    try:
        from session_event_paths import append_jsonl_event
        append_jsonl_event(event_type, payload, source_module=source_module)
    except Exception:
        pass


def append_translation_event(
    event_type: str,
    source: str = "",
    translation: str = "",
    speaker: str = "",
    engine: str = "",
    latency_ms: int | float = 0,
    cache: str = "",
    extra: Optional[Dict[str, Any]] = None,
    source_module: str = "translation",
) -> None:
    payload = {
        "speaker": speaker or "",
        "source": source or "",
        "translation": translation or "",
        "engine": engine or "",
        "latency_ms": latency_ms,
        "cache": cache or "",
    }
    if extra:
        payload.update(extra)
    append_event(event_type, payload, source_module=source_module)
