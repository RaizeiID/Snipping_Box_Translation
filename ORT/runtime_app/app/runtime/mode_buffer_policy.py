"""ORT v8.8.7 Mode Buffer policy.

Experimental recording buffer. Default OFF. When enabled from WebUI checkbox,
it gives final-lane commit a small controlled buffer while keeping preview fast.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time


@dataclass(frozen=True)
class ModeBufferDecision:
    enabled: bool
    buffer_ms: int
    final_delay_due: bool
    reason: str


class ModeBufferPolicy:
    def __init__(self, *, enabled: bool = False, buffer_ms: int = 700) -> None:
        self.enabled = bool(enabled)
        self.buffer_ms = max(0, int(buffer_ms))
        self._turn_id = ""
        self._turn_start_ts = 0.0

    @classmethod
    def from_env(cls) -> "ModeBufferPolicy":
        enabled = os.environ.get("ORT_MODE_BUFFER", "0") == "1"
        return cls(enabled=enabled, buffer_ms=int(os.environ.get("ORT_MODE_BUFFER_MS", "700")))

    def reset(self) -> None:
        self._turn_id = ""
        self._turn_start_ts = 0.0

    def update(self, *, turn_id: str, final_like: bool = False, mode: str = "") -> ModeBufferDecision:
        if not self.enabled:
            return ModeBufferDecision(False, 0, True, "mode_buffer_off")
        if str(mode or "").upper() == "FREEZE":
            return ModeBufferDecision(True, 0, True, "freeze_no_buffer")
        tid = str(turn_id or "").strip() or "default"
        now = time.time()
        if tid != self._turn_id:
            self._turn_id = tid
            self._turn_start_ts = now
        elapsed_ms = int((now - (self._turn_start_ts or now)) * 1000)
        due = bool(final_like or elapsed_ms >= self.buffer_ms)
        return ModeBufferDecision(True, self.buffer_ms, due, "buffer_due" if due else "buffer_collecting")
