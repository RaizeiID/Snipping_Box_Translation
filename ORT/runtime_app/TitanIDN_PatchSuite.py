# -*- coding: utf-8 -*-
"""TitanIDN_PatchSuite.py

Version : 1.0.1
Updated : 2026-01-06

Fungsi:
- Aktifkan mode *_IDN lewat env flags.
- Paksa stdout UTF-8 agar simbol/emoji tidak crash di Windows.
- Jika modul localizer/glossary ada, akan di-init (opsional).

Catatan:
- Patch ini dibuat aman: kalau hook tidak ketemu, base script tetap jalan normal.
"""

from __future__ import annotations

import os
import sys

try:
    from TitanIndonesianLocalizer import IndonesianLocalizer  # type: ignore
except Exception:
    IndonesianLocalizer = None  # type: ignore

try:
    from TitanLoreGlossary import LoreGlossary  # type: ignore
except Exception:
    LoreGlossary = None  # type: ignore

_INSTALLED = False


def _force_utf8_stdout() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def install_idn_patch(profile: str = "IDN_MAX") -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    _force_utf8_stdout()

    os.environ.setdefault("TITAN_IDN_MODE", "1")
    os.environ.setdefault("TITAN_IDN_PROFILE", profile)

    # optional init
    try:
        if IndonesianLocalizer:
            IndonesianLocalizer(profile=profile)
        if LoreGlossary:
            LoreGlossary()
    except Exception:
        pass

    _INSTALLED = True
