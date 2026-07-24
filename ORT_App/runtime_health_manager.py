"""ORT Translation v8.4 runtime health manager.

Low-overhead guard that keeps ORT from fighting heavy games.  It is safe when
psutil/nvidia-smi are missing: it falls back to UNKNOWN/NORMAL and never blocks
translation for long.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "status" / "runtime_health.json"


@dataclass
class RuntimeHealth:
    timestamp: float
    status: str
    cpu_percent: float
    ram_percent: float
    vram_free_gb: float
    vram_total_gb: float
    queue_size: int
    queue_max: int
    avg_ocr_ms: float
    avg_translate_ms: float
    recommended_sleep_ms: int
    recommended_ocr_resolution: int
    force_cpu: bool
    reason: str


class RuntimeHealthManager:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.policy = os.environ.get("ORT_PERFORMANCE_POLICY", "balanced").lower()
        self.core_profile = os.environ.get("ORT_CORE_PROFILE", "balanced").lower()
        self.heavy_safe = os.environ.get("TITAN_HEAVY_GAME_SAFE", "0") == "1"
        self.lite_gpu_efficient = os.environ.get("ORT_LITE_GPU_EFFICIENT", "0") == "1"
        self.vram_low = float(os.environ.get("TITAN_VRAM_LOW_GB", "1.5"))
        self.vram_recover = float(os.environ.get("TITAN_VRAM_RECOVER_GB", "2.4"))
        self.base_ocr = int(os.environ.get("ORT_OCR_RESOLUTION_PERCENT", "65"))
        self._last_check = 0.0
        self._last_health = RuntimeHealth(time.time(), "NORMAL", 0, 0, 0, 0, 0, 1, 0, 0, 0, self.base_ocr, False, "init")
        self._translate_samples = []
        self._ocr_samples = []

    def observe_translate_ms(self, ms: float) -> None:
        try:
            self._translate_samples.append(float(ms))
            if len(self._translate_samples) > 30:
                self._translate_samples = self._translate_samples[-30:]
        except Exception:
            pass

    def observe_ocr_ms(self, ms: float) -> None:
        try:
            self._ocr_samples.append(float(ms))
            if len(self._ocr_samples) > 30:
                self._ocr_samples = self._ocr_samples[-30:]
        except Exception:
            pass

    def _avg(self, xs):
        return round(sum(xs) / len(xs), 1) if xs else 0.0

    def _cpu_ram(self) -> tuple[float, float]:
        try:
            import psutil  # type: ignore
            return float(psutil.cpu_percent(interval=None)), float(psutil.virtual_memory().percent)
        except Exception:
            return 0.0, 0.0

    def _vram(self) -> tuple[float, float]:
        try:
            out = subprocess.check_output([
                "nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"
            ], text=True, encoding="utf-8", errors="replace", timeout=0.8)
            line = out.splitlines()[0]
            free_mb, total_mb = [float(x.strip()) for x in line.split(',')[:2]]
            return round(free_mb / 1024.0, 2), round(total_mb / 1024.0, 2)
        except Exception:
            return 0.0, 0.0

    def snapshot(self, queue_size: int = 0, queue_max: int = 1, force: bool = False) -> RuntimeHealth:
        now = time.time()
        if not force and now - self._last_check < 1.5:
            return self._last_health
        self._last_check = now
        cpu, ram = self._cpu_ram()
        vfree, vtotal = self._vram()
        status = "NORMAL"
        reasons = []
        force_cpu = False
        sleep = 0
        ocr = self.base_ocr
        q_ratio = (float(queue_size) / max(1.0, float(queue_max))) if queue_max else 0.0
        if self.heavy_safe or self.core_profile in {"safe_game", "potato"}:
            sleep = max(sleep, 80 if self.lite_gpu_efficient else 120)
            ocr = min(ocr, 55 if self.lite_gpu_efficient else 58)
            reasons.append("lite gpu efficient guard" if self.lite_gpu_efficient else "safe game guard")
        if cpu >= 88 or ram >= 90:
            status = "CRITICAL"
            sleep = max(sleep, 280)
            ocr = min(ocr, 50)
            reasons.append("CPU/RAM critical")
        elif cpu >= 75 or ram >= 82:
            status = "WARNING"
            sleep = max(sleep, 120)
            ocr = min(ocr, 56)
            reasons.append("CPU/RAM warning")
        if vfree and vfree < self.vram_low:
            status = "CRITICAL" if self.heavy_safe else "WARNING"
            force_cpu = False if self.lite_gpu_efficient else True
            sleep = max(sleep, 180 if self.lite_gpu_efficient else 220)
            ocr = min(ocr, 48 if self.lite_gpu_efficient else 52)
            reasons.append(f"VRAM low {vfree}GB" + ("; Lite GPU throttled" if self.lite_gpu_efficient else ""))
        if q_ratio >= 0.80:
            status = "WARNING" if status == "NORMAL" else status
            sleep = max(sleep, 150)
            reasons.append("queue backlog")
        if self._avg(self._translate_samples) > 1200:
            status = "WARNING" if status == "NORMAL" else status
            sleep = max(sleep, 180)
            reasons.append("translate latency high")
        health = RuntimeHealth(
            timestamp=now,
            status=status,
            cpu_percent=round(cpu, 1),
            ram_percent=round(ram, 1),
            vram_free_gb=vfree,
            vram_total_gb=vtotal,
            queue_size=int(queue_size),
            queue_max=int(queue_max or 1),
            avg_ocr_ms=self._avg(self._ocr_samples),
            avg_translate_ms=self._avg(self._translate_samples),
            recommended_sleep_ms=int(sleep),
            recommended_ocr_resolution=int(ocr),
            force_cpu=bool(force_cpu),
            reason="; ".join(reasons) or "normal",
        )
        self._last_health = health
        self.write_status(health)
        return health

    def write_status(self, health: Optional[RuntimeHealth] = None) -> None:
        health = health or self._last_health
        try:
            data = asdict(health)
            data["version"] = "v8.4"
            _write_status("runtime_health", data, self.base_dir)
        except Exception:
            pass

    def recommended_extra_sleep_ms(self, queue_size: int = 0, queue_max: int = 1) -> int:
        return int(self.snapshot(queue_size, queue_max).recommended_sleep_ms)

    def should_force_cpu(self) -> bool:
        return bool(self.snapshot().force_cpu)
