"""ORT v8.8.3 render signature helpers.

Render signatures are used only for visual dedupe.  They intentionally avoid
heavy semantic analysis so Auto Story stays fast.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9']+")
_PUNCT_RE = re.compile(r"[\s\.,;:!\?\-_/\\\(\)\[\]\{\}\"`´]+")
_OCR_CONFUSIONS = str.maketrans({
    "0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "8": "b",
})


def strip_html(text: str) -> str:
    s = _TAG_RE.sub(" ", str(text or ""))
    return html.unescape(s)


def visual_signature(text: str) -> str:
    s = strip_html(text).casefold().strip()
    s = s.translate(_OCR_CONFUSIONS)
    s = s.replace("tmstill", "im still").replace("youre", "you're")
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compact_signature(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", visual_signature(text))


def words(text: str) -> list[str]:
    return _WORD_RE.findall(visual_signature(text))


def similarity(a: str, b: str) -> float:
    ca = compact_signature(a); cb = compact_signature(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    if ca.startswith(cb) or cb.startswith(ca):
        return min(len(ca), len(cb)) / max(1, max(len(ca), len(cb)))
    return SequenceMatcher(None, ca, cb).ratio()


def token_gain(old: str, new: str) -> int:
    return max(0, len(words(new)) - len(words(old)))


def is_substantial_update(old: str, new: str, *, min_token_gain: int = 3, min_char_gain: int = 18) -> bool:
    if not old:
        return bool(new)
    if len(strip_html(new)) >= len(strip_html(old)) + min_char_gain:
        return True
    if token_gain(old, new) >= min_token_gain:
        return True
    return False
