# -*- coding: utf-8 -*-
"""
TitanIndonesianLocalizer.py

Version : 2.2.0 (2026-01-06)
Update  :
- Naturalizer FAST/BALANCED/MAX
- Bersihin noise OCR (|, 。, spasi ganda)
- Pola kalimat biar lebih natural buat orang Indonesia
"""

from __future__ import annotations

import os
import re
from typing import Optional

_LEVEL_DEFAULT = os.getenv("TITAN_IDN_LEVEL", "BALANCED").strip().upper()

_RE_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_RE_CJK_PERIOD = re.compile(r"。")
_RE_WEIRD_PIPE = re.compile(r"[|¦]")
_RE_SPACE_PUNCT = re.compile(r"\s+([,.!?])")
_RE_PUNCT_SPACE = re.compile(r"([,.!?])([^\s])")

_RULES_FAST = [
    (_RE_CJK_PERIOD, "."),
    (_RE_WEIRD_PIPE, " "),
    (_RE_MULTI_SPACE, " "),
    (_RE_SPACE_PUNCT, r"\1"),
    (_RE_PUNCT_SPACE, r"\1 \2"),
]

_RULES_BALANCED = _RULES_FAST + [
    (re.compile(r"\bMe neither\.\b", re.I), "Aku juga nggak."),
    (re.compile(r"\bNo problem\.\b", re.I), "Gampang."),
    (re.compile(r"\bThat's clever\b", re.I), "Wah, pinter juga"),
    (re.compile(r"\bAll things considered\b,?", re.I), "Kalau dipikir-pikir,"),
    (re.compile(r"\bWhile it isn't very likely\b,?", re.I), "Meski kecil kemungkinannya,"),
    (re.compile(r"\bthere's still a chance\b", re.I), "tetap ada kemungkinan"),
    (re.compile(r"\blead\b", re.I), "petunjuk"),
    (re.compile(r"\btrap\b", re.I), "jebakan"),
    (re.compile(r"\bRush hour\b", re.I), "jam sibuk"),
]

_RULES_MAX = _RULES_BALANCED + [
    (
        re.compile(r"\bIt's not realistic to expect ([A-Za-z0-9_']+) to\b", re.I),
        r"Nggak realistis kalau kita berharap \1 bisa",
    ),
    (re.compile(r"\bSuccess isn't everything\b", re.I), "Yang penting bukan cuma berhasil"),
    (re.compile(r"\bPlenty\b[.!]?", re.I), "Bisa banget."),
    (re.compile(r"\bUgh\.\.\.\b", re.I), "Hadeh..."),
    (re.compile(r"\bMaybe less\b", re.I), "Bahkan mungkin kurang dari itu"),
    (re.compile(r"\bEveryone good\?\b", re.I), "Semua aman?"),
]


def _apply_rules(text: str, rules) -> str:
    out = text
    for pat, repl in rules:
        out = pat.sub(repl, out)
    return out.strip()


def localize_id(text: str, kind: str = "DIALOG", level: Optional[str] = None) -> str:
    if not text:
        return text

    lvl = (level or _LEVEL_DEFAULT).strip().upper()
    if lvl not in ("FAST", "BALANCED", "MAX"):
        lvl = "BALANCED"

    if lvl == "FAST":
        out = _apply_rules(text, _RULES_FAST)
    elif lvl == "MAX":
        out = _apply_rules(text, _RULES_MAX)
    else:
        out = _apply_rules(text, _RULES_BALANCED)

    # rapikan monolog ()
    if kind.upper() == "MONOLOG":
        if text.strip().startswith("(") and not out.startswith("("):
            out = "(" + out
        if text.strip().endswith(")") and not out.endswith(")"):
            out = out + ")"

    return out
