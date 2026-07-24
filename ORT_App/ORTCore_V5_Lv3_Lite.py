import os
import sys
from pathlib import Path

TARGET = 'TITANMAIN.py'
MODEL_LABEL = 'ORTCore V5 Lv3 Lite'
EXTRA_ENV = {'TITAN_NATURALIZE_MAX': '1', 'ORT_V5_LEVEL': '3', 'TITAN_LITE_MODE': '1', 'TITAN_USE_LITE_POLICY': '1'}
DEFAULT_INTERVAL = 520


def main():
    root = Path(__file__).resolve().parent
    target_path = (root / TARGET).resolve()
    if not target_path.exists():
        print('[MODEL] Target script not found:', target_path)
        raise SystemExit(1)
    env = os.environ.copy()
    env.setdefault('ORT_V7_ENABLED', '1')
    env.setdefault('TITAN_MODEL_PRESET', 'V5')
    env.setdefault('TITAN_MODEL_LABEL', MODEL_LABEL)
    env.setdefault('ORT_MODEL_KEY', 'lite_idn_v3')
    env.setdefault('ORT_MODEL_GROUP', 'lite_idn')
    env.setdefault('ORT_BOOT_INTERVAL_MS', str(DEFAULT_INTERVAL))
    env.setdefault('ORT_BOOT_MODE', 'freeze')
    env.setdefault('ORT_BOOT_ENGINE', 'cpu')
    env.setdefault('TITAN_UNIFIED_UI_ENABLED', '1')
    env.setdefault('TITAN_DISABLE_HUD_POPUP', '1')
    env.setdefault('ORT_GAME_OVERRIDE', os.environ.get('ORT_GAME_OVERRIDE', 'GFL2_EXILIUM'))
    for k, v in EXTRA_ENV.items():
        env[str(k)] = str(v)
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, str(target_path)], env=env))


if __name__ == '__main__':
    main()
