"""ORT v8.8.8-r2 Mode Policy Manager.

Separates Auto, Interval, Freeze, and Mode Buffer behavior without adding heavy
global delay. v8.8.8-r2 makes policy visible in runtime telemetry.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass
class ModePolicy:
    requested_mode: str
    policy_name: str
    preview_enabled: bool
    final_required: bool
    stable_wait_ms: int
    emergency_timeout_ms: int
    allow_mode_buffer: bool
    notes: str


class ModePolicyManager:
    def __init__(self, mode_buffer_enabled: bool = False):
        self.mode_buffer_enabled = bool(mode_buffer_enabled)

    @classmethod
    def from_env(cls) -> "ModePolicyManager":
        enabled = os.environ.get("ORT_MODE_BUFFER_ENABLED", os.environ.get("ORT_MODE_BUFFER", "0")) in {"1", "true", "True", "yes", "on"}
        return cls(mode_buffer_enabled=enabled)

    def policy_for(self, mode: str, capture_mode: str = "STABLE") -> ModePolicy:
        m = (mode or "auto").strip().lower()
        c = (capture_mode or "STABLE").strip().upper()
        if c == "FREEZE" or m == "freeze":
            return ModePolicy(m, "freeze_final_snapshot", False, True, 650, 1200, False, "snapshot/final-only; do not behave like auto_story loop")
        if m == "interval":
            return ModePolicy(m, "interval_semi_stable", True, True, 420, 650, True, "semi-stable; fast-skip safety required")
        if self.mode_buffer_enabled:
            return ModePolicy(m, "auto_with_mode_buffer", True, True, 500, 850, True, "preview fast; final buffered")
        return ModePolicy(m, "auto_fast_preview_final", True, True, 220, 750, False, "visual-novel style preview with mandatory final")
