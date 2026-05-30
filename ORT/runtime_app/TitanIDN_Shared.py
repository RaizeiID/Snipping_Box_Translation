# -*- coding: utf-8 -*-
"""
TitanIDN_Shared.py

UPDATE NOTES (2026-01-05)  | PACK: TitanCore_V2 + IDN MultiModel (6.4-IDN-1)
- Shared helpers untuk semua *_IDN:
  1) Protect/restore UNIQUE_TERMS memakai token ⟦UTx⟧ supaya naturalizer tidak merusak istilah.
  2) Patch aman untuk _safe_save_json (fix: "dictionary changed size during iteration").
  3) Util env parsing sederhana.

Catatan:
- UNIQUE_TERMS diambil dari TitanMainV2.UNIQUE_TERMS jika tersedia, jika tidak -> baca unique_terms.json.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, Tuple, List, Any

def env_bool(name: str, default: bool=False) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    if v in ("1","true","yes","y","on"): return True
    if v in ("0","false","no","n","off"): return False
    return default

def env_str(name: str, default: str="") -> str:
    return (os.environ.get(name) or default).strip()

def env_int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except Exception:
        return default

def _load_unique_terms() -> List[str]:
    # Prefer in-memory list
    try:
        import TitanMainV2 as tm  # type: ignore
        ut = getattr(tm, "UNIQUE_TERMS", None)
        if isinstance(ut, list):
            return [str(x).strip() for x in ut if str(x).strip()]
    except Exception:
        pass

    # Fallback file
    try:
        path = os.path.join(os.path.dirname(__file__), "unique_terms.json")
        if os.path.exists(path):
            j = json.loads(open(path, "r", encoding="utf-8").read())
            if isinstance(j, dict) and isinstance(j.get("known"), list):
                return [str(x).strip() for x in j.get("known") if str(x).strip()]
            if isinstance(j, list):
                return [str(x).strip() for x in j if str(x).strip()]
    except Exception:
        pass
    return []

def protect_terms(text: str, terms: List[str]) -> Tuple[str, Dict[str, str]]:
    out = text or ""
    mapping: Dict[str, str] = {}
    idx = 0
    for term in sorted(set(terms), key=len, reverse=True):
        if len(term) < 2:
            continue
        pat = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        if not pat.search(out):
            continue
        token = f"⟦UT{idx}⟧"
        idx += 1
        out = pat.sub(token, out)
        mapping[token] = term
    return out, mapping

def restore_terms(text: str, mapping: Dict[str, str]) -> str:
    out = text or ""
    for token, term in mapping.items():
        out = out.replace(token, term)
    return out

def patch_safe_save_json(tm_module: Any) -> None:
    """
    Fix umum: saat exit/save cache, dict berubah di tengah iterasi => crash.
    Kita copy dict/list sebelum dipassing ke _safe_save_json original.
    """
    try:
        if not hasattr(tm_module, "_safe_save_json"):
            return
        orig = tm_module._safe_save_json
        if getattr(tm_module, "_IDN_SAFE_SAVE_PATCHED", False):
            return

        def safe(path, data):
            try:
                if isinstance(data, dict):
                    data = dict(data)
                elif isinstance(data, list):
                    data = list(data)
            except Exception:
                pass
            return orig(path, data)

        tm_module._safe_save_json = safe  # type: ignore
        tm_module._IDN_SAFE_SAVE_PATCHED = True
    except Exception:
        pass
