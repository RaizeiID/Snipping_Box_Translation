from __future__ import annotations
import html, json, os
from pathlib import Path
from typing import Any, Dict
ROOT = Path(__file__).resolve().parent
THEME_FILE = ROOT / 'ort_ui_theme.json'
SETTINGS_FILE = ROOT / 'ui_settings.json'

def _read_json(path: Path, default: dict):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            merged = dict(default)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(default)

def load_theme() -> Dict[str, Any]:
    default = {
        'themes': {
            'gfl2': {'box_background':'rgba(18,26,29,.84)','box_border':'#22c55e','accent_color':'#86efac','title_color':'#f8fafc','body_color':'#e5f7e9'},
            'wuwa': {'box_background':'rgba(23,20,36,.84)','box_border':'#a78bfa','accent_color':'#c4b5fd','title_color':'#f8fafc','body_color':'#ede9fe'},
            'neutral': {'box_background':'rgba(17,24,39,.84)','box_border':'#38bdf8','accent_color':'#7dd3fc','title_color':'#f8fafc','body_color':'#e2e8f0'}
        },
        'font_family': 'Segoe UI', 'corner_radius': 16, 'shadow': '0 14px 40px rgba(0,0,0,.35)'
    }
    return _read_json(THEME_FILE, default)

def load_settings() -> Dict[str, Any]:
    return _read_json(SETTINGS_FILE, {'profile':'gfl2','compact':False,'show_ms':True,'show_mode':True,'show_model':True,'show_game':True,'show_speaker':True,'show_engine':True,'show_interval':True,'corner_radius':16,'font_scale':1.0,'theme':'gfl2','show_engine_corner':True})

def save_settings(settings: Dict[str, Any]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')

def _engine_color(engine: str) -> str:
    e = str(engine or '').lower()
    if 'gpu' in e and 'auto' not in e and 'hybrid' not in e:
        return '#22c55e'
    if 'auto' in e or 'hybrid' in e or 'cpu+gpu' in e:
        return '#ef4444'
    return '#60a5fa'

def _game_label(raw: str) -> str:
    x = str(raw or os.environ.get('TITAN_GAME_OVERRIDE', 'gfl2')).lower().strip()
    if 'gfl2' in x:
        return 'gfl2'
    if 'wuthering' in x or 'wuwa' in x:
        return 'wuthering waves'
    return x.replace('_exilium','').replace('_game','').replace('_',' ')

def render_html(payload: Dict[str, Any]) -> str:
    theme = load_theme(); settings = load_settings()
    th = theme['themes'].get(settings.get('theme','neutral'), theme['themes']['neutral'])
    game = _game_label(str(payload.get('game') or 'gfl2'))
    model = str(payload.get('model') or 'ORTCore')
    speaker = str(payload.get('speaker') or '')
    text = str(payload.get('translated_text') or payload.get('text') or 'Pratinjau box terjemahan aktif.')
    ms = payload.get('latency_ms', 439)
    interval = payload.get('interval_ms', 220)
    mode = payload.get('mode', 'interval')
    engine = payload.get('engine', 'auto')
    chips=[]
    if settings.get('show_mode', True): chips.append(f"MODE: {mode.upper()}")
    if settings.get('show_interval', True): chips.append(f"INT: {interval} ms")
    if settings.get('show_ms', True): chips.append(f"MS: {ms} ms")
    if settings.get('show_engine', True): chips.append(f"ENGINE: {str(engine).upper()}")
    header = []
    if settings.get('show_model', True): header.append(model)
    if settings.get('show_game', True): header.append(game)
    scale = float(settings.get('font_scale',1.0) or 1.0)
    radius = int(settings.get('corner_radius',16) or 16)
    chip_html=''.join([f"<span style='padding:4px 8px;border-radius:999px;border:1px solid {th['box_border']};font-size:{12*scale:.0f}px;color:{th['title_color']};background:rgba(255,255,255,.06);margin-right:6px'>{html.escape(c)}</span>" for c in chips])
    speaker_html = f"<div style='color:{th['accent_color']};font-weight:700;font-size:{20*scale:.0f}px;margin-bottom:6px'>{html.escape(speaker)}</div>" if speaker and settings.get('show_speaker', True) else ''
    ec = _engine_color(str(engine))
    corner = ''
    if settings.get('show_engine_corner', True):
        corner = f"<div style='position:absolute;right:14px;top:12px;width:26px;height:26px;border-top:4px solid {ec};border-right:4px solid {ec};border-top-right-radius:8px;opacity:.95'></div>"
    return f"<div style='position:relative;font-family:{theme['font_family']};background:{th['box_background']};border-left:4px solid {th['box_border']};border-top:1px solid rgba(255,255,255,.08);border-right:1px solid rgba(255,255,255,.08);border-bottom:1px solid rgba(255,255,255,.08);border-radius:{radius}px;box-shadow:{theme['shadow']};padding:14px 16px;color:{th['body_color']};min-height:104px'>{corner}<div style='display:flex;justify-content:space-between;align-items:center;gap:10px;padding-right:30px'><div style='font-size:{13*scale:.0f}px;color:{th['title_color']};font-weight:700'>{html.escape(' • '.join([x for x in header if x]))}</div><div>{chip_html}</div></div>{speaker_html}<div style='font-size:{18*scale:.0f}px;line-height:1.45;white-space:pre-wrap'>{html.escape(text)}</div></div>"
