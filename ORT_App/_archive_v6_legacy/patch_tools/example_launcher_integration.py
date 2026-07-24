"""
Contoh integrasi ke launcher_backend.py
"""
import os
from webui_prefs import save_prefs


def build_runtime_env(base_env: dict, runtime_root: str, *, engine_mode: str, run_mode: str,
                      interval_ms: int, game_name: str, model_name: str, model_family: str) -> dict:
    env = dict(base_env)
    env["ORT_ENGINE_MODE"] = engine_mode.lower().strip()
    env["ORT_RUN_MODE"] = run_mode.lower().strip()
    env["ORT_INTERVAL_MS"] = str(interval_ms)
    env["ORT_GAME_NAME"] = game_name.strip().lower()

    save_prefs(runtime_root, {
        "engine_mode": env["ORT_ENGINE_MODE"],
        "run_mode": env["ORT_RUN_MODE"],
        "interval_ms": interval_ms,
        "game_name": game_name,
        "model_name": model_name,
        "model_family": model_family,
    })
    return env
