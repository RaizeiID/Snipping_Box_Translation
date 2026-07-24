"""ORT v8.8.6 render signature and OCR quality helpers.

These helpers are deterministic and cheap. They are used only for visual
commit decisions, final-completeness checks, bad-cache shielding, and low-OCR
churn rescue. No ML model is called here.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9']+")
_PUNCT_RE = re.compile(r"[\s\.,;:!\?\-_/\\\(\)\[\]\{\}\"`´]+")
_TERMINAL_RE = re.compile(r"[.!?…][\"')\]]?\s*$")
_OCR_CONFUSIONS = str.maketrans({"0":"o","1":"l","3":"e","5":"s","7":"t","8":"b"})

# Conservative OCR repair patterns observed repeatedly in GFL2 logs.
# They do not invent story content; they normalize common glyph confusions.
_REPLACEMENTS = {
    "tmstill": "im still",
    "youre": "you're",
    "dont": "don't",
    "werent": "weren't",
    "didntexpect": "didn't expect",
    "ofcourse": "of course",
    "massne": "massive",
    "exploslon": "explosion",
    "exploslon": "explosion",
    "berryfiela": "berryfield",
    "berryfleld": "berryfield",
    "berryflold": "berryfield",
    "borryflold": "berryfield",
    "berrfield": "berryfield",
    "cocoons": "cocoon's",
    "lontln": "lentine",
    "lontin": "lentine",
    "tactlcal": "tactical",
    "intemal": "internal",
    "intemal": "internal",
    "proflted": "profited",
    "thls": "this",
    "mtel": "intel",
    "lvlv": "lviv",
    "lvn": "lviv",
    "lviy": "lviv",
    "wherent": "weren't",
    "nlkketa": "nikketa",
    "blig": "big",
    "sls": "sis",
    "hlena": "helena",
    "helna": "helena",
    "incldent": "incident",
    "inltlated": "initiated",
    "belf": "self",
}


def strip_html(text: str) -> str:
    s = _TAG_RE.sub(" ", str(text or ""))
    return html.unescape(s)


def terminal_punctuation(text: str) -> bool:
    return bool(_TERMINAL_RE.search(str(text or "").strip()))


def repair_ocr_text(text: str) -> str:
    """Repair very common OCR glitches without changing meaning.

    This is the "automatic visor wiper" for low OCR profiles: it cleans repeated
    mud-like glyph errors before similarity/cache/finalizer decisions. It does
    not raise the OCR percentage and does not call any heavy engine.
    """
    s = str(text or "")
    if not s:
        return s
    # common joined words from typewriter/OCR.
    s = re.sub(r"(?i)weren\s*tfast", "weren't fast", s)
    s = re.sub(r"(?i)didn\s*texpect", "didn't expect", s)
    s = re.sub(r"(?i)of\s*course", "of course", s)
    # word-level replacements only, preserving surrounding punctuation.
    def repl(m):
        w = m.group(0)
        lw = w.casefold()
        rw = _REPLACEMENTS.get(lw)
        if not rw:
            return w
        if w[:1].isupper():
            return rw[:1].upper() + rw[1:]
        return rw
    s = re.sub(r"[A-Za-z0-9']+", repl, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def visual_signature(text: str) -> str:
    s = strip_html(text).casefold().strip()
    s = repair_ocr_text(s).casefold()
    s = s.translate(_OCR_CONFUSIONS)
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
        return bool(str(new or "").strip())
    old_plain = strip_html(old)
    new_plain = strip_html(new)
    if len(new_plain) >= len(old_plain) + min_char_gain:
        return True
    if token_gain(old, new) >= min_token_gain:
        return True
    return False


def ocr_corruption_score(text: str) -> float:
    """Return a lightweight 0..1 corruption estimate.

    High values mean the text looks like low-OCR noise and should not be trusted
    for final cache or best-source overwrite. This is intentionally simple.
    """
    s = strip_html(text)
    if not s.strip():
        return 1.0
    toks = re.findall(r"[A-Za-z0-9']+", s)
    if not toks:
        return 1.0
    digit_words = sum(1 for t in toks if any(c.isdigit() for c in t) and any(c.isalpha() for c in t))
    no_vowel = sum(1 for t in toks if len(t) >= 5 and not re.search(r"[aeiouAEIOU]", t))
    weird_case = sum(1 for t in toks if len(t) >= 4 and sum(c.isupper() for c in t) >= 2 and not t.isupper())
    symbol_noise = len(re.findall(r"[^A-Za-z0-9\s.,!?;:'\-()\[\]…]", s))
    short_orphans = sum(1 for t in toks if len(t) == 1)
    raw = digit_words * 1.8 + no_vowel * 1.2 + weird_case * 0.8 + symbol_noise * 1.0 + short_orphans * 0.25
    return max(0.0, min(1.0, raw / max(5.0, len(toks) * 0.9)))
