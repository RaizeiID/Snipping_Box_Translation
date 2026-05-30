"""ORT Translation v8.8.1 model strategy layer.

This module makes model choices operational instead of cosmetic.  The WebUI still
shows the familiar Normal/Lite/IDN/Lite IDN/Fast model names, but every selected
model now expands into a runtime contract:

- OCR interval and resolution behavior
- CPU/GPU preference and heavy-game guard
- queue size and CPU thread limit
- translation engine policy: offline / hybrid online / fast
- post-processing / QA intensity
- active core profile for the Runtime Bridge
- cache scope per game/model family

The strategy is deliberately data-driven and dependency-free so it can be used by
launcher_backend, TITANMAIN, and runtime_bridge without starting OCR or Qt.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from status_manager import write_status as _write_status

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "status" / "strategy.json"


@dataclass(frozen=True)
class ModelStrategy:
    model_key: str
    model_title: str
    group: str
    family: str
    level: int
    strategy_name: str
    engine_policy: str
    cache_scope: str
    core_profile: str
    postprocess_level: str
    qa_level: str
    online_policy: str
    fast_path: bool
    idn_enabled: bool
    lite_enabled: bool
    naturalize_depth: int
    recommended_engine: str
    recommended_mode: str
    interval_floor_ms: int
    ocr_resolution_percent: int
    queue_max: int
    cpu_threads: int
    vram_low_gb: float
    vram_recover_gb: float
    scan_sleep_gpu_ms: int
    scan_sleep_cpu_ms: int
    reason: str

    def idn_quality_mode(self) -> str:
        if self.fast_path:
            return "fast_light" if self.model_key == "fast_idn" or self.idn_enabled else "off"
        if not self.idn_enabled:
            return "off"
        if self.lite_enabled:
            return {1: "lite_light", 2: "lite_balanced", 3: "balanced", 4: "natural", 5: "quality"}.get(int(self.level), "lite_balanced")
        return {1: "lite_light", 2: "balanced", 3: "natural", 4: "natural", 5: "quality"}.get(int(self.level), "balanced")

    def to_env(self) -> Dict[str, str]:
        return {
            "ORT_RUNTIME_STRATEGY": "1",
            "ORT_MODEL_KEY": self.model_key,
            "ORT_MODEL_GROUP": self.group,
            "ORT_MODEL_FAMILY": self.family,
            "ORT_MODEL_LEVEL": str(self.level),
            "ORT_MODEL_STRATEGY": self.strategy_name,
            "ORT_ENGINE_POLICY": self.engine_policy,
            "ORT_CACHE_SCOPE": self.cache_scope,
            "ORT_CORE_PROFILE": self.core_profile,
            "ORT_POSTPROCESS_LEVEL": self.postprocess_level,
            "ORT_QA_LEVEL": self.qa_level,
            "ORT_ONLINE_POLICY": self.online_policy,
            "ORT_FAST_PATH": "1" if self.fast_path else "0",
            "TITAN_FAST_MODE": "1" if self.fast_path else "0",
            "TITAN_IDN_MODE": "1" if self.idn_enabled else "0",
            "TITAN_LITE_MODE": "1" if self.lite_enabled else "0",
            "TITAN_NATURALIZE_MAX": "1" if self.naturalize_depth >= 2 else "0",
            "ORT_NATURALIZE_DEPTH": str(self.naturalize_depth),
            "ORT_BOOT_ENGINE": self.recommended_engine,
            "ORT_BOOT_MODE": self.recommended_mode,
            "ORT_BOOT_INTERVAL_MS": str(self.interval_floor_ms),
            "ORT_OCR_RESOLUTION_PERCENT": str(self.ocr_resolution_percent),
            "ORT_BOOT_OCR_RESOLUTION": str(self.ocr_resolution_percent),
            "TITAN_QUEUE_MAX": str(self.queue_max),
            "TITAN_CPU_THREADS": str(self.cpu_threads),
            "TITAN_VRAM_LOW_GB": str(self.vram_low_gb),
            "TITAN_VRAM_RECOVER_GB": str(self.vram_recover_gb),
            "TITAN_SCAN_SLEEP_GPU_MS": str(self.scan_sleep_gpu_ms),
            "TITAN_SCAN_SLEEP_CPU_MS": str(self.scan_sleep_cpu_ms),
            "TITAN_HEAVY_GAME_SAFE": "1" if self.core_profile in {"safe_game", "potato"} else "0",
            "ORT_LITE_GPU_EFFICIENT": "1" if self.lite_enabled else "0",
            "ORT_IDN_QUALITY_LAYER": "1" if self.idn_enabled else "0",
            "ORT_IDN_QUALITY_MODE": self.idn_quality_mode(),
            "ORT_IDN_STYLE_PROFILE": self.idn_quality_mode(),
            "ORT_IDN_TERMINOLOGY_LOCK": "1" if self.idn_enabled else "0",
            "ORT_IDN_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
            "ORT_SCOPED_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
            "ORT_ENTITY_SPAN_PIPELINE": "1",
            "ORT_SPEAKER_TRANSITION_GUARD": "1",
            "ORT_SEMANTIC_FAITHFULNESS_GATE": "1",
            "ORT_DIALOGUE_COMPLETENESS_GATE": "1",
            "ORT_IDN_ACCURACY_QUALITY_LOCK": "1" if self.idn_enabled else "0",
            "ORT_CT2_PATH_REBIND": "1",
            "ORT_IDN_QUALITY_ENGINE_PASS": "1" if self.idn_enabled else "0",
            "ORT_CONTROLLED_ONLINE_ASSIST": "1",
            "ORT_ALLOW_ONLINE_ASSIST": "1" if (self.level == 4 and self.online_policy in {"hybrid", "timeout_assist", "online_assist"} and not self.fast_path) else "0",
            "ORT_LIVE_OFFLINE_GUARD": "1",
            "TITAN_ONLINE_ASSIST": "1" if (self.level == 4 and self.online_policy in {"hybrid", "timeout_assist", "online_assist"} and not self.fast_path) else "0",
            "TITAN_ONLINE_TIMEOUT": "1.0" if (self.level == 4 and self.lite_enabled) else ("1.2" if self.core_profile in {"safe_game", "fast", "lite_efficient", "lite_idn_efficient"} else "2.0"),
            "ORT_LITE_WIDE_DIALOG_FILTER": "1" if self.lite_enabled else "0",
            "ORT_OCR_NOISE_REJECT": "1" if self.lite_enabled else "0",
            "ORT_LITE_ADAPTIVE_OCR": "1" if self.lite_enabled else "0",
            "ORT_NUMERIC_DUAL_PASS": "1" if (self.lite_enabled or self.idn_enabled or self.level >= 5) else "0",
            "ORT_NATURALIZED_CACHE": "1" if self.idn_enabled else "0",
            "ORT_NAME_ALIAS_NORMALIZER": "1",
            "ORT_ADAPTIVE_READABILITY_GUARD": "1" if (self.lite_enabled or self.fast_path) else "0",
            "ORT_OCR_STORY_MIN_PERCENT": "50",
            "ORT_NAME_ROI_MIN_PERCENT": "50",
            "ORT_GFL2_EXACT_FALLBACK_ONLY": "1",
            "ORT_RUNTIME_OCR_REPORTING": "1",
            "ORT_FAITHFULNESS_V2": "1",
            "ORT_QUR_CORRUPTION_QUARANTINE": "1",
            "ORT_STRICT_CT2_STORY": "1",
            "ORT_IDN_OVER_CT2": "1" if (self.idn_enabled or self.group == "normal") else "0",
            "ORT_FINAL_ONLY_SAFE_COMMIT": "1" if (self.idn_enabled or self.group == "normal") else "0",
            "ORT_DISABLE_ARGOS_PROGRESSIVE_WHEN_CT2": "1",
            "ORT_HARD_STRICT_CT2_STORY": "1",
            "ORT_FORCE_TRUSTED_PREVIEW": "1",
            "ORT_RESPONSIVE_STORY_MODE": "1",
            "ORT_LATEST_FRAME_WINS": "1",
            "ORT_TURN_SAFE_OVERLAY": "1",
            "ORT_SCENE_EXIT_GUARD": "1",
            "ORT_SEMANTIC_FIDELITY_GUARD": "1",
        }

    def summary_lines(self) -> List[str]:
        return [
            f"Model = {self.model_title} ({self.model_key})",
            f"Strategy = {self.strategy_name}",
            f"Group/Family/Level = {self.group}/{self.family}/{self.level}",
            f"Engine policy = {self.engine_policy}",
            f"Runtime = {self.recommended_engine} / {self.recommended_mode} / {self.interval_floor_ms} ms",
            f"OCR = {self.ocr_resolution_percent}% | Queue = {self.queue_max} | CPU threads = {self.cpu_threads}",
            f"Core profile = {self.core_profile}",
            f"Postprocess = {self.postprocess_level} | QA = {self.qa_level} | Online = {self.online_policy}",
            f"Cache scope = {self.cache_scope}",
            f"Reason = {self.reason}",
        ]


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except Exception:
        return default


def _float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return default


def _model_level(model_key: str, family: str) -> int:
    key = (model_key or "").lower()
    fam = (family or "").lower()
    for token in ("v5", "v4", "v3", "v2", "v1"):
        if token in key or token == fam:
            return int(token[-1])
    if key == "fast_idn":
        return 2
    if key.startswith("fast"):
        return 1 if key.endswith("v1") else 2
    return 2


def _base_by_level(level: int) -> Dict[str, Any]:
    # V1 light, V2 balanced, V3 accuracy, V4 online/offline hybrid, V5 deep IDN.
    table = {
        1: dict(interval=160, ocr=64, queue=36, cpu=4, post="minimal", qa="light", engine="offline", core="light", reason="V1 ringan untuk dialog sederhana."),
        2: dict(interval=220, ocr=68, queue=60, cpu=6, post="standard", qa="normal", engine="offline", core="balanced", reason="V2 balance sebagai default aman."),
        3: dict(interval=320, ocr=74, queue=56, cpu=6, post="quality", qa="strict", engine="offline", core="quality", reason="V3 mengejar akurasi; lebih lambat."),
        4: dict(interval=260, ocr=70, queue=48, cpu=6, post="standard", qa="normal", engine="hybrid", core="hybrid", reason="V4 offline-first + online assist timeout pendek."),
        5: dict(interval=340, ocr=75, queue=46, cpu=6, post="deep_idn", qa="strict", engine="offline", core="natural", reason="V5 naturalisasi presisi dan konsistensi istilah."),
    }
    return dict(table.get(level, table[2]))


def _game_defaults(game: str) -> Dict[str, Any]:
    key = (game or "CUSTOM").upper()
    if key == "WUWA":
        return dict(heavy=True, engine="hybrid", mode="auto", interval_min=450, ocr_max=55, queue_max=20, cpu_max=4,
                    vram_low=1.1, vram_recover=2.2, gpu_sleep=115, cpu_sleep=165, core="safe_game",
                    reason="Wuthering Waves terdeteksi sebagai heavy game; v8.4 memakai Lite GPU Efficient bila model Lite/Lite IDN dipilih.")
    if key == "GFL2_EXILIUM":
        return dict(heavy=False, engine="hybrid", mode="auto", interval_min=90, ocr_max=70, queue_max=72, cpu_max=6,
                    vram_low=1.0, vram_recover=1.8, gpu_sleep=22, cpu_sleep=55, core="balanced",
                    reason="GFL2 visual-novel/story; v8.2 memakai hash gate + scheduler agar dialog tidak diproses berulang.")
    return dict(heavy=False, engine="hybrid", mode="auto", interval_min=240, ocr_max=70, queue_max=55, cpu_max=6,
                vram_low=1.5, vram_recover=2.4, gpu_sleep=45, cpu_sleep=95, core="balanced",
                reason="Profil custom dimulai dari balanced.")


def build_strategy(
    model_key: str = "v2",
    model_title: str = "ORTCore V2",
    group: str = "normal",
    family: str = "V2",
    game: str = "GFL2_EXILIUM",
    policy: str = "auto",
    requested_engine: str = "hybrid",
    requested_mode: str = "auto",
    requested_interval_ms: Optional[int] = None,
    requested_ocr_resolution: Optional[int] = None,
    normal_override: bool = False,
) -> ModelStrategy:
    model_key = (model_key or "v2").lower()
    group = (group or "normal").lower()
    family = (family or "V2").upper()
    game = (game or "GFL2_EXILIUM").upper()
    policy = (policy or "auto").lower()
    level = _model_level(model_key, family)
    base = _base_by_level(level)
    gd = _game_defaults(game)

    lite = "lite" in group or model_key.startswith("lite")
    idn = "idn" in group or "idn" in model_key
    fast = group == "fast" or model_key.startswith("fast")
    natural_depth = 0
    if idn:
        natural_depth = 1
    if level >= 5 or "v5" in model_key:
        natural_depth = max(natural_depth, 2)
    if idn and level >= 3:
        natural_depth = max(natural_depth, 2)
    if fast:
        natural_depth = 1 if idn else 0

    interval = int(base["interval"])
    ocr = int(base["ocr"])
    queue = int(base["queue"])
    cpu = int(base["cpu"])
    engine_policy = str(base["engine"])
    core_profile = str(base["core"])
    post = str(base["post"])
    qa = str(base["qa"])
    online = "hybrid" if level == 4 else "off"
    mode = requested_mode or str(gd["mode"])
    engine = requested_engine or str(gd["engine"])
    reason = [str(base["reason"]), str(gd["reason"])]

    if fast:
        # v8.5.1: Fast OCR/latency retune preserved from v8.5.
        # Fast variants still share CT2 backend; only OCR, latency, queue, and polish differ.
        if model_key == "fast_v1":
            interval = 45
            ocr = min(ocr, 40)
            queue = min(queue, 14)
            post = "minimal"
            qa = "light"
            reason.append("Fast V1 v8.5 ultra speed: OCR 40%, latency minimum, polish minimal.")
        elif model_key == "fast_idn":
            interval = 75
            ocr = min(ocr, 50)
            queue = min(queue, 20)
            post = "fast_idn_polish_light"
            qa = "light"
            natural_depth = max(natural_depth, 1)
            reason.append("Fast IDN v8.5: OCR 50%, basis Fast V2 + IDN naturalizer ringan.")
        else:
            interval = 60
            ocr = min(ocr, 45)
            queue = min(queue, 18)
            post = "fast_balanced_light"
            qa = "light"
            reason.append("Fast V2 v8.5 low-latency balanced: OCR 45%, cleanup tetap aktif.")
        cpu = min(cpu, 3)
        online = "off"
        engine_policy = "fast"
        core_profile = "fast"
        mode = requested_mode or "auto"

    if lite:
        # v8.5 final: Lite/Lite IDN identity is explicit, not slow-safe.  Keep GPU Efficient
        # allowed and reduce latency/cores instead of pushing every Lite profile toward
        # long interval waits.  Wide GFL2 dialog boxes are accepted; noise is handled by
        # OCR filtering instead of forcing users to crop too tightly.
        if idn:
            table = {
                1: (260, 40, 12, 2, "lite_light"),
                2: (330, 45, 14, 3, "lite_balanced"),
                3: (390, 50, 16, 3, "lite_balanced"),
                4: (430, 55, 18, 3, "lite_balanced"),
                5: (480, 60, 18, 3, "lite_quality"),
            }
            interval, ocr, queue, cpu, idn_mode = table.get(level, table[2])
            post = "lite_idn_light" if level <= 2 else "lite_idn_quality_safe"
            core_profile = "lite_idn_efficient"
            reason.append(f"Lite IDN v8.8.1 profile: OCR {ocr}%, interval {interval}ms, IDN Quality {idn_mode}; terminology lock + v8.6 naturalized cache aktif.")
        else:
            table = {
                1: (240, 40, 12, 2),
                2: (310, 45, 14, 3),
                3: (370, 50, 16, 3),
                4: (410, 55, 18, 3),
                5: (460, 60, 18, 3),
            }
            interval, ocr, queue, cpu = table.get(level, table[2])
            post = "lite"
            core_profile = "lite_efficient"
            reason.append(f"Lite v8.8.1 profile: OCR {ocr}%, interval {interval}ms; V2 recommended, V3 balanced quality, V5 quality only.")
        qa = "light"
        if level == 4:
            online = "timeout_assist"
        engine_policy = "offline" if level != 4 else "hybrid"

    if idn and not fast:
        post = "deep_idn" if level >= 5 else ("quality_idn" if level >= 3 else "standard_idn")
        reason.append("IDN v8.6 mengaktifkan shared IDN Quality Layer dan terminology consistency.")

    if gd["heavy"] and not normal_override:
        engine = "hybrid" if lite else "cpu"
        mode = requested_mode or "auto"
        interval = max(interval, int(gd["interval_min"]))
        ocr = min(ocr, int(gd["ocr_max"]))
        queue = min(queue, int(gd["queue_max"]))
        cpu = min(cpu, int(gd["cpu_max"]))
        core_profile = "safe_game" if not fast else "fast"
        if level == 4 and not lite:
            online = "off"
        reason.append("Heavy-game guard v8.4 menurunkan beban; Lite/Lite IDN boleh memakai GPU Efficient dengan VRAM budget.")
    elif policy in {"safe_game", "potato"}:
        engine = "cpu"
        mode = requested_mode or "auto"
        interval = max(interval, 430)
        ocr = min(ocr, 58)
        queue = min(queue, 22)
        cpu = min(cpu, 4)
        core_profile = "safe_game" if policy == "safe_game" else "potato"
        reason.append("User memilih kebijakan Safe/Potato.")
    elif policy in {"normal", "normal_forced", "force_normal"} or normal_override:
        # Respect user's normal override, but do not inflate Lite/Lite IDN back into a
        # normal model.  v8.5 keeps Lite efficient even when the UI is in Normal/Manual.
        interval = max(interval, 180 if gd["heavy"] else 90)
        if lite:
            # Preserve explicit Lite V1-V5 OCR identity even in Normal/Manual mode.
            # Level-aware caps below still prevent V1/V2 from drifting into quality-heavy behavior.
            queue = min(queue, 20)
            cpu = min(cpu, 3)
            reason.append("Normal override aktif, tetapi Lite v8.5 tetap memakai profil OCR level-aware.")
        else:
            ocr = min(max(ocr, 60), 78)
            queue = min(max(queue, 34), 70)
            core_profile = "normal_override" if gd["heavy"] else core_profile
            reason.append("Normal override aktif; sistem tetap memberi batas aman.")
    elif policy == "balanced":
        interval = max(interval, int(gd["interval_min"]))
        ocr = min(ocr, int(gd["ocr_max"]))
        queue = min(queue, int(gd["queue_max"]))
        cpu = min(max(cpu, 4), int(gd["cpu_max"]))
        if not gd["heavy"]:
            core_profile = "balanced"
        reason.append("Balanced menjaga responsif tanpa over-scan.")

    if requested_interval_ms is not None:
        interval = max(interval, _int(requested_interval_ms, interval, 45, 2500)) if gd["heavy"] and not normal_override else _int(requested_interval_ms, interval, 45, 2500)
    if requested_ocr_resolution is not None:
        req_ocr = _int(requested_ocr_resolution, ocr, 35, 120)
        ocr = min(req_ocr, int(gd["ocr_max"])) if gd["heavy"] and not normal_override else req_ocr
    if lite:
        # v8.8.1: preserve low-cost preset identity, but never silently reject a user's
        # higher OCR override. V1/V2 are now diagnostic/ultra-efficient presets for GFL2
        # story unless Adaptive Readability Rescue raises a degraded frame temporarily.
        level_ocr_preset = {1: 40, 2: 45, 3: 50, 4: 55, 5: 60}.get(level, 45)
        if requested_ocr_resolution is None:
            ocr = min(int(ocr), int(level_ocr_preset))
        else:
            requested_clean = _int(requested_ocr_resolution, int(ocr), 35, 120)
            ocr = requested_clean if not (gd["heavy"] and not normal_override) else min(requested_clean, int(gd["ocr_max"]))
            if ocr > level_ocr_preset:
                reason.append(f"v8.8.1 manual OCR override respected: preset {level_ocr_preset}% -> applied {ocr}% (Modification).")
        if game == "GFL2_EXILIUM" and int(ocr) < 50:
            reason.append("v8.8.1 GFL2 story warning: OCR below 50% is diagnostic/ultra-efficient; Adaptive Readability Rescue may retry degraded frames at 50%+.")
        queue_cap = {1: 12, 2: 14, 3: 16, 4: 18, 5: 18}.get(level, 14)
        queue = min(int(queue), queue_cap)
        cpu = min(int(cpu), 2 if level == 1 else 3)

    if fast:
        engine = "hybrid" if engine not in {"cpu", "force_cpu"} and not gd["heavy"] else "cpu"
        if not gd["heavy"]:
            # Keep Fast user/default latency low instead of clamping back to old 90/140ms behavior.
            fast_floor = 45 if model_key == "fast_v1" else (60 if model_key == "fast_v2" else 75)
            interval = max(fast_floor, min(interval, 120))
        else:
            interval = max(interval, 300)
    if gd["heavy"] and engine in {"gpu", "force_gpu"} and not normal_override and not lite:
        engine = "cpu"
        reason.append("GPU penuh diblokir untuk model non-Lite pada heavy game; gunakan Lite GPU Efficient untuk GPU hemat.")
    if game == "GFL2_EXILIUM" and not lite and not fast and normal_override:
        # v8.5.1: GFL2 wide dialog + 75% OCR caused 0.8-1.1GB OCR spikes.
        # Keep Normal models usable, but cap runtime pressure unless the user edits manually later.
        ocr = min(int(ocr), 68)
        queue = min(int(queue), 32)
        cpu = min(int(cpu), 5)
        reason.append("v8.5.1 GFL2 normal-model VRAM guard: OCR/queue capped to reduce GPU spikes before CPU fallback.")

    scan_gpu = int(gd["gpu_sleep"])
    scan_cpu = int(gd["cpu_sleep"])
    if fast and not gd["heavy"]:
        scan_gpu = min(scan_gpu, 22)
        scan_cpu = min(scan_cpu, 55)
    if core_profile in {"safe_game", "potato"}:
        scan_gpu = max(scan_gpu, 90)
        scan_cpu = max(scan_cpu, 145)
    if core_profile in {"lite_efficient", "lite_idn_efficient"}:
        scan_gpu = max(scan_gpu, 38 if not gd["heavy"] else 70)
        scan_cpu = max(scan_cpu, 85 if not gd["heavy"] else 130)

    strategy_name = f"{group}:{family}:L{level}:{core_profile}"
    cache_scope = f"{game.lower()}:{group}:{family.lower()}"
    return ModelStrategy(
        model_key=model_key,
        model_title=model_title,
        group=group,
        family=family,
        level=level,
        strategy_name=strategy_name,
        engine_policy=engine_policy,
        cache_scope=cache_scope,
        core_profile=core_profile,
        postprocess_level=post,
        qa_level=qa,
        online_policy=online,
        fast_path=fast,
        idn_enabled=idn,
        lite_enabled=lite,
        naturalize_depth=natural_depth,
        recommended_engine=str(engine).lower(),
        recommended_mode=str(mode).lower(),
        interval_floor_ms=int(interval),
        ocr_resolution_percent=int(ocr),
        queue_max=int(queue),
        cpu_threads=int(cpu),
        vram_low_gb=float(gd["vram_low"]),
        vram_recover_gb=float(gd["vram_recover"]),
        scan_sleep_gpu_ms=int(scan_gpu),
        scan_sleep_cpu_ms=int(scan_cpu),
        reason=" ".join(reason),
    )


def strategy_from_env() -> ModelStrategy:
    return build_strategy(
        model_key=os.environ.get("ORT_MODEL_KEY", "v2"),
        model_title=os.environ.get("TITAN_MODEL_LABEL", os.environ.get("ORT_MODEL_KEY", "ORTCore V2")),
        group=os.environ.get("ORT_MODEL_GROUP", "normal"),
        family=os.environ.get("ORT_MODEL_FAMILY", os.environ.get("TITAN_MODEL_PRESET", "V2")),
        game=os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "GFL2_EXILIUM")),
        policy=os.environ.get("ORT_PERFORMANCE_POLICY", "auto"),
        requested_engine=os.environ.get("ORT_BOOT_ENGINE", "hybrid"),
        requested_mode=os.environ.get("ORT_BOOT_MODE", "auto"),
        requested_interval_ms=os.environ.get("ORT_BOOT_INTERVAL_MS"),
        requested_ocr_resolution=os.environ.get("ORT_OCR_RESOLUTION_PERCENT", os.environ.get("ORT_BOOT_OCR_RESOLUTION")),
        normal_override=os.environ.get("ORT_NORMAL_OVERRIDE", "0") == "1",
    )


def write_strategy_status(strategy: ModelStrategy, base_dir: Optional[Path] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    data = asdict(strategy)
    data["summary"] = "\n".join(strategy.summary_lines())
    if extra:
        data["extra"] = extra
    try:
        _write_status("strategy", data, base_dir or ROOT)
    except Exception:
        pass


def html_summary(strategy: ModelStrategy) -> str:
    color = "#22c55e"
    if strategy.core_profile in {"safe_game", "potato"}:
        color = "#f59e0b"
    if strategy.core_profile == "normal_override":
        color = "#ef4444"
    rows = "".join(f"<tr><td>{line.split('=',1)[0].strip()}</td><td>{line.split('=',1)[1].strip() if '=' in line else line}</td></tr>" for line in strategy.summary_lines())
    return f"""
    <div class='card'>
      <h3 style='margin:0 0 8px 0'>Model Strategy</h3>
      <div style='font-weight:800;color:{color};margin-bottom:8px'>{strategy.strategy_name}</div>
      <table style='width:100%;border-collapse:collapse'>{rows}</table>
    </div>
    """
