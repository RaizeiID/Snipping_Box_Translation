"""ORT v8.8.5 bad-cache shield.

Fuzzy/naturalized cache is useful for small OCR typos, but low-OCR corrupted
frames must not be allowed to look like stable final output. This shield marks
bad cache cases so the overlay treats them as preview/hold rather than final.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from app.runtime.render_signature import ocr_corruption_score, words

@dataclass(frozen=True)
class BadCacheDecision:
    allow: bool
    reason: str
    corruption: float

class BadCacheShield:
    def __init__(self, *, threshold: float = 0.50, min_words: int = 4) -> None:
        self.threshold = float(threshold)
        self.min_words = int(min_words)

    @classmethod
    def from_env(cls) -> "BadCacheShield":
        return cls(
            threshold=float(os.environ.get("ORT_BAD_CACHE_CORRUPTION_THRESHOLD", "0.50")),
            min_words=int(os.environ.get("ORT_BAD_CACHE_MIN_WORDS", "4")),
        )

    def check(self, source: str, *, cache_label: str = "", ocr_percent: int = 0) -> BadCacheDecision:
        cache_u = str(cache_label or "").upper()
        if cache_u not in {"HIT_STABLE_FINAL", "NATURALIZED_CACHE", "SCOPED_CACHE", "LEGACY_HIT"}:
            return BadCacheDecision(True, "not_cache_final", 0.0)
        corr = ocr_corruption_score(source)
        if int(ocr_percent or 0) <= 50 and len(words(source)) >= self.min_words and corr >= self.threshold:
            return BadCacheDecision(False, "low_ocr_corrupted_cache_blocked", corr)
        return BadCacheDecision(True, "cache_ok", corr)
