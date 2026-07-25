from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[2]
STATUS_DIR = APP_ROOT / "status"
CONFIG_PATH = STATUS_DIR / "overlay_preview_config.json"
STATE_PATH = STATUS_DIR / "overlay_preview_state.json"
_LOCK = threading.RLock()
_PROCESS: subprocess.Popen | None = None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _normalise_config(config: dict[str, Any] | None, *, active: bool) -> dict[str, Any]:
    row = dict(config or {})
    mode = str(row.get("mode") or "adaptive").strip().lower()
    if mode not in {"adaptive", "fixed", "custom"}:
        mode = "adaptive"
    return {
        "active": bool(active),
        "mode": mode,
        "width_percent": max(40, min(100, int(row.get("width_percent", 92) or 92))),
        "height_px": max(100, min(720, int(row.get("height_px", 190) or 190))),
        "font_size": max(10, min(30, int(row.get("font_size", 15) or 15))),
        "opacity_percent": max(45, min(100, int(row.get("opacity_percent", 91) or 91))),
        "show_source": bool(row.get("show_source", True)),
        "alignment": "center" if str(row.get("alignment") or "left").lower() == "center" else "left",
        "source_text": str(row.get("source_text") or "This is a realtime overlay preview."),
        "translation_text": str(
            row.get("translation_text")
            or "Ini adalah pratinjau box terjemahan secara realtime. Ubah pengaturan tanpa menutup preview."
        ),
        "updated_at": time.time(),
    }


def _process_alive() -> bool:
    global _PROCESS
    return bool(_PROCESS is not None and _PROCESS.poll() is None)


def update_overlay_preview(config: dict[str, Any] | None, *, active: bool | None = None) -> dict[str, Any]:
    with _LOCK:
        effective_active = _process_alive() if active is None else bool(active)
        payload = _normalise_config(config, active=effective_active)
        _write_json(CONFIG_PATH, payload)
        _write_json(
            STATE_PATH,
            {
                "active": effective_active,
                "pid": int(_PROCESS.pid) if _process_alive() else 0,
                "config_path": str(CONFIG_PATH),
                "updated_at": time.time(),
            },
        )
        return payload


def start_overlay_preview(config: dict[str, Any] | None = None) -> tuple[bool, str]:
    global _PROCESS
    with _LOCK:
        if _process_alive():
            update_overlay_preview(config, active=True)
            return True, "Preview aktif · perubahan diterapkan realtime"
        payload = update_overlay_preview(config, active=True)
        audio_main = APP_ROOT / "audio_main.py"
        if not audio_main.is_file():
            return False, f"audio_main.py tidak ditemukan: {audio_main}"
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            _PROCESS = subprocess.Popen(
                [sys.executable, str(audio_main), "--overlay-preview-config", str(CONFIG_PATH)],
                cwd=str(APP_ROOT),
                env=env,
                creationflags=creationflags,
            )
        except Exception as exc:
            _PROCESS = None
            update_overlay_preview(payload, active=False)
            return False, f"Preview gagal dimulai: {type(exc).__name__}: {exc}"
        update_overlay_preview(payload, active=True)
        return True, "Preview aktif · perubahan diterapkan realtime"


def stop_overlay_preview() -> tuple[bool, str]:
    global _PROCESS
    with _LOCK:
        try:
            current = {}
            if CONFIG_PATH.is_file():
                current = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            update_overlay_preview(current, active=False)
        except Exception:
            pass
        proc = _PROCESS
        _PROCESS = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        _write_json(
            STATE_PATH,
            {
                "active": False,
                "pid": 0,
                "config_path": str(CONFIG_PATH),
                "updated_at": time.time(),
            },
        )
        return False, "Preview dihentikan"


def toggle_overlay_preview(active: bool, config: dict[str, Any] | None = None) -> tuple[bool, str, str]:
    if bool(active) and _process_alive():
        state, message = stop_overlay_preview()
        return state, "Preview", message
    state, message = start_overlay_preview(config)
    return state, "Stop Preview" if state else "Preview", message


def overlay_preview_status() -> dict[str, Any]:
    with _LOCK:
        return {
            "active": _process_alive(),
            "pid": int(_PROCESS.pid) if _process_alive() else 0,
            "config_path": str(CONFIG_PATH),
        }
