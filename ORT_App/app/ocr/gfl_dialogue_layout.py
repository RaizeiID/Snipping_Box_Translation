from __future__ import annotations

"""Low-cost visual guard and footer mask for the compact GFL1 dialogue box."""

import os
import time
from dataclasses import dataclass
from typing import Any

try:
    import cv2
    import numpy as np
except Exception:  # import-safe for documentation/unit use
    cv2 = None
    np = None


@dataclass
class GFLFrameDecision:
    process: bool
    reason: str
    masked: bool = False
    yellow_ratio: float = 0.0
    dark_ratio: float = 0.0


class GFLDialoguePresenceGuard:
    """Conservative dialogue presence guard.

    It only blocks after repeated strong misses so unusual dialogue skins are not
    silently lost.  The primary anti-contamination mechanism remains the footer
    mask and text-level credit/artifact filter.
    """
    def __init__(self, miss_limit: int = 3) -> None:
        self.miss_limit = max(2, int(miss_limit))
        self._misses = 0
        self.last_reason = "init"
        self.last_log = 0.0

    def assess(self, frame_rgb: Any) -> GFLFrameDecision:
        if cv2 is None or np is None or frame_rgb is None:
            return GFLFrameDecision(True, "visual_guard_unavailable")
        try:
            h, w = frame_rgb.shape[:2]
            if h < 40 or w < 100:
                return GFLFrameDecision(True, "crop_too_small_for_guard")
            hsv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2HSV)
            # Yellow/orange line used on the GFL dialog frame.
            yellow = cv2.inRange(hsv, (10, 70, 80), (45, 255, 255))
            upper = yellow[: max(1, int(h * 0.48)), :]
            yellow_ratio = float((upper > 0).mean())
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            dark_ratio = float((gray < 78).mean())
            present = yellow_ratio >= 0.0010 and dark_ratio >= 0.12
            if present:
                self._misses = 0
                self.last_reason = "dialog_frame_detected"
                return GFLFrameDecision(True, self.last_reason, yellow_ratio=yellow_ratio, dark_ratio=dark_ratio)
            self._misses += 1
            if self._misses >= self.miss_limit and os.environ.get("ORT_GFL_DIALOG_PRESENCE_GUARD", "1") == "1":
                self.last_reason = "non_dialog_frame_repeated_miss"
                return GFLFrameDecision(False, self.last_reason, yellow_ratio=yellow_ratio, dark_ratio=dark_ratio)
            self.last_reason = "uncertain_allow"
            return GFLFrameDecision(True, self.last_reason, yellow_ratio=yellow_ratio, dark_ratio=dark_ratio)
        except Exception:
            return GFLFrameDecision(True, "visual_guard_exception")


def mask_footer_ui(frame_rgb: Any) -> tuple[Any, dict[str, Any]]:
    if frame_rgb is None or not hasattr(frame_rgb, "shape"):
        return frame_rgb, {"masked": False, "reason": "no_frame"}
    try:
        out = frame_rgb.copy()
        h, w = out.shape[:2]
        # Only the fixed lower-right GFsystem/button footprint is hidden.  The
        # rest of the bottom line remains available for long dialogue text.
        x1, y1 = int(w * 0.78), int(h * 0.62)
        out[y1:h, x1:w] = 0
        return out, {"masked": True, "x1": x1, "y1": y1, "w": w, "h": h}
    except Exception:
        return frame_rgb, {"masked": False, "reason": "mask_exception"}
