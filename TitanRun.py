# TitanRun.py
from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent

def _pick_engine(candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = (ROOT / name)
        if p.exists() and p.is_file():
            return p.resolve()
    return None

def run_engine(candidates: List[str], env_overrides: dict) -> int:
    engine = _pick_engine(candidates)
    if not engine:
        print("[RUN] Engine file not found.")
        print("[RUN] Searched:")
        for c in candidates:
            print("  -", c)
        return 1

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    for k, v in env_overrides.items():
        env[str(k)] = str(v)

    # Use list args + cwd to avoid Windows path-with-spaces issues.
    return subprocess.call([sys.executable, str(engine)], cwd=str(ROOT), env=env)

def run_v1(preset: str, label: str, lite: bool=False, idn: bool=False) -> int:
    env = {
        "TITAN_MODEL_PRESET": preset,
        "TITAN_MODEL_LABEL": label,
        # allow replay/testing
        "TITAN_GAME_OVERRIDE": os.environ.get("TITAN_GAME_OVERRIDE", "TEST"),
    }
    if lite:
        env["TITAN_LITE"] = "1"

    # Naturalization rules:
    if idn:
        env["TITAN_IDN_MODE"] = "1"
        env["TITAN_NATURALIZE_MAX"] = "1"
        env["TITAN_IDN_LEVEL"] = "MAX"
    else:
        env["TITAN_DISABLE_NATURALIZE"] = "1"

    # engine candidates
    candidates = [
        "TitanMainV1_ENGINE.py",
        "TitanMainV1_CORE.py",
        "TitanMainV1_ORIG.py",
        "TITANMAIN.py",
    ]
    return run_engine(candidates, env)
