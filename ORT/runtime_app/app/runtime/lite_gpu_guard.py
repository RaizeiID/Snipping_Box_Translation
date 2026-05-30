from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Mapping


@dataclass
class LiteGpuDecision:
    enabled: bool
    profile: str
    device: str
    compute_type: str
    ocr_cap: int
    extra_sleep_ms: int
    queue_cap: int
    cpu_threads_cap: int
    fallback_cpu: bool
    reason: str
    vram_free_gb: float = 0.0
    vram_total_gb: float = 0.0


def _query_vram() -> tuple[float, float]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=0.9,
        )
        first = out.splitlines()[0]
        free_mb, total_mb = [float(x.strip()) for x in first.split(",")[:2]]
        return round(free_mb / 1024.0, 2), round(total_mb / 1024.0, 2)
    except Exception:
        return 0.0, 0.0


def is_lite_like(model_key: str = "", group: str = "") -> bool:
    s = f"{model_key} {group}".lower()
    return "lite" in s


def is_lite_idn(model_key: str = "", group: str = "") -> bool:
    s = f"{model_key} {group}".lower()
    return "lite_idn" in s or ("lite" in s and "idn" in s)


def lite_level(model_key: str = "") -> int:
    s = str(model_key or "").lower()
    for n in (5, 4, 3, 2, 1):
        if f"v{n}" in s:
            return n
    return 2

def level_ocr_cap(model_key: str = "", *, heavy: bool = False, unknown_or_tight: bool = False) -> int:
    # v8.5 final Lite identity ladder: V1=40, V2=45, V3=50, V4=55, V5=60.
    # Guard may lower caps when VRAM is unknown/tight or game is very heavy.
    cap = {1: 40, 2: 45, 3: 50, 4: 55, 5: 60}.get(lite_level(model_key), 45)
    if unknown_or_tight:
        return min(cap, 46)
    if heavy:
        return min(cap, 55)
    return cap

def level_queue_cap(model_key: str = "", *, heavy: bool = False) -> int:
    cap = {1: 9, 2: 11, 3: 13, 4: 14, 5: 14}.get(lite_level(model_key), 12)
    return min(cap, 14 if heavy else cap)


