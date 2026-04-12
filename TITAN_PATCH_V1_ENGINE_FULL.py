# TITAN_PATCH_V1_ENGINE_FULL.py
# Patches V1 engine to:
# - Show GAME + MS indicators using existing internal indicator system (no new UI)
# - Remap F11 to INTERVAL (auto snapshot) and restrict CAS to ` and Shift+F1
# - Keep STABLE/FREEZE/INTERVAL semantics unchanged
#
# Run: python TITAN_PATCH_V1_ENGINE_FULL.py
from __future__ import annotations

import re, os, shutil, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAMP = time.strftime("%Y%m%d_%H%M%S")

ENGINE_CANDIDATES = [
    "TitanMainV1_ENGINE.py",
    "TitanMainV1_CORE.py",
    "TitanMainV1_ORIG.py",
    # last resort: if V1 is still monolithic
    "TitanMainV1.py",
]

def log(msg: str):
    print(f"[V1PATCH] {msg}")

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def write(p: Path, s: str):
    p.write_text(s, encoding="utf-8", newline="\n")

def backup(p: Path) -> Path:
    bdir = ROOT / f"_backup_v1_engine_{STAMP}"
    bdir.mkdir(parents=True, exist_ok=True)
    dst = bdir / p.name
    shutil.copy2(p, dst)
    return dst

def pick_engine() -> Path | None:
    for name in ENGINE_CANDIDATES:
        p = ROOT / name
        if p.exists() and p.is_file():
            txt = read(p)
            # crude heuristic: real engine has BOOT/shortcut strings or OCR init
            if "[BOOT]" in txt or "snip" in txt.lower() or "keyboard.add_hotkey" in txt:
                return p
    return None

HELPERS = r