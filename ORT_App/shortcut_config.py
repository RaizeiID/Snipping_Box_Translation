
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CFG = ROOT / 'shortcut_config.json'
DEFAULT = {
  'esc_exit_enabled': False,
  'bindings': {
    'pause_resume':'f1','reset_area':'f2','capture_mode':'f3','visual_style':'f4','box_position':'f5',
    'font_down':'f6','font_up':'f7','box_width':'f8','ocr_engine':'f9','snapshot_ultra':'f10',
    'interval_mode':'f11','cas_toggle':'shift+f1','launch_legacy_menu':'shift+f9','toggle_live_mode':'f12'
  }
}

def load_shortcuts():
    data = json.loads(json.dumps(DEFAULT))
    try:
        raw = json.loads(CFG.read_text(encoding='utf-8'))
        if isinstance(raw, dict):
            data.update({k:v for k,v in raw.items() if k != 'bindings'})
            if isinstance(raw.get('bindings'), dict):
                data['bindings'].update({str(k): str(v) for k,v in raw['bindings'].items()})
    except Exception:
        pass
    return data

def save_shortcuts(cfg: dict):
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')

def binding(action: str, fallback: str) -> str:
    cfg = load_shortcuts()
    return str(cfg.get('bindings', {}).get(action, fallback))

def esc_enabled() -> bool:
    return bool(load_shortcuts().get('esc_exit_enabled', False))
