"""ORT Translation v8.5.2 runtime health applier.

runtime_health_manager.py measures pressure.  This module turns that signal into
closed-loop directives that TITANMAIN and translation_engine.py can obey:
- dynamic OCR resolution downshift
- throttled CPU OCR fallback
- online assist pause
- temporary fast-mode hint when queue/latency is high
- gradual restore hints, disabled by default for GPU to avoid stutter
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from status_manager import write_status as _write_status

ROOT = Path(__file__).resolve().parent

@dataclass
class RuntimeDirectives:
    timestamp: float
    status: str
    ocr_resolution_percent: int
    force_cpu: bool
    disable_online: bool
    temporary_fast_mode: bool
    extra_sleep_ms: int
    reason: str
    should_reload_cpu: bool = False
    should_restore_engine: bool = False
    restore_ocr_resolution_percent: int = 0


class RuntimeHealthApplier:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None, logger=print):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.log = logger
        self.base_ocr = max(35, min(120, int(float(os.environ.get("ORT_OCR_RESOLUTION_PERCENT", os.environ.get("ORT_BOOT_OCR_RESOLUTION", "65")) or 65))))
        self.min_ocr = max(35, min(self.base_ocr, int(os.environ.get("ORT_MIN_OCR_RESOLUTION", "42"))))
        self.allow_force_cpu = os.environ.get("ORT_ALLOW_FORCE_CPU", "0") == "1"
        self.allow_restore = os.environ.get("ORT_ALLOW_RESTORE_GPU", "0") == "1"
        self.cooldown_sec = float(os.environ.get("ORT_ACTION_COOLDOWN_SEC", "8.0"))
        self._last_action_ts = 0.0
        self._cpu_forced = False
        self._previous_engine = "AUTO_GPU"
        self._normal_count = 0
        self._force_cpu_count = 0
        self._last = RuntimeDirectives(time.time(), "INIT", self.base_ocr, False, False, False, 0, "init", restore_ocr_resolution_percent=self.base_ocr)

    def _clamp_ocr(self, value: int) -> int:
        return max(self.min_ocr, min(120, int(value)))

    def decide(self, health: Any, current_engine_mode: str = "AUTO_GPU", is_using_gpu: bool = False) -> RuntimeDirectives:
        now = time.time()
        status = str(getattr(health, "status", "NORMAL") or "NORMAL")
        recommended = self._clamp_ocr(int(getattr(health, "recommended_ocr_resolution", self.base_ocr) or self.base_ocr))
        sleep = int(getattr(health, "recommended_sleep_ms", 0) or 0)
        force_cpu_rec = bool(getattr(health, "force_cpu", False))
        reason = str(getattr(health, "reason", "normal") or "normal")
        queue_size = int(getattr(health, "queue_size", 0) or 0)
        queue_max = max(1, int(getattr(health, "queue_max", 1) or 1))
        avg_translate_ms = float(getattr(health, "avg_translate_ms", 0) or 0)
        q_ratio = queue_size / queue_max

        force_cpu = False
        reload_cpu = False
        restore_engine = False
        temporary_fast = q_ratio >= 0.70 or avg_translate_ms >= float(os.environ.get("ORT_TEMP_FAST_LATENCY_MS", "1300"))
        disable_online = status in {"WARNING", "CRITICAL"} or "latency" in reason.lower() or force_cpu_rec or temporary_fast

        if status == "CRITICAL":
            recommended = min(recommended, 48)
            sleep = max(sleep, 260)
            self._normal_count = 0
        elif status == "WARNING":
            recommended = min(recommended, 55)
            sleep = max(sleep, 110)
            self._normal_count = 0
        else:
            self._normal_count += 1
            # Restore OCR resolution gradually after several normal samples.
            if self._normal_count >= 4:
                recommended = min(self.base_ocr, max(recommended, self.base_ocr))

        if temporary_fast:
            sleep = max(sleep, 90)
            recommended = min(recommended, 55)
            reason += "; temporary fast-mode hint"

        if force_cpu_rec:
            self._force_cpu_count += 1
            # v8.5.2: avoid sudden CPU OCR fallback on transient VRAM spikes.
            # Downscale OCR/slow loop first; CPU fallback only if explicitly enabled
            # and sustained for several health samples.
            recommended = min(recommended, 52)
            sleep = max(sleep, 180)
            if self.allow_force_cpu and self._force_cpu_count >= int(os.environ.get("ORT_FORCE_CPU_SUSTAINED_SAMPLES", "4")):
                force_cpu = True
                if is_using_gpu and (now - self._last_action_ts >= self.cooldown_sec):
                    reload_cpu = True
                    self._last_action_ts = now
                    if not self._cpu_forced:
                        self._previous_engine = current_engine_mode or "AUTO_GPU"
                    self._cpu_forced = True
                    reason += "; sustained CPU OCR fallback"
            else:
                reason += "; staged VRAM relief without CPU fallback"
        else:
            self._force_cpu_count = 0

        if self._cpu_forced and self.allow_restore and status == "NORMAL" and not force_cpu_rec and self._normal_count >= 6:
            if now - self._last_action_ts >= self.cooldown_sec * 2:
                restore_engine = True
                self._last_action_ts = now
                self._cpu_forced = False
                reason += "; restoring previous engine"

        directives = RuntimeDirectives(
            timestamp=now,
            status=status,
            ocr_resolution_percent=recommended,
            force_cpu=force_cpu,
            disable_online=disable_online,
            temporary_fast_mode=temporary_fast,
            extra_sleep_ms=sleep,
            reason=reason,
            should_reload_cpu=reload_cpu,
            should_restore_engine=restore_engine,
            restore_ocr_resolution_percent=self.base_ocr,
        )
        self._last = directives
        self.write_status(directives, health=health)
        return directives

    @property
    def previous_engine(self) -> str:
        return self._previous_engine or "AUTO_GPU"

    def write_status(self, directives: Optional[RuntimeDirectives] = None, health: Any = None) -> None:
        directives = directives or self._last
        payload: Dict[str, Any] = asdict(directives)
        payload["version"] = "v8.5.2"
        payload["base_ocr_resolution_percent"] = self.base_ocr
        payload["min_ocr_resolution_percent"] = self.min_ocr
        payload["cpu_forced_state"] = self._cpu_forced
        payload["normal_count"] = self._normal_count
        payload["force_cpu_count"] = self._force_cpu_count
        payload["allow_force_cpu"] = self.allow_force_cpu
        if health is not None:
            payload["health_status"] = str(getattr(health, "status", "-"))
            payload["health_reason"] = str(getattr(health, "reason", "-"))
            payload["cpu_percent"] = getattr(health, "cpu_percent", None)
            payload["ram_percent"] = getattr(health, "ram_percent", None)
            payload["vram_free_gb"] = getattr(health, "vram_free_gb", None)
            payload["queue_size"] = getattr(health, "queue_size", None)
            payload["queue_max"] = getattr(health, "queue_max", None)
            payload["avg_translate_ms"] = getattr(health, "avg_translate_ms", None)
        try:
            _write_status("runtime_actions", payload, self.base_dir)
        except Exception:
            pass
