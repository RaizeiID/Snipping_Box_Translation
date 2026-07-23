"""ORT v8.9.1 Overlay language guard.

Prevents raw English OCR/source previews from leaking into the user-facing
translation overlay. Source text remains available in logs/debug events.
"""
from __future__ import annotations

import os
import re

_EN_WORDS = re.compile(r"\b(?:the|you|your|we|our|they|she|he|it|that|this|what|why|with|from|because|should|would|could|don't|can't|will|if|then|not|are|is|am|be|been|have|has|had|look|call|healing)\b", re.I)
_ID_WORDS = re.compile(r"\b(?:yang|dan|atau|aku|saya|kamu|kau|dia|mereka|kita|kami|tidak|bukan|akan|sudah|telah|dengan|karena|untuk|dari|ini|itu|harus|bisa|dapat)\b", re.I)


def looks_like_english(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return False
    en = len(_EN_WORDS.findall(s))
    idn = len(_ID_WORDS.findall(s))
    alpha_words = re.findall(r"[A-Za-z']+", s)
    if len(alpha_words) < 3:
        return False
    return en >= max(2, idn + 2)


def looks_same_as_source(output: str, source: str) -> bool:
    o = re.sub(r"\W+", " ", str(output or "").lower()).strip()
    s = re.sub(r"\W+", " ", str(source or "").lower()).strip()
    if not o or not s:
        return False
    if o == s:
        return True
    # Most raw source previews are prefix/suffix variants during typewriter.
    return len(o) >= 12 and (o in s or s in o)


def make_indonesian_waiting_preview(source: str = "", *, reason: str = "") -> str:
    # Optional fallback only. v8.9.1 suppresses it by default to avoid visible
    # placeholder flicker in recordings; enable ORT_OVERLAY_SHOW_ID_WAITING_PREVIEW=1
    # if a visible waiting message is preferred.
    return "Menyiapkan terjemahan…"


def guard_overlay_text(output: str, source: str, *, trusted_preview: bool = False, held: bool = False) -> tuple[str, bool, str]:
    if os.environ.get("ORT_OVERLAY_ALLOW_ENGLISH_SOURCE", "0") == "1":
        return output, False, "english_source_allowed"
    out = str(output or "")
    src = str(source or "")
    if trusted_preview or held or looks_same_as_source(out, src):
        if looks_like_english(out) or looks_same_as_source(out, src):
            if os.environ.get("ORT_OVERLAY_SILENCE_ENGLISH_PREVIEW", "1") == "1":
                return "", True, "english_source_preview_silenced"
            return make_indonesian_waiting_preview(src), True, "english_source_preview_hidden"
    return out, False, "ok"
