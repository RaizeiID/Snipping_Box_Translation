"""ORT v8.8.9 Dialogue Timeout Safety / Emergency Commit.

Prevents a new dialogue from being held forever by translation_hold,
coverage gates, or repeated repaint_last_good.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from collections import deque
from typing import Dict


@dataclass
class TimeoutDecision:
    emergency_due: bool
    reason: str
    age_ms: int
    repaint_limited: bool = False


class DialogueTimeoutSafety:
    def __init__(self, enabled: bool = True, timeout_ms: int = 700, repaint_window_ms: int = 1500, max_repaints: int = 3):
        self.enabled = enabled
        self.timeout_ms = int(timeout_ms)
        self.repaint_window_ms = int(repaint_window_ms)
        self.max_repaints = int(max_repaints)
        self.turn_started: Dict[str, float] = {}
        self.visible_turns: Dict[str, bool] = {}
        self.repaint_times = deque(maxlen=64)

    @classmethod
    def from_env(cls) -> "DialogueTimeoutSafety":
        return cls(
            enabled=os.environ.get("ORT_DIALOGUE_TIMEOUT_SAFETY", "1") != "0",
            timeout_ms=int(os.environ.get("ORT_DIALOGUE_TIMEOUT_MS", "700")),
            repaint_window_ms=int(os.environ.get("ORT_STALE_LAST_GOOD_WINDOW_MS", "1500")),
            max_repaints=int(os.environ.get("ORT_STALE_LAST_GOOD_MAX_REPAINTS", "3")),
        )

    def update(self, *, turn_id: str, source: str, visible: bool = False, held: bool = False) -> TimeoutDecision:
        if not self.enabled:
            return TimeoutDecision(False, "disabled", 0)
        tid = turn_id or "default"
        now = time.time()
        self.turn_started.setdefault(tid, now)
        if visible:
            self.visible_turns[tid] = True
        age_ms = int((now - self.turn_started[tid]) * 1000)
        emergency = bool(source and held and not self.visible_turns.get(tid, False) and age_ms >= self.timeout_ms)
        return TimeoutDecision(emergency, "dialogue_timeout_emergency_commit" if emergency else "within_timeout", age_ms)

    def mark_visible(self, turn_id: str) -> None:
        tid = turn_id or "default"
        self.visible_turns[tid] = True

    def reset_turn(self, turn_id: str = "") -> None:
        if turn_id:
            self.turn_started.pop(turn_id, None)
            self.visible_turns.pop(turn_id, None)

    def allow_repaint_last_good(self) -> TimeoutDecision:
        if not self.enabled:
            return TimeoutDecision(True, "disabled", 0)
        now = time.time()
        self.repaint_times.append(now)
        cutoff = now - (self.repaint_window_ms / 1000.0)
        recent = [t for t in self.repaint_times if t >= cutoff]
        if len(recent) > self.max_repaints:
            return TimeoutDecision(False, "stale_last_good_repaint_limit", int((now - recent[0]) * 1000), repaint_limited=True)
        return TimeoutDecision(True, "repaint_allowed", 0)
