from __future__ import annotations
import json, shutil, time
from pathlib import Path
from typing import Iterable
from .app_state import reset_state

SETTING_FILES = [
    "webui_prefs.json", "runtime_paths.json", "online_assist_config.json",
    "data_processing_settings.json", "ui_settings.json", "shortcut_config.json",
    "configs/app_state.json", "configs/ui_layout_settings.json", "configs/user_settings.json",
]

def _base(base_dir=None) -> Path:
    return Path(base_dir or Path(__file__).resolve().parents[2]).resolve()

def backup_settings(base_dir=None) -> Path:
    base = _base(base_dir)
    out = base / "backups" / ("settings_backup_" + time.strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    for rel in SETTING_FILES:
        src = base / rel
        if src.exists() and src.is_file():
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return out

def reset_settings(scope: str = "all", base_dir=None, backup: bool = True) -> str:
    base = _base(base_dir)
    backed = backup_settings(base) if backup else None
    scope = (scope or "all").lower()
    remove = []
    if scope in {"all", "ui"}:
        remove += ["webui_prefs.json", "ui_settings.json", "configs/ui_layout_settings.json"]
    if scope in {"all", "runtime"}:
        remove += ["runtime_paths.json", "configs/app_state.json"]
    if scope in {"all", "online"}:
        remove += ["online_assist_config.json"]
    if scope in {"all", "data"}:
        remove += ["data_processing_settings.json"]
    for rel in remove:
        try:
            (base / rel).unlink(missing_ok=True)
        except Exception:
            pass
    reset_state(base)
    msg = f"Reset settings scope={scope} selesai."
    if backed:
        msg += f" Backup: {backed}"
    return msg