def decide_lite_gpu(
    model_key: str = "",
    group: str = "",
    game: str = "",
    requested_engine: str = "hybrid",
    requested_ocr: int | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> LiteGpuDecision:
    """v8.7.6 Lite GPU Efficient policy with visible manual OCR override support.

    Lite/Lite IDN is allowed to use GPU on heavy games, but the GPU use is capped.
    CPU fallback only happens when VRAM is truly below the safe floor.
    """
    lite = is_lite_like(model_key, group)
    lite_idn = is_lite_idn(model_key, group)
    heavy = (game or "").upper() in {"WUWA", "WUTHERING_WAVES"}
    engine = (requested_engine or "hybrid").lower()
    free, total = _query_vram()
    ocr_req = int(requested_ocr or 55)
    preset_cap = level_ocr_cap(model_key, heavy=heavy)
    manual_above_preset = ocr_req > preset_cap
    def quality_cap(default_cap: int) -> int:
        # v8.7.6: do not silently undo an explicit OCR increase while the
        # VRAM budget is healthy enough for normal Lite operation.
        return ocr_req if manual_above_preset else min(ocr_req, default_cap)

    if not lite:
        return LiteGpuDecision(False, "off", "cpu", "int8", ocr_req, 0, 0, 0, False, "not a Lite/Lite IDN model", free, total)

    # Defaults are intentionally conservative for 6GB-class laptop GPUs.
    safe_floor = float(os.environ.get("ORT_LITE_GPU_SAFE_FLOOR_GB", "1.10"))
    low_floor = float(os.environ.get("ORT_LITE_GPU_LOW_GB", "1.60"))
    healthy_floor = float(os.environ.get("ORT_LITE_GPU_HEALTHY_GB", "2.20"))

    if engine in {"cpu", "force_cpu"}:
        return LiteGpuDecision(True, "cpu_safe", "cpu", "int8", quality_cap(level_ocr_cap(model_key, heavy=heavy)), 105 if heavy else 45, level_queue_cap(model_key, heavy=heavy), 2, True, "user selected CPU/Force CPU", free, total)

    if free and free < safe_floor:
        return LiteGpuDecision(True, "cpu_fallback_low_vram", "cpu", "int8", min(ocr_req, 45), 180, 10, 2, True, f"VRAM too low for safe GPU Lite ({free}GB free)", free, total)

    if not free:
        # No nvidia-smi data. Still allow hybrid, but use conservative caps.
        return LiteGpuDecision(True, "gpu_unknown_safe", "cuda", "int8", min(ocr_req, level_ocr_cap(model_key, heavy=heavy, unknown_or_tight=True)), 110 if heavy else 45, min(level_queue_cap(model_key, heavy=heavy), 12 if heavy else 16), 2 if heavy else 3, False, "VRAM unknown; using conservative GPU Efficient caps", free, total)

    if free < low_floor:
        return LiteGpuDecision(True, "gpu_low_vram", "cuda", "int8", min(ocr_req, level_ocr_cap(model_key, heavy=heavy, unknown_or_tight=True)), 135, min(level_queue_cap(model_key, heavy=heavy), 10), 2, False, f"VRAM tight; GPU Efficient low profile ({free}GB free)", free, total)

    if free < healthy_floor:
        return LiteGpuDecision(True, "gpu_efficient", "cuda", "int8", quality_cap(level_ocr_cap(model_key, heavy=heavy)), 85 if heavy else 35, level_queue_cap(model_key, heavy=heavy), 3, False, f"GPU Efficient balanced under VRAM budget ({free}GB free)", free, total)

    compute = "int8" if lite_idn else ("int8_float16" if total >= 5.5 else "int8")
    # v8.6: Lite IDN prioritizes low VRAM/FPS stability over maximum decoding speed.
    # Keep OCR and queue capped even when the VRAM budget looks healthy.
    cap = level_ocr_cap(model_key, heavy=heavy)
    extra_sleep = 52 if heavy else (18 if lite_idn else 22)
    queue_cap = level_queue_cap(model_key, heavy=heavy)
    cpu_cap = 3
    return LiteGpuDecision(True, "gpu_efficient_plus", "cuda", compute, quality_cap(cap), extra_sleep, queue_cap, cpu_cap, False, f"GPU Efficient healthy budget ({free}GB free); v8.7.6 manual OCR override respected when requested, Adaptive Readability Rescue ready", free, total)


def apply_lite_gpu_env(env: Dict[str, str], *, model_key: str, group: str, game: str, requested_engine: str, requested_ocr: int, base_dir: str | os.PathLike[str]) -> LiteGpuDecision:
    decision = decide_lite_gpu(model_key, group, game, requested_engine, requested_ocr, base_dir)
    if not decision.enabled:
        return decision
    env["ORT_LITE_GPU_EFFICIENT"] = "1"
    env["ORT_LITE_GPU_PROFILE"] = decision.profile
    env["ORT_LITE_GPU_REASON"] = decision.reason
    env["ORT_LITE_GPU_VRAM_FREE_GB"] = str(decision.vram_free_gb)
    env["ORT_LITE_GPU_VRAM_TOTAL_GB"] = str(decision.vram_total_gb)
    env["ORT_LITE_REQUESTED_OCR"] = str(requested_ocr)
    env["ORT_LITE_APPLIED_OCR"] = str(decision.ocr_cap)
    env["ORT_LITE_PRESET_OCR"] = str(level_ocr_cap(model_key, heavy=(game or "").upper() in {"WUWA", "WUTHERING_WAVES"}))
    env["ORT_LITE_OCR_OVERRIDE_APPLIED"] = "1" if int(requested_ocr) > int(env["ORT_LITE_PRESET_OCR"]) and int(decision.ocr_cap) >= int(requested_ocr) else "0"
    env["ORT_LITE_APPLIED_QUEUE"] = str(decision.queue_cap)
    env["ORT_LITE_APPLIED_CPU_THREADS"] = str(decision.cpu_threads_cap)
    env["ORT_LITE_CT2_ALLOWED"] = "1"
    env["ORT_LITE_CT2_MODEL_DIR"] = str(Path(base_dir) / "models" / "ct2_opus_mt_en_id")
    env["TITAN_CT2_DEVICE"] = decision.device
    env["TITAN_CT2_COMPUTE_TYPE"] = decision.compute_type
    env["ORT_LITE_IDN_LIGHT_POST"] = "1" if is_lite_idn(model_key, group) else "0"
    env["ORT_LITE_WIDE_DIALOG_FILTER"] = "1"
    env["ORT_OCR_NOISE_REJECT"] = "1"
    env["ORT_LITE_ADAPTIVE_OCR"] = "1"
    env["ORT_NUMERIC_DUAL_PASS"] = "1"
    env["ORT_NUMERIC_ROI_ONLY"] = "1"
    env["ORT_NUMERIC_DUAL_PASS_MIN_MS"] = env.get("ORT_NUMERIC_DUAL_PASS_MIN_MS", "1100")
    env["ORT_IDN_QUALITY_LAYER"] = "1" if is_lite_idn(model_key, group) else env.get("ORT_IDN_QUALITY_LAYER", "0")
    env["ORT_IDN_QUALITY_ENGINE_PASS"] = "1" if is_lite_idn(model_key, group) else env.get("ORT_IDN_QUALITY_ENGINE_PASS", "0")
    if is_lite_idn(model_key, group):
        env["ORT_IDN_QUALITY_MODE"] = env.get("ORT_IDN_QUALITY_MODE") or "lite_balanced"
    else:
        env["ORT_IDN_QUALITY_MODE"] = env.get("ORT_IDN_QUALITY_MODE", "off")
    env["ORT_BOOT_OCR_RESOLUTION"] = str(min(int(env.get("ORT_BOOT_OCR_RESOLUTION", requested_ocr)), decision.ocr_cap))
    env["ORT_OCR_RESOLUTION_PERCENT"] = str(min(int(env.get("ORT_OCR_RESOLUTION_PERCENT", requested_ocr)), decision.ocr_cap))
    env["TITAN_QUEUE_MAX"] = str(min(int(env.get("TITAN_QUEUE_MAX", decision.queue_cap) or decision.queue_cap), decision.queue_cap))
    env["TITAN_CPU_THREADS"] = str(min(int(env.get("TITAN_CPU_THREADS", decision.cpu_threads_cap) or decision.cpu_threads_cap), decision.cpu_threads_cap))
    env["ORT_LITE_EXTRA_SLEEP_MS"] = str(decision.extra_sleep_ms)
    env["ORT_LITE_CPU_FALLBACK"] = "1" if decision.fallback_cpu else "0"
    if decision.fallback_cpu:
        env["ORT_BOOT_ENGINE"] = "cpu"
    return decision


def write_lite_gpu_status(base_dir: str | os.PathLike[str], decision: LiteGpuDecision | Mapping[str, Any]) -> None:
    try:
        from status_manager import write_status
        payload = asdict(decision) if isinstance(decision, LiteGpuDecision) else dict(decision)
        payload["version"] = "v8.6"
        payload["timestamp"] = time.time()
        try:
            payload["requested_ocr"] = int(os.environ.get("ORT_LITE_REQUESTED_OCR", "0") or 0)
            payload["applied_ocr"] = int(os.environ.get("ORT_LITE_APPLIED_OCR", payload.get("ocr_cap", 0)) or 0)
            payload["applied_queue"] = int(os.environ.get("ORT_LITE_APPLIED_QUEUE", payload.get("queue_cap", 0)) or 0)
            payload["applied_cpu_threads"] = int(os.environ.get("ORT_LITE_APPLIED_CPU_THREADS", payload.get("cpu_threads_cap", 0)) or 0)
        except Exception:
            pass
        write_status("lite_gpu_guard", payload, Path(base_dir))
    except Exception:
        pass


def lite_gpu_status_text(base_dir: str | os.PathLike[str] | None = None) -> str:
    base = Path(base_dir or Path(__file__).resolve().parents[2])
    p = base / "status" / "lite_gpu_guard.json"
    if not p.exists():
        return "Lite GPU Guard belum berjalan. Pilih model Lite/Lite IDN lalu Start untuk melihat status."
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return f"Gagal membaca status Lite GPU Guard: {exc}"
    lines = [
        "Lite GPU Efficient Guard v8.6",
        "================================",
        f"profile = {data.get('profile', '-')}",
        f"device = {data.get('device', '-')}",
        f"compute_type = {data.get('compute_type', '-')}",
        f"fallback_cpu = {data.get('fallback_cpu', '-')}",
        f"vram_free_gb = {data.get('vram_free_gb', '-')}",
        f"vram_total_gb = {data.get('vram_total_gb', '-')}",
        f"requested_ocr = {data.get('requested_ocr', '-')}",
        f"applied_ocr = {data.get('applied_ocr', data.get('ocr_cap', '-'))}",
        f"ocr_cap = {data.get('ocr_cap', '-')}",
        f"applied_queue = {data.get('applied_queue', data.get('queue_cap', '-'))}",
        f"extra_sleep_ms = {data.get('extra_sleep_ms', '-')}",
        f"reason = {data.get('reason', '-')}",
        "",
        "Catatan: Lite GPU memakai GPU secara hemat untuk game berat. CPU fallback hanya jika VRAM berada di bawah batas aman.",
    ]
    return "\n".join(lines)
