"""Adaptive OCR readability guard for ORT Translation v8.7.6.

The guard is conservative: it never fabricates corrected text.  It scores an
initial OCR result and, for GFL2 story frames that look degraded, asks the
caller to run one higher-resolution OCR pass.  The better raw result is then
selected before translation/cache.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Optional

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*")
_MIXED_NOISE_RE = re.compile(r"(?:[a-z][A-Z][a-z]|[A-Za-z]\d[A-Za-z]|\d[A-Za-z]{2,}|[|{}\[\]<>])")
_VOWELS = set("aeiouyAEIOUY")


@dataclass(frozen=True)
class ReadabilityAssessment:
    score: float
    corruption: float
    word_count: int
    needs_rescue: bool
    reason: str


def score_text(text: str, applied_percent: int = 100, min_story_percent: int = 50) -> ReadabilityAssessment:
    raw = " ".join(str(text or "").split())
    words = _WORD_RE.findall(raw)
    if not raw or not words:
        return ReadabilityAssessment(0.0, 1.0, 0, True, "empty_or_no_words")
    alpha = sum(ch.isalpha() for ch in raw)
    signal = alpha / max(1, len(raw))
    suspicious = 0
    no_vowel = 0
    short_single = 0
    for word in words:
        if _MIXED_NOISE_RE.search(word):
            suspicious += 1
        if len(word) >= 4 and not (word.islower() or word.istitle() or word.isupper()):
            suspicious += 2
        if len(word) >= 4 and not any(ch in _VOWELS for ch in word):
            no_vowel += 1
        if len(word) == 1 and word.lower() not in {"a", "i"}:
            short_single += 1
    token_noise = (suspicious + no_vowel + short_single) / max(1, len(words))
    punctuation_noise = sum(ch in "|{}[]<>~`" for ch in raw) / max(1, len(raw))
    corruption = min(1.0, (token_noise * 0.62) + (punctuation_noise * 3.0) + max(0.0, 0.78 - signal))
    score = max(0.0, min(1.0, (signal * 0.62) + ((1.0 - corruption) * 0.38)))
    low_profile = int(applied_percent) < int(min_story_percent)
    long_enough = len(raw) >= 12 and len(words) >= 2
    degraded = corruption >= 0.16 or score < 0.72
    needs = bool(long_enough and (degraded or low_profile))
    reason = "low_story_profile" if low_profile and not degraded else ("corruption_detected" if degraded else "readable")
    return ReadabilityAssessment(round(score, 4), round(corruption, 4), len(words), needs, reason)


def rescue_percent(applied_percent: int, min_story_percent: int = 50, maximum: int = 65) -> int:
    value = int(applied_percent)
    if value < min_story_percent:
        return min(maximum, max(min_story_percent, value + 10))
    return min(maximum, value + 5)


def select_better_text(initial: str, retry: str, applied_percent: int, retry_percent: int, min_story_percent: int = 50):
    base = score_text(initial, applied_percent, min_story_percent)
    alt = score_text(retry, retry_percent, min_story_percent)
    improvement = alt.score - base.score
    use_retry = bool(retry.strip()) and (
        improvement >= 0.025
        or (base.needs_rescue and alt.corruption + 0.035 < base.corruption)
        or (int(applied_percent) < int(min_story_percent) and int(retry_percent) >= int(min_story_percent) and alt.score >= base.score - 0.04)
    )
    return (retry if use_retry else initial), base, alt, use_retry
