from __future__ import annotations

import json
import time
import html
from pathlib import Path
from typing import Any, Dict

BASE = Path(__file__).resolve().parents[2]
PRESET_FILE = BASE / "configs" / "model_user_presets.json"


def _load_all() -> Dict[str, Any]:
    try:
        if PRESET_FILE.exists():
            data = json.loads(PRESET_FILE.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_all(data: Dict[str, Any]) -> None:
    PRESET_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_stale_fast_default(title: str, item: Dict[str, Any]) -> bool:
    """v8.4.5: ignore autosaved old Fast defaults so the new OCR/latency retune applies.

    Only resets values matching the old built-in defaults. Real custom values are kept.
    """
    t = str(title or "").lower()
    if not isinstance(item, dict) or str(item.get("version", "")) >= "v8.4.5":
        return False
    try:
        ocr = int(item.get("ocr_resolution", -1))
        interval = int(item.get("interval_ms", -1))
    except Exception:
        return False
    if "fast v1" in t and ocr == 55 and interval >= 90:
        return True
    if "fast v2" in t and ocr == 60 and interval >= 90:
        return True
    if "fast idn" in t and ocr == 55 and interval >= 90:
        return True
    return False



def _is_stale_lite_default(title: str, item: Dict[str, Any]) -> bool:
    """v8.4.5: ignore autosaved old Lite/Lite IDN defaults so final OCR ladder applies.

    Only resets values matching v8.4.2/v8.4.3 built-in Lite defaults. Real custom values are kept.
    """
    t = str(title or "").lower()
    if not isinstance(item, dict) or str(item.get("version", "")) >= "v8.4.5":
        return False
    try:
        ocr = int(item.get("ocr_resolution", -1))
        interval = int(item.get("interval_ms", -1))
    except Exception:
        return False
    old = {1: (48, {240, 260}), 2: (50, {310, 330}), 3: (52, {370, 390}), 4: (53, {410, 430}), 5: (55, {460, 480})}
    for level, (old_ocr, intervals) in old.items():
        if f"lite" in t and f"v{level}" in t and ocr == old_ocr and interval in intervals:
            return True
    return False

def get_model_user_preset(model_title: str) -> Dict[str, Any]:
    data = _load_all()
    title = str(model_title or "")
    item = data.get(title, {})
    if isinstance(item, dict) and (_is_stale_fast_default(title, item) or _is_stale_lite_default(title, item)):
        return {}
    return item if isinstance(item, dict) else {}


def save_model_user_preset(model_title: str, *, mode: str, engine: str, interval_ms: int, ocr_resolution: int) -> Dict[str, Any]:
    title = str(model_title or "").strip()
    if not title:
        raise ValueError("model_title is required")
    data = _load_all()
    item = {
        "mode": str(mode or "auto").lower(),
        "engine": str(engine or "hybrid").lower(),
        "interval_ms": int(interval_ms),
        "ocr_resolution": int(ocr_resolution),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "v8.7.2",
    }
    data[title] = item
    _write_all(data)
    return item


def reset_model_user_preset(model_title: str) -> bool:
    title = str(model_title or "").strip()
    data = _load_all()
    existed = title in data
    if existed:
        data.pop(title, None)
        _write_all(data)
    return existed


def describe_model_user_preset(model_title: str) -> str:
    item = get_model_user_preset(model_title)
    if not item:
        return "Belum ada default kustom untuk model ini. Saat model dipilih, ORT memakai default bawaan model."
    return (
        "Default kustom aktif untuk model ini: "
        f"mode={item.get('mode','-')} / engine={item.get('engine','-')} / "
        f"interval={item.get('interval_ms','-')}ms / OCR={item.get('ocr_resolution','-')}% "
        f"(disimpan {item.get('updated_at','-')})."
    )



def model_user_preset_is_modified(model_title: str) -> bool:
    """Return True when the selected model has user-modified defaults."""
    return bool(get_model_user_preset(model_title))


def describe_model_user_preset_short(model_title: str) -> str:
    item = get_model_user_preset(model_title)
    if not item:
        return "Default bawaan aktif."
    return (
        f"Modification aktif: {item.get('mode','-')} / {item.get('engine','-')} / "
        f"{item.get('interval_ms','-')}ms / OCR {item.get('ocr_resolution','-')}%."
    )


def model_user_preset_badge_html(model_title: str) -> str:
    """Small WebUI badge shown near the model picker.

    v8.3.4: no explicit save button. User changes are remembered automatically per model,
    and this badge shows when the selected model differs from its built-in defaults.
    """
    item = get_model_user_preset(model_title)
    title = html.escape(str(model_title or "Model"))
    if not item:
        return (
            "<div class='model-default-panel model-default-clean'>"
            "<span class='model-default-badge'>• Default bawaan</span>"
            "<small>Setiap perubahan mode/engine/interval/OCR akan tersimpan otomatis untuk model ini.</small>"
            "</div>"
        )
    mode = html.escape(str(item.get('mode', '-')))
    engine = html.escape(str(item.get('engine', '-')))
    interval = html.escape(str(item.get('interval_ms', '-')))
    ocr = html.escape(str(item.get('ocr_resolution', '-')))
    updated = html.escape(str(item.get('updated_at', '-')))
    return (
        "<div class='model-default-panel model-default-modified'>"
        "<span class='model-modification-badge'>• Modification</span>"
        f"<small>{title}: {mode} / {engine} / {interval}ms / OCR {ocr}% · autosaved {updated}</small>"
        "</div>"
    )
