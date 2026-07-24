from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class HashGateDecision:
    run: bool
    reason: str
    distance: int = 0
    sleep_ms: int = 0


class ImageHashGate:
    """Cheap image-change gate placed before EasyOCR.

    It prevents repeated OCR while a story/dialog frame is visually unchanged
    (for example while character voice is still playing after text is complete).
    The gate is intentionally dependency-light: cv2/numpy are imported only when
    computing the hash, and failure means "run OCR" rather than blocking.
    """

    def __init__(self, threshold: int = 4, max_hold_ms: int = 650, min_run_gap_ms: int = 0, enabled: bool = True):
        self.threshold = int(threshold)
        self.max_hold_ms = int(max_hold_ms)
        self.min_run_gap_ms = int(min_run_gap_ms)
        self.enabled = bool(enabled)
        self._last_hash: Optional[int] = None
        self._last_run_ts = 0.0
        self._last_change_ts = 0.0

    @classmethod
    def from_env(cls, profile: str = "interval_auto") -> "ImageHashGate":
        profile = str(profile or "interval_auto").lower()
        enabled = os.environ.get("ORT_IMAGE_HASH_GATE", "1") != "0"
        if profile == "auto_story":
            threshold = int(os.environ.get("ORT_IMAGE_HASH_THRESHOLD", "3"))
            max_hold = int(os.environ.get("ORT_IMAGE_HASH_MAX_HOLD_MS", "450"))
        elif profile == "freeze_manual":
            threshold = int(os.environ.get("ORT_IMAGE_HASH_THRESHOLD", "5"))
            max_hold = int(os.environ.get("ORT_IMAGE_HASH_MAX_HOLD_MS", "900"))
        else:
            threshold = int(os.environ.get("ORT_IMAGE_HASH_THRESHOLD", "4"))
            max_hold = int(os.environ.get("ORT_IMAGE_HASH_MAX_HOLD_MS", "650"))
        gap = int(os.environ.get("ORT_IMAGE_HASH_MIN_RUN_GAP_MS", "0"))
        return cls(threshold=threshold, max_hold_ms=max_hold, min_run_gap_ms=gap, enabled=enabled)

    @staticmethod
    def _ahash(frame_rgb: Any) -> int:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY) if len(frame_rgb.shape) == 3 else frame_rgb
        small = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA)
        mean = float(np.mean(small))
        bits = (small > mean).astype("uint8").flatten()
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return int(value)

    @staticmethod
    def _distance(a: int, b: int) -> int:
        return int((int(a) ^ int(b)).bit_count())

    def should_run(self, frame_rgb: Any, *, manual: bool = False) -> HashGateDecision:
        if not self.enabled or manual:
            return HashGateDecision(True, "disabled_or_manual")
        now = time.time()
        try:
            current = self._ahash(frame_rgb)
        except Exception:
            return HashGateDecision(True, "hash_error")
        if self._last_hash is None:
            self._last_hash = current
            self._last_run_ts = self._last_change_ts = now
            return HashGateDecision(True, "first_frame")
        dist = self._distance(current, self._last_hash)
        elapsed_hold = int((now - self._last_run_ts) * 1000)
        elapsed_gap = int((now - self._last_run_ts) * 1000)
        if dist >= self.threshold:
            if self.min_run_gap_ms > 0 and elapsed_gap < self.min_run_gap_ms:
                return HashGateDecision(False, "changed_but_gap", dist, max(1, self.min_run_gap_ms - elapsed_gap))
            self._last_hash = current
            self._last_run_ts = self._last_change_ts = now
            return HashGateDecision(True, "changed", dist)
        if elapsed_hold >= self.max_hold_ms:
            self._last_run_ts = now
            return HashGateDecision(True, "hold_probe", dist)
        return HashGateDecision(False, "same_frame_hold", dist, min(40, max(5, self.max_hold_ms - elapsed_hold)))
