"""ORT v8.8.6 OCR Churn Rescue.

The goal is to make low-OCR profiles (40-45%) usable instead of simply saying
"not recommended". We do that with cheap heuristics:
- clean common glyph confusions;
- detect churn/noise so bad frames do not overwrite a better source;
- mark suspicious frames so cache/final commits are treated carefully;
- expose metrics for later long-session analysis.

This module does not raise the global OCR percentage and does not call OCR
again. It is a software-side "visor wiper" for muddy frames.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import os
import time

from app.runtime.render_signature import repair_ocr_text, visual_signature, ocr_corruption_score, words


@dataclass(frozen=True)
class OCRChurnDecision:
    text: str
    repaired: bool
    corruption: float
    churn: bool
    bad_cache_risk: bool
    force_hold: bool
    reason: str


class OCRChurnRescue:
    def __init__(self, *, low_ocr_threshold: int = 50, corruption_hold: float = 0.62, corruption_cache: float = 0.48) -> None:
        self.low_ocr_threshold = int(low_ocr_threshold)
        self.corruption_hold = float(corruption_hold)
        self.corruption_cache = float(corruption_cache)
        self._rescue_notes = []
        self._last_sig = ""
        self._last_ts = 0.0
        self._flip_count = 0

    @classmethod
    def from_env(cls) -> "OCRChurnRescue":
        return cls(
            low_ocr_threshold=int(os.environ.get("ORT_LOW_OCR_CHURN_THRESHOLD", "50")),
            corruption_hold=float(os.environ.get("ORT_OCR_CORRUPTION_HOLD", "0.62")),
            corruption_cache=float(os.environ.get("ORT_OCR_CORRUPTION_CACHE", "0.48")),
        )

    def analyze(self, text: str, *, ocr_percent: int = 0, mode: str = "", speaker: str = "") -> OCRChurnDecision:
        raw = str(text or "").strip()
        repaired = repair_ocr_text(raw)
        sig = visual_signature(repaired)
        now = time.time()
        sim = SequenceMatcher(None, sig, self._last_sig).ratio() if sig and self._last_sig else 1.0
        if sig and self._last_sig and sim < 0.58 and now - self._last_ts < 1.2:
            self._flip_count += 1
        elif now - self._last_ts > 1.5:
            self._flip_count = 0
        self._last_sig = sig or self._last_sig
        self._last_ts = now

        corruption = ocr_corruption_score(repaired)
        low = bool(int(ocr_percent or 0) <= self.low_ocr_threshold)
        churn = bool(low and self._flip_count >= 2)
        too_short_dirty = bool(low and corruption >= self.corruption_hold and len(words(repaired)) <= 5)
        bad_cache = bool(low and corruption >= self.corruption_cache)
        force_hold = bool(too_short_dirty and str(mode or "").upper() != "FREEZE")
        reason = "clean"
        if repaired != raw:
            reason = "repaired_common_ocr_confusions"
        if churn:
            reason = "low_ocr_churn_detected"
        if force_hold:
            reason = "low_ocr_corrupted_fragment_hold"
        return OCRChurnDecision(repaired, repaired != raw, corruption, churn, bad_cache, force_hold, reason)
