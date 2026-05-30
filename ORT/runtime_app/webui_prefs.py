from __future__ import annotations
import json
from pathlib import Path

DEFAULT_PREFS = {
    'model_group': 'basic',
    'model_name': 'ORTCore V1',
    'game_name': 'GFL2_EXILIUM',
    'engine_mode': 'gpu',
    'run_mode': 'interval',
    'default_interval': True,
    'interval_ms': 220,
}


def prefs_path(runtime_root: Path) -> Path:
    return Path(runtime_root) / 'webui_prefs.json'


def load_prefs(runtime_root: Path) -> dict:
    path = prefs_path(runtime_root)
    if not path.exists():
        return dict(DEFAULT_PREFS)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        merged = dict(DEFAULT_PREFS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_PREFS)


def save_prefs(runtime_root: Path, update: dict) -> dict:
    data = load_prefs(runtime_root)
    data.update(update)
    path = prefs_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data
