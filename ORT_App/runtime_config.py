from __future__ import annotations
import json, os
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / 'runtime_paths.json'

def default_runtime_root() -> Path:
    try:
        return Path(os.environ['ORT_RUNTIME_ROOT']).resolve()
    except Exception:
        return ROOT / '_runtime'

def read_runtime_config() -> Dict[str, str]:
    data = {
        'storage_mode': 'local',
        'project_root': str(ROOT),
        'runtime_root': str(default_runtime_root()),
        'runtime_label': 'ORT_Runtime',
    }
    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        data.update({k: str(v) for k, v in loaded.items() if v is not None})
    except Exception:
        pass
    return data

def runtime_root() -> Path:
    return Path(read_runtime_config().get('runtime_root') or ROOT).resolve()

def runtime_meta_path() -> Path:
    return runtime_root() / 'runtime_meta.json'

def read_runtime_meta() -> Dict[str, str]:
    p = runtime_meta_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
