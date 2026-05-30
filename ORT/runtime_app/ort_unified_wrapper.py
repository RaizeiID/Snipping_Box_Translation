from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'TITANMAIN.py'


def run_unified(*, model_preset: str, model_label: str, default_interval: int = 220,
                extra_env: Mapping[str, str] | None = None) -> int:
    if not TARGET.exists():
        print('[MODEL] Unified target not found:', TARGET)
        return 1

    env = os.environ.copy()
    env.setdefault('PYTHONUTF8', '1')
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('TITAN_MODEL_PRESET', model_preset)
    env.setdefault('TITAN_MODEL_LABEL', model_label)
    env.setdefault('TITAN_CAPTURE_INTERVAL_MS', str(default_interval))
    env.setdefault('TITAN_UNIFIED_UI_ENABLED', '1')
    env['TITAN_DISABLE_HUD_POPUP'] = '1'
    env.setdefault('TITAN_GAME_OVERRIDE', os.environ.get('TITAN_GAME_OVERRIDE', 'GFL2_EXILIUM'))
    if extra_env:
        for k, v in extra_env.items():
            env[str(k)] = str(v)

    return subprocess.call([sys.executable, str(TARGET)], env=env)
