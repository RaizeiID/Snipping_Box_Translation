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


def _torch_reusable_cache_gb() -> float:
    """VRAM torch already holds and can re-use without a new device allocation."""
    try:
        import torch  # noqa: PLC0415 -- optional dependency for this guard

        if not torch.cuda.is_available():
            return 0.0
        slack = int(torch.cuda.memory_reserved()) - int(torch.cuda.memory_allocated())
        return max(0.0, slack / 1073741824.0)
    except Exception:
        return 0.0


def _query_vram() -> tuple[float, float]:
    """Free/total VRAM in GB: device-level free, plus torch's re-usable cache.

    ORT_V9_0_7_R3 replaced nvidia-smi with torch.cuda.mem_get_info() because the
    smi number sent OCR to CPU while memory was actually available. The premise
    was right but mem_get_info() alone overstates headroom badly on this WDDM
    laptop: measured concurrently on the RTX 4050, nvidia-smi reported 1700 MiB
    free while mem_get_info() reported 4.96 GB -- a 3.2 GB overstatement. Every
    floor below (1.10 / 1.60 / 2.20 GB) was therefore cleared on a machine with
    1.7 GB left, so nothing throttled and EasyOCR stalled ~26 s per frame once a
    heavier profile (V2/balanced) was loaded alongside the game.

    R3's real observation was that torch can satisfy an allocation out of its own
    cached pool without touching device-free memory. That is exactly
    `memory_reserved - memory_allocated`, so account for it explicitly instead of
    trusting a single number that hides it. With a cold torch this equals the smi
    figure; with a warm cache it credits back what R3 measured.
    """
    device_free = 0.0
    total = 0.0
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
        device_free, total = free_mb / 1024.0, total_mb / 1024.0
    except Exception:
        device_free, total = 0.0, 0.0

    if not total:
        # No smi. Fall back to CUDA's own view rather than reporting "unknown",
        # but clamp it: mem_get_info can overstate, and the callers treat a big
        # number as permission to run the heaviest profile.
        try:
            import torch  # noqa: PLC0415 -- optional dependency for this guard

            if torch.cuda.is_available():
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                return round(free_bytes / 1073741824.0, 2), round(total_bytes / 1073741824.0, 2)
        except Exception:
            pass
        return 0.0, 0.0

    usable = device_free + _torch_reusable_cache_gb()
    return round(min(usable, total), 2), round(total, 2)


def is_lite_like(model_key: str = "", group: str = "") -> bool:
    s = f"{model_key} {group}".lower()
    return "lite" in s


def is_fast_like(model_key: str = "", group: str = "") -> bool:
    s = f"{model_key} {group}".lower()
    return "fast" in s


# ORT_V9_0_7_R14: VRAM floors per core family, in GB free.
# (cpu_fallback, low_profile, healthy)
#
# Until R14 the whole ladder was gated behind is_lite_like(), so `normal`, `idn`
# and `fast` ran with no VRAM guard at all -- `decide_lite_gpu` returned
# "not a Lite/Lite IDN model" and stopped. That contradicted the job each family
# is supposed to do: `normal` exists for stability, yet it was the one family
# with nothing watching VRAM. It is what let a V2/balanced session oversubscribe
# a 6 GB laptop GPU and stall EasyOCR for 26 s per frame.
#
# The floors differ because the footprints genuinely differ. fast carries no
# naturalisation and a light QA pass, so it can keep the GPU down to a lower
# floor; normal/idn run full QA plus CT2 and need real headroom to stay accurate.
_TIER_VRAM_FLOORS = {
    "fast": (0.90, 1.30, 1.80),
    # ORT v9.0.7 R32: Lite's whole job is to be the lightest core, so its safe
    # floor is the one that should sit closest to the metal. It was 1.10 GB,
    # which is why a 1.03 GB session dropped to CPU and then ran at one thread
    # with a 6.1 s worst-case backend. The GPU cost at this tier is bounded by
    # the CRAFT detector's working resolution, and canvas 960 was measured at a
    # 207 MB peak on this card -- so 0.75 GB free is genuinely enough as long as
    # the ultra-low profile below clamps the canvas and the queue.
    "lite": (0.75, 1.30, 2.00),
    "normal": (1.40, 2.00, 2.80),
}

# Devices the user pinned. A pinned device is a decision, not a hint: the guard
# may make the run slower or narrower, but it must not silently move the work to
# the other processor. Only "hybrid" (shown as Adaptif) is allowed to switch.
_LOCKED_GPU = {"gpu", "force_gpu", "cuda"}
_LOCKED_CPU = {"cpu", "force_cpu"}


def engine_is_locked(engine: str) -> bool:
    e = str(engine or "").strip().lower()
    return e in _LOCKED_GPU or e in _LOCKED_CPU


def engine_locks_gpu(engine: str) -> bool:
    return str(engine or "").strip().lower() in _LOCKED_GPU


