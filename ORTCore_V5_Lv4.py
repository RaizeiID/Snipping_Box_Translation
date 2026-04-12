
import os
import sys
from pathlib import Path

TARGET = 'TitanMainV4.py'
MODEL_LABEL = 'ORTCore V5 Lv4'
EXTRA_ENV = {'TITAN_NATURALIZE_MAX': '1', 'ORT_V5_LEVEL': '4'}
DEFAULT_INTERVAL = 200

def main():
    root = Path(__file__).resolve().parent
    target_path = (root / TARGET).resolve()
    if not target_path.exists():
        print('[MODEL] Target script not found:', target_path)
        raise SystemExit(1)
    env = os.environ.copy()
    env.setdefault('TITAN_MODEL_PRESET', 'V5')
    env.setdefault('TITAN_MODEL_LABEL', MODEL_LABEL)
    env.setdefault('TITAN_CAPTURE_INTERVAL_MS', str(DEFAULT_INTERVAL))
    env.setdefault('TITAN_UNIFIED_UI_ENABLED', '1')
    for k, v in EXTRA_ENV.items():
        env[str(k)] = str(v)
    import subprocess
    env.setdefault('TITAN_DISABLE_HUD_POPUP', '1')
    env.setdefault('TITAN_GAME_OVERRIDE', os.environ.get('TITAN_GAME_OVERRIDE', 'gfl2'))
    raise SystemExit(subprocess.call([sys.executable, str(target_path)], env=env))

if __name__ == '__main__':
    main()
