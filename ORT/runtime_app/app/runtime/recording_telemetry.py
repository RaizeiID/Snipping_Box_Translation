"""Lightweight recording telemetry for ORT v8.8.3."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict, Any

@dataclass
class RecordingTelemetry:
    start_ts: float = field(default_factory=time.time)
    last_log_ts: float = field(default_factory=time.time)
    counters: Dict[str, int] = field(default_factory=dict)

    def inc(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + int(amount)

    def snapshot(self) -> Dict[str, Any]:
        data = dict(self.counters)
        data["duration_sec"] = int(time.time() - self.start_ts)
        commits = max(1, data.get("overlay_committed", 0) + data.get("overlay_suppressed", 0))
        data["flicker_suppression_rate"] = round(data.get("overlay_suppressed", 0) / commits, 4)
        return data

    def maybe_log(self, emit, *, min_interval_sec: int = 60) -> None:
        now = time.time()
        if now - self.last_log_ts < min_interval_sec:
            return
        self.last_log_ts = now
        data = self.snapshot()
        emit("[REC v8.8.3] " + " | ".join(f"{k}={v}" for k, v in sorted(data.items())))
