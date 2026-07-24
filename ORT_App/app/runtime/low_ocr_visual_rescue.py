"""ORT v8.8.7 Low-OCR Visual Rescue planner.

This module does not run OCR by itself. It decides when low-OCR frames look
muddy enough that runtime should prefer consensus/final-lane rescue and avoid
trusting cache/preview. It is intentionally cheap and safe for Lite/Fast.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from app.runtime.render_signature import ocr_corruption_score, words, repair_ocr_text


@dataclass(frozen=True)
class VisualRescueDecision:
    rescue: bool
    text: str
    reason: str
    corruption: float
    suggested_profile: str


class LowOCRVisualRescue:
    def __init__(self, *, low_ocr_threshold: int = 50, corruption_threshold: float = 0.52) -> None:
        self.low_ocr_threshold = int(low_ocr_threshold)
        self.corruption_threshold = float(corruption_threshold)

    @classmethod
    def from_env(cls) -> "LowOCRVisualRescue":
        return cls(
            low_ocr_threshold=int(os.environ.get("ORT_LOW_OCR_VISUAL_RESCUE_THRESHOLD", "50")),
            corruption_threshold=float(os.environ.get("ORT_LOW_OCR_VISUAL_RESCUE_CORRUPTION", "0.52")),
        )

    def analyze(self, text: str, *, ocr_percent: int = 0, mode: str = "") -> VisualRescueDecision:
        cleaned = repair_ocr_text(str(text or "").strip())
        corr = ocr_corruption_score(cleaned)
        low = int(ocr_percent or 0) <= self.low_ocr_threshold
        enough = len(words(cleaned)) >= 3
        rescue = bool(low and enough and corr >= self.corruption_threshold and str(mode or "").upper() != "FREEZE")
        profile = "contrast_sharpen_retry_hint" if rescue else "none"
        reason = "low_ocr_visual_rescue_needed" if rescue else "visual_rescue_not_needed"
        return VisualRescueDecision(rescue, cleaned, reason, corr, profile)
