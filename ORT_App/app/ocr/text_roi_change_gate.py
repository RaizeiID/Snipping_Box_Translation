from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Optional


@dataclass(frozen=True)
class TextROIChangeDecision:
    run: bool
    reason: str
    distance: int = 0
    changed_ratio: float = 0.0
    sleep_ms: int = 0


class TextROIChangeGate:
    def __init__(
        self,
        *,
        threshold: float = 0.018,
        max_hold_ms: int = 15000,
        min_run_gap_ms: int = 90,
        confirm_delay_ms: int = 450,
        top_ratio: float = 0.02,
        bottom_ratio: float = 0.98,
        left_ratio: float = 0.01,
        right_ratio: float = 0.99,
        enabled: bool = True,
    ) -> None:
        self.threshold = max(0.001, min(0.50, float(threshold)))
        self.max_hold_ms = max(250, int(max_hold_ms))
        self.min_run_gap_ms = max(0, int(min_run_gap_ms))
        self.confirm_delay_ms = max(100, int(confirm_delay_ms))
        self.top_ratio = max(0.0, min(0.90, float(top_ratio)))
        self.bottom_ratio = max(self.top_ratio + 0.05, min(1.0, float(bottom_ratio)))
        self.left_ratio = max(0.0, min(0.90, float(left_ratio)))
        self.right_ratio = max(self.left_ratio + 0.05, min(1.0, float(right_ratio)))
        self.enabled = bool(enabled)
        self._last_signature: Optional[Any] = None
        self._last_run_ts = 0.0
        self._confirm_pending = False

    @classmethod
    def from_env(cls, profile: str = "auto_story") -> "TextROIChangeGate":
        profile = str(profile or "auto_story").lower()
        default_hold = 15000 if profile == "auto_story" else (8000 if profile == "interval_auto" else 900)
        return cls(
            threshold=float(os.environ.get("ORT_TEXT_ROI_CHANGE_THRESHOLD", "0.018")),
            max_hold_ms=int(os.environ.get("ORT_TEXT_ROI_MAX_HOLD_MS", str(default_hold))),
            min_run_gap_ms=int(os.environ.get("ORT_TEXT_ROI_MIN_RUN_GAP_MS", "90")),
            confirm_delay_ms=int(os.environ.get("ORT_TEXT_ROI_CONFIRM_DELAY_MS", "450")),
            top_ratio=float(os.environ.get("ORT_TEXT_ROI_TOP", "0.02")),
            bottom_ratio=float(os.environ.get("ORT_TEXT_ROI_BOTTOM", "0.98")),
            left_ratio=float(os.environ.get("ORT_TEXT_ROI_LEFT", "0.01")),
            right_ratio=float(os.environ.get("ORT_TEXT_ROI_RIGHT", "0.99")),
            enabled=os.environ.get("ORT_TEXT_ROI_CHANGE_GATE", "1") != "0",
        )

    def _signature(self, frame_rgb: Any):
        import cv2
        import numpy as np

        height, width = frame_rgb.shape[:2]
        y1 = max(0, min(height - 1, int(height * self.top_ratio)))
        y2 = max(y1 + 1, min(height, int(height * self.bottom_ratio)))
        x1 = max(0, min(width - 1, int(width * self.left_ratio)))
        x2 = max(x1 + 1, min(width, int(width * self.right_ratio)))
        roi = frame_rgb[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) if len(roi.shape) == 3 else roi
        target_w = 72
        target_h = max(12, min(32, int(target_w * gray.shape[0] / max(1, gray.shape[1]))))
        small = cv2.resize(gray, (target_w, target_h), interpolation=cv2.INTER_AREA)
        smooth = cv2.GaussianBlur(small, (0, 0), 1.15)
        local_contrast = cv2.absdiff(small, smooth)
        grad_x = cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.magnitude(grad_x, grad_y)
        gradient = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX).astype("uint8")
        text_edges = (local_contrast >= 9) | (gradient >= 96)
        return text_edges.astype("uint8")

    @staticmethod
    def _change_ratio(current: Any, previous: Any) -> float:
        import numpy as np

        if current.shape != previous.shape:
            return 1.0
        return float(np.count_nonzero(current != previous)) / float(max(1, current.size))

    def should_run(self, frame_rgb: Any, *, manual: bool = False) -> TextROIChangeDecision:
        if not self.enabled or manual:
            return TextROIChangeDecision(True, "disabled_or_manual")
        now = time.monotonic()
        try:
            signature = self._signature(frame_rgb)
        except Exception:
            return TextROIChangeDecision(True, "signature_error")
        if self._last_signature is None:
            self._last_signature = signature
            self._last_run_ts = now
            self._confirm_pending = True
            return TextROIChangeDecision(True, "first_text_roi")

        ratio = self._change_ratio(signature, self._last_signature)
        distance = int(round(ratio * int(signature.size)))
        elapsed_ms = int((now - self._last_run_ts) * 1000)
        if ratio >= self.threshold:
            if self.min_run_gap_ms and elapsed_ms < self.min_run_gap_ms:
                return TextROIChangeDecision(False, "changed_but_gap", distance, ratio, self.min_run_gap_ms - elapsed_ms)
            self._last_signature = signature
            self._last_run_ts = now
            self._confirm_pending = True
            return TextROIChangeDecision(True, "text_roi_changed", distance, ratio)
        if self._confirm_pending and elapsed_ms >= self.confirm_delay_ms:
            self._last_signature = signature
            self._last_run_ts = now
            self._confirm_pending = False
            return TextROIChangeDecision(True, "text_stability_confirm", distance, ratio)
        if elapsed_ms >= self.max_hold_ms:
            self._last_signature = signature
            self._last_run_ts = now
            return TextROIChangeDecision(True, "static_probe", distance, ratio)
        remaining = max(5, self.max_hold_ms - elapsed_ms)
        return TextROIChangeDecision(False, "static_text_roi", distance, ratio, min(80, remaining))

    def reset(self) -> None:
        self._last_signature = None
        self._last_run_ts = 0.0
        self._confirm_pending = False

    def request_confirmation(self) -> None:
        self._confirm_pending = True
