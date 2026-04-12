# -*- coding: utf-8 -*-
"""
TitanLoreGlossary.py

Version : 1.2.0 (2026-01-06)
Update  :
- Akronim diketahui -> warna biru laut tua + (kepanjangan)
- Akronim tidak diketahui -> warna coklat + "AKRONIM" (tanpa kepanjangan)
- OGAS dipaksa mode unknown-lore => tampil "OGAS" warna coklat (tanpa kepanjangan) sesuai request
- Dukungan override lore via titan_glossary_custom.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

# Warna sesuai request
ACRONYM_COLOR_KNOWN_HEX = "#003B73"   # dark sea blue
ACRONYM_COLOR_UNKNOWN_HEX = "#8B4513" # brown (saddle brown)

UNKNOWN_EXPANSION_IDN = None  # None => treat as unknown-lore

# Regex akronim OCR: 2-9 char, kapital/angka
_ACR_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,8}\b")

# Terms (Doll/Droid) - dijelaskan dalam kurung (tidak diwarnai)
TERMS_GLOBAL: Dict[str, str] = {
    "Doll": "Boneka Tempur/Android",
    "Dolls": "Boneka Tempur/Android",
    "Droid": "Robot patroli",
    "Droids": "Robot patroli",
}

# Akronim global yang AMAN (bukan lore game)
# (yang kamu yakin dan memang umum)
ACRONYMS_GLOBAL: Dict[str, Optional[str]] = {
    "PMC": "Private Military Company",
    "AI": "Artificial Intelligence",
    "UAV": "Unmanned Aerial Vehicle",
    "EMP": "Electromagnetic Pulse",
}

# Akronim yang sengaja DIPAKSA unknown-lore (tampil "AKRONIM" coklat, tanpa kepanjangan)
FORCE_UNKNOWN_ACRONYMS = {"OGAS", "URNC"}  # URNC/OGAS jangan ditebak dari luar game

_CUSTOM_PATH = Path(__file__).with_name("titan_glossary_custom.json")


def _load_custom() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """
    titan_glossary_custom.json format:
    {
      "acronyms": { "URNC": "Kepanjangan lore", "OGAS": null },
      "terms": { "Doll": "..." }
    }

    - acronym value = string => dianggap known
    - acronym value = null => dipaksa unknown-lore (coklat + kutip)
    """
    if not _CUSTOM_PATH.exists():
        return {}, {}
    try:
        data = json.loads(_CUSTOM_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}, {}
        acr_raw = data.get("acronyms", {}) or {}
        terms_raw = data.get("terms", {}) or {}

        acr: Dict[str, Optional[str]] = {}
        if isinstance(acr_raw, dict):
            for k, v in acr_raw.items():
                kk = str(k).strip().upper()
                if not kk:
                    continue
                if v is None:
                    acr[kk] = None
                else:
                    vv = str(v).strip()
                    acr[kk] = vv if vv else None

        terms: Dict[str, str] = {}
        if isinstance(terms_raw, dict):
            for k, v in terms_raw.items():
                kk = str(k).strip()
                vv = str(v).strip()
                if kk and vv:
                    terms[kk] = vv

        return acr, terms
    except Exception:
        return {}, {}


def _merge_glossary() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    acr = dict(ACRONYMS_GLOBAL)
    terms = dict(TERMS_GLOBAL)

    custom_acr, custom_terms = _load_custom()
    if custom_acr:
        acr.update(custom_acr)
    if custom_terms:
        terms.update(custom_terms)

    # Force unknown-lore
    for a in FORCE_UNKNOWN_ACRONYMS:
        # custom bisa override; kalau user isi string, dianggap known
        if a not in custom_acr:
            acr[a] = None

    return acr, terms


def _already_has_parentheses(text: str, idx_after_token: int) -> bool:
    j = idx_after_token
    while j < len(text) and text[j] == " ":
        j += 1
    return j < len(text) and text[j] == "("


def _safe_append_parentheses(original: str, token_end: int, appendix: str) -> str:
    if _already_has_parentheses(original, token_end):
        return original
    return original[:token_end] + f" ({appendix})" + original[token_end:]


def annotate_plain(text: str, enable_terms: bool = True) -> str:
    """
    Plain text output:
    - Known acronym: "PMC (Private Military Company)"
    - Unknown acronym: "\"OGAS\"" (kutip saja, no parentheses)
    - Terms: "Doll (Boneka Tempur/Android)"
    """
    if not text:
        return text

    acr_map, term_map = _merge_glossary()
    out = text

    # Acronyms: annotate first occurrence each
    seen = set()
    for m in list(_ACR_RE.finditer(out)):
        tok = m.group(0).upper()
        if tok in seen:
            continue
        seen.add(tok)

        expansion = acr_map.get(tok, None)
        # refresh locate in current out (index may shift)
        mm = re.search(rf"\b{re.escape(tok)}\b", out)
        if not mm:
            continue

        if expansion:
            out = _safe_append_parentheses(out, mm.end(), expansion)
        else:
            # unknown-lore => quote only
            # avoid double quotes if already quoted
            if mm.start() > 0 and out[mm.start() - 1] == '"' and mm.end() < len(out) and out[mm.end()] == '"':
                continue
            out = out[:mm.start()] + f"\"{tok}\"" + out[mm.end():]

    # Terms (one occurrence)
    if enable_terms and term_map:
        for term, meaning in term_map.items():
            pat = re.compile(rf"(?<!\w)({re.escape(term)})(?!\w)")
            mm = pat.search(out)
            if not mm:
                continue
            if _already_has_parentheses(out, mm.end(1)):
                continue
            out = _safe_append_parentheses(out, mm.end(1), meaning)

    return out


def annotate_html_escaped(escaped_text: str, enable_terms: bool = True) -> str:
    """
    Input: text sudah di-html-escape (belum ada tag).
    Output: inject span:
    - Known acronym -> biru laut tua + (kepanjangan)
    - Unknown acronym -> coklat + "AKRONIM" (tanpa kepanjangan)
    """
    if not escaped_text:
        return escaped_text

    acr_map, term_map = _merge_glossary()
    out = escaped_text

    # Replace acronyms left-to-right (safer)
    cursor = 0
    pieces = []
    while True:
        m = _ACR_RE.search(out, cursor)
        if not m:
            pieces.append(out[cursor:])
            break

        pieces.append(out[cursor:m.start()])
        tok = m.group(0).upper()
        expansion = acr_map.get(tok, None)

        # if already has parentheses right after -> keep as is
        if _already_has_parentheses(out, m.end()):
            pieces.append(tok)
        else:
            if expansion:
                colored = f'<span style="color:{ACRONYM_COLOR_KNOWN_HEX}; font-weight:800;">{tok}</span>'
                pieces.append(f"{colored} ({expansion})")
            else:
                # unknown-lore => brown + quotes
                colored = f'<span style="color:{ACRONYM_COLOR_UNKNOWN_HEX}; font-weight:900;">"{tok}"</span>'
                pieces.append(colored)

        cursor = m.end()

    out2 = "".join(pieces)

    # Terms annotate once (no color)
    if enable_terms and term_map:
        for term, meaning in term_map.items():
            pat = re.compile(rf"(?<!\w)({re.escape(term)})(?!\w)")
            mm = pat.search(out2)
            if not mm:
                continue
            if _already_has_parentheses(out2, mm.end(1)):
                continue
            out2 = out2[:mm.end(1)] + f" ({meaning})" + out2[mm.end(1):]

    return out2


def ensure_reserved_terms(extra: Optional[list] = None) -> list:
    base = [
        "PMC", "URNC", "OGAS",
        "Doll", "Dolls", "Droid", "Droids",
    ]
    if extra:
        for x in extra:
            if x and x not in base:
                base.append(x)
    return base
