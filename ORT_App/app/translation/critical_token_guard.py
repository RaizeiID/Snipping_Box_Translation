"""Critical token revision policy for v8.7.3.

Prevents final-cache commit when identity/information-bearing tokens are likely
still resolving across OCR frames (Roman numerals and thin glyph contractions).
"""
from __future__ import annotations
import re

SUSPICIOUS_PATTERNS = (
    (re.compile(r"\bLevel\s+I[l1]\b", re.I), "roman_numeral_ambiguous"),
    (re.compile(r"\bII\s+need\b", re.I), "possible_ill_contraction"),
    (re.compile(r"\bl['’]Ve\b", re.I), "possible_ive_contraction"),
    (re.compile(r"\bl['’]ll\b", re.I), "possible_ill_contraction"),
)


def revision_reason(text: str) -> str:
    source = str(text or "")
    for pattern, reason in SUSPICIOUS_PATTERNS:
        if pattern.search(source):
            return reason
    return ""


def safe_normalize(text: str) -> str:
    source = str(text or "")
    source = re.sub(r"\bl['’]Ve\b", "I've", source, flags=re.I)
    source = re.sub(r"\bl['’]ll\b", "I'll", source, flags=re.I)
    return source


def can_commit_final(text: str) -> tuple[bool, str]:
    reason = revision_reason(text)
    return (not bool(reason), reason or "critical_tokens_stable")
