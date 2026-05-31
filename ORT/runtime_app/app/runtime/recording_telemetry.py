"""Lightweight recording telemetry for ORT v8.8.5."""
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
        render_total = max(1, data.get("overlay_committed", 0) + data.get("overlay_suppressed", 0))
        data["flicker_suppression_rate"] = round(data.get("overlay_suppressed", 0) / render_total, 4)
        final_total = max(1, data.get("overlay_committed", 0))
        data["final_complete_ratio"] = round(data.get("overlay_committed_final_complete", 0) / final_total, 4)
        data["new_turn_ratio"] = round(data.get("overlay_committed_new_turn", 0) / final_total, 4)
        data["source_suppressed_ratio"] = round(data.get("source_longer_but_suppressed", 0) / max(1, data.get("overlay_suppressed", 0)), 4)
        data["bad_cache_shielded"] = data.get("bad_cache_shielded", 0)
        data["ocr_churn_rescued"] = data.get("ocr_churn_rescued", 0)
        data["turn_finalizer_forced"] = data.get("turn_finalizer_forced", 0)
        return data

    def maybe_log(self, emit, *, min_interval_sec: int = 60) -> None:
        now = time.time()
        if now - self.last_log_ts < min_interval_sec:
            return
        self.last_log_ts = now
        data = self.snapshot()
        emit("[REC v8.8.5] " + " | ".join(f"{k}={v}" for k, v in sorted(data.items())))
