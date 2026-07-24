"""Lightweight recording telemetry for the active ORT build."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict, Any

from build_info import APP_VERSION_TAG

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
        data["mandatory_final_committed"] = data.get("mandatory_final_committed", 0)
        data["temporal_consensus_ready"] = data.get("temporal_consensus_ready", 0)
        data["mode_buffer_collecting"] = data.get("mode_buffer_collecting", 0)
        data["low_ocr_visual_rescue"] = data.get("low_ocr_visual_rescue", 0)
        data["contextual_ocr_repaired"] = data.get("contextual_ocr_repaired", 0)
        data["english_source_overlay_blocked"] = data.get("english_source_overlay_blocked", 0)
        data["id_preview_visible"] = data.get("id_preview_visible", 0)
        data["legacy_repaint_blocked"] = data.get("legacy_repaint_blocked", 0)
        data["stale_overlay_limited"] = data.get("stale_overlay_limited", 0)
        data["ui_text_filtered_before_translate"] = data.get("ui_text_filtered_before_translate", 0)
        data["emergency_commit_used"] = data.get("emergency_commit_used", 0)
        data["prediction_green_applied"] = data.get("prediction_green_applied", 0)
        data["prediction_yellow_applied"] = data.get("prediction_yellow_applied", 0)
        data["prediction_red_blocked"] = data.get("prediction_red_blocked", 0)
        data["prediction_final_cache_blocked"] = data.get("prediction_final_cache_blocked", 0)
        data["ambiguous_entity_blocked"] = data.get("ambiguous_entity_blocked", 0)
        data["speaker_label_resolved"] = data.get("speaker_label_resolved", 0)
        data["interval_fast_skip_forced"] = data.get("interval_fast_skip_forced", 0)
        data["mode_policy_auto"] = data.get("mode_policy_auto", 0)
        data["mode_policy_interval"] = data.get("mode_policy_interval", 0)
        data["mode_policy_freeze"] = data.get("mode_policy_freeze", 0)
        data["entity_green_labeled"] = data.get("entity_green_labeled", 0)
        data["entity_yellow_labeled"] = data.get("entity_yellow_labeled", 0)
        data["interval_fast_skip_forced"] = data.get("interval_fast_skip_forced", 0)
        data["mode_policy_auto"] = data.get("mode_policy_auto", 0)
        data["mode_policy_interval"] = data.get("mode_policy_interval", 0)
        data["mode_policy_freeze"] = data.get("mode_policy_freeze", 0)
        data["change_gate_skipped"] = data.get("change_gate_skipped", 0)
        data["change_gate_run"] = data.get("change_gate_run", 0)
        gate_total = max(1, data["change_gate_skipped"] + data["change_gate_run"])
        data["static_ocr_skip_rate"] = round(data["change_gate_skipped"] / gate_total, 4)
        data["turn_started"] = data.get("turn_started", 0)
        data["generation_advanced"] = data.get("generation_advanced", 0)
        data["progressive_frames_coalesced"] = data.get("progressive_frames_coalesced", 0)
        data["stale_results_dropped"] = data.get("stale_results_dropped", 0)
        data["atomic_overlay_swaps"] = data.get("atomic_overlay_swaps", 0)
        data["explicit_clears"] = data.get("explicit_clears", 0)
        data["unmatched_clear"] = data.get("unmatched_clear", 0)
        data["multi_final_prevented"] = data.get("multi_final_prevented", 0)
        return data

    def maybe_log(self, emit, *, min_interval_sec: int = 60) -> None:
        now = time.time()
        if now - self.last_log_ts < min_interval_sec:
            return
        self.last_log_ts = now
        data = self.snapshot()
        emit(f"[REC {APP_VERSION_TAG}] " + " | ".join(f"{k}={v}" for k, v in sorted(data.items())))
