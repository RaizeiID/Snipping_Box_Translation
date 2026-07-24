"""ORT v8.8.8-r2 Interval Fast-Skip Safety.

Prevents quick manual/interval clicks from losing a dialogue turn before a
visible translation is committed.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Dict


@dataclass
class FastSkipDecision:
    force_commit: bool
    reason: str
    age_ms: int


class IntervalFastSkipSafety:
    def __init__(self, enabled: bool = True, timeout_ms: int = 650):
        self.enabled = enabled
        self.timeout_ms = int(timeout_ms)
        self.first_seen: Dict[str, float] = {}
        self.visible: Dict[str, bool] = {}

    def update(self, turn_id: str, source: str, mode: str = "auto", visible: bool = False) -> FastSkipDecision:
        if not self.enabled:
            return FastSkipDecision(False, "disabled", 0)
        tid = turn_id or "default"
        now = time.time()
        self.first_seen.setdefault(tid, now)
        if visible:
            self.visible[tid] = True
        age = int((now - self.first_seen[tid]) * 1000)
        if mode.lower() == "interval" and source and not self.visible.get(tid, False) and age >= self.timeout_ms:
            return FastSkipDecision(True, "interval_fast_skip_force_commit", age)
        return FastSkipDecision(False, "within_interval_window", age)

    def mark_visible(self, turn_id: str) -> None:
        self.visible[turn_id or "default"] = True