def tier_vram_floors(model_key: str = "", group: str = "") -> tuple[float, float, float]:
    """(safe, low, healthy) VRAM floors in GB for this core family."""
    if is_fast_like(model_key, group):
        key = "fast"
    elif is_lite_like(model_key, group):
        key = "lite"
    else:
        key = "normal"
    safe, low, healthy = _TIER_VRAM_FLOORS[key]
    return (
        float(os.environ.get("ORT_LITE_GPU_SAFE_FLOOR_GB", str(safe))),
        float(os.environ.get("ORT_LITE_GPU_LOW_GB", str(low))),
        float(os.environ.get("ORT_LITE_GPU_HEALTHY_GB", str(healthy))),
    )


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

    # Floors follow the core family (see _TIER_VRAM_FLOORS); env still overrides.
    safe_floor, low_floor, healthy_floor = tier_vram_floors(model_key, group)

    if engine in {"cpu", "force_cpu"}:
        return LiteGpuDecision(True, "cpu_safe", "cpu", "int8", quality_cap(level_ocr_cap(model_key, heavy=heavy)), 105 if heavy else 45, level_queue_cap(model_key, heavy=heavy), 2, True, "user selected CPU/Force CPU", free, total)

    if free and free < safe_floor:
        # R32: a pinned GPU is never moved to the CPU. Instead Lite drops into
        # its smallest shape -- detector canvas clamped to 960, a short queue and
        # long pacing -- which is what "as light as possible" has to mean when
        # there is under a gigabyte to work with. 960 rather than 640 because the
        # R3 measurement on this card put canvas 960 at a 207 MB peak with
        # accuracy unchanged, while 640 dropped it to 77.7%. The run gets
        # narrower and slower, never relocated.
        if engine_locks_gpu(engine):
            return LiteGpuDecision(
                True, "gpu_locked_min_vram", "cuda", "int8",
                min(ocr_req, 40), 200, 4, 2, False,
                f"GPU locked by user; Lite running in minimum-VRAM shape ({free}GB free)",
                free, total,
            )
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


def decide_vram_safety(model_key: str = "", group: str = "", game: str = "", requested_engine: str = "hybrid") -> LiteGpuDecision:
    """VRAM ladder for the families that are NOT Lite.

    ORT_V9_0_7_R14. Deliberately NOT `decide_lite_gpu`: that function's companion
    `apply_lite_gpu_env` also installs the whole Lite behaviour package --
    ORT_LITE_ADAPTIVE_OCR, ORT_LITE_WIDE_DIALOG_FILTER, ORT_NUMERIC_DUAL_PASS,
    the Lite IDN quality layer. Turning that on for `normal` would not give
    `normal` a VRAM guard, it would turn `normal` into Lite and erase the very
    job separation this is meant to protect.

    So this returns only the safety-critical part: which device to use, and how
    hard to throttle when VRAM is genuinely short. Pipeline character -- QA
    depth, postprocess level, naturalisation -- stays owned by model_strategy.
    """
    free, total = _query_vram()
    safe_floor, low_floor, healthy_floor = tier_vram_floors(model_key, group)
    heavy = (game or "").upper() in {"WUWA", "WUTHERING_WAVES"}
    engine = str(requested_engine or "hybrid").strip().lower()

    if engine in {"cpu", "force_cpu"}:
        return LiteGpuDecision(True, "cpu_safe", "cpu", "int8", 0, 0, 0, 0, True, "user selected CPU/Force CPU", free, total)
    if not free:
        return LiteGpuDecision(True, "gpu_unknown_safe", "cuda", "int8", 0, 45, 0, 0, False, "VRAM unknown; GPU kept with a conservative sleep", free, total)
    if free < safe_floor:
        # R32: same rule on the non-Lite path -- a pinned GPU stays on the GPU.
        if engine_locks_gpu(engine):
            return LiteGpuDecision(True, "gpu_locked_min_vram", "cuda", "int8", 0, 200, 0, 0, False, f"GPU locked by user; running in minimum-VRAM shape ({free}GB free)", free, total)
        return LiteGpuDecision(True, "cpu_fallback_low_vram", "cpu", "int8", 0, 150, 0, 0, True, f"VRAM too low for safe GPU ({free}GB free < {safe_floor}GB)", free, total)
    if free < low_floor:
        return LiteGpuDecision(True, "gpu_low_vram", "cuda", "int8", 0, 110 if heavy else 70, 0, 0, False, f"VRAM tight; GPU with extra pacing ({free}GB free)", free, total)
    if free < healthy_floor:
        return LiteGpuDecision(True, "gpu_efficient", "cuda", "int8", 0, 60 if heavy else 30, 0, 0, False, f"GPU under VRAM budget ({free}GB free)", free, total)
    return LiteGpuDecision(True, "gpu_healthy", "cuda", "int8_float16" if total >= 5.5 else "int8", 0, 0, 0, 0, False, f"GPU healthy VRAM budget ({free}GB free)", free, total)


def apply_vram_safety_env(env: Dict[str, str], *, model_key: str, group: str, game: str, requested_engine: str) -> LiteGpuDecision:
    """Install only the VRAM safety decision for a non-Lite core."""
    decision = decide_vram_safety(model_key, group, game, requested_engine)
    env["ORT_VRAM_GUARD_PROFILE"] = decision.profile
    env["ORT_VRAM_GUARD_REASON"] = decision.reason
    env["ORT_VRAM_GUARD_FREE_GB"] = str(decision.vram_free_gb)
    env["ORT_VRAM_GUARD_TOTAL_GB"] = str(decision.vram_total_gb)
    env["TITAN_CT2_DEVICE"] = decision.device
    env["TITAN_CT2_COMPUTE_TYPE"] = decision.compute_type
    if decision.fallback_cpu:
        env["ORT_FORCE_OCR_CPU"] = "1"
    if decision.extra_sleep_ms:
        env["ORT_VRAM_GUARD_EXTRA_SLEEP_MS"] = str(decision.extra_sleep_ms)
    return decision


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
    # R32: the actual VRAM levers for the minimum-VRAM shape. canvas_size bounds
    # the CRAFT detector's working resolution and is the single biggest driver of
    # its activation memory (247 MB at the 2560 default, 207 MB at 960); the
    # allocator hint keeps a fragmented 1 GB usable instead of failing a large
    # contiguous request.
    if decision.profile in {"gpu_locked_min_vram", "gpu_low_vram"}:
        env.setdefault("ORT_OCR_DETECTOR_CANVAS", "960")
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        env["ORT_LITE_MIN_VRAM_SHAPE"] = "1"
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
