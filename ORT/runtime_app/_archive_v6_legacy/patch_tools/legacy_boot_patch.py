from __future__ import annotations
import os
from typing import Dict


def read_webui_boot_preset() -> Dict[str, str]:
    return {
        "engine_mode": os.environ.get("ORT_ENGINE_MODE", "auto").strip().lower(),
        "run_mode": os.environ.get("ORT_RUN_MODE", "auto").strip().lower(),
        "interval_ms": os.environ.get("ORT_INTERVAL_MS", "80").strip(),
        "game_name": os.environ.get("ORT_GAME_NAME", "gfl2").strip().lower(),
    }


def apply_boot_preset_to_legacy_globals(globals_dict: dict) -> Dict[str, str]:
    preset = read_webui_boot_preset()
    engine = preset["engine_mode"]
    if engine in {"cpu", "gpu", "hybrid", "auto"}:
        globals_dict["OCR_ENGINE_MODE"] = engine
        globals_dict["TRANSLATE_ENGINE_MODE"] = engine

    mode = preset["run_mode"]
    if mode in {"auto", "freeze", "interval"}:
        globals_dict["RUN_MODE"] = mode

    try:
        interval_ms = int(preset["interval_ms"])
        globals_dict["CAPTURE_INTERVAL_MS"] = max(10, interval_ms)
    except Exception:
        pass

    globals_dict["GAME_NAME"] = preset["game_name"]
    return preset
