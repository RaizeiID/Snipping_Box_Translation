"""ORT v9.0.7 unified resource ladder: mode x level x device resource.

The old resource policy was three loose tokens (efficient/normal/optimal) whose
meaning stopped at a VRAM guard and a context-word count. This module turns the
axis into one continuous, *real* ladder that every pipeline (Audio ASR, OCR,
CT2 translation) reads its knobs from.

Design
------
Three modes, five levels each, arranged on ONE light->heavy continuum W=1..15:

    Efisien   maks..terendah  -> W 1..5    (virtue: latency & lightness)
    Stabil    maks..terendah  -> W 6..10   (virtue: never stutter)
    Intensive terendah..maks  -> W 11..15  (virtue: accuracy; heavier is better)

The level slider means "more of this mode's virtue":
  * Efisien  maks  = W1  : fastest & lightest the system can go (accuracy paid)
  * Stabil   maks  = W6  : maximum headroom -- old GPUs / tight VRAM stay smooth
  * Intensive maks = W15 : maximum accuracy -- accepts weight, wants VRAM

Adjacent boundaries intentionally touch (Efisien terendah W5 vs Stabil maks W6
differ by one step), which is what makes the ladder feel continuous instead of
three disconnected presets. The three "menengah" points sit far apart
(W3 / W8 / W13), so medium-efficient, medium-stable, and medium-intensive are
genuinely different runtimes, not one preset with three labels.

Every knob below is interpolated from anchors at W=1 and W=15 and then given
mode-specific character. All of them map to levers the pipelines already obey:
LocalRealtimePolicy timings, ORT_AUDIO_CONTEXT_WORDS, VRAM preflight guard,
CT2 beam, thread budgets, OCR interval/resolution.

Device resource is an independent axis about the MACHINE, not the pipeline:
    saver    (Hemat)            : shrink threads/RAM ceilings, protect the game
    adaptive (Normal/Adaptif)   : no adjustment
    quality  (Kualitas Optimal) : spend the headroom a big machine has
"""
from __future__ import annotations

import os
from dataclasses import dataclass


MODES = ("efficient", "stable", "intensive")
DEVICE_MODES = ("saver", "adaptive", "quality")
LEVEL_MIN, LEVEL_MAX = 1, 5

LEVEL_LABELS = {1: "Terendah", 2: "Rendah", 3: "Menengah", 4: "Tinggi", 5: "Maks"}


def normalize_resource_mode(value: str) -> str:
    token = str(value or "stable").strip().lower()
    aliases = {
        # Legacy tokens keep working everywhere.
        "normal": "stable", "stabil": "stable",
        "optimal": "intensive", "accurate": "intensive", "intensif": "intensive",
        "efisien": "efficient", "eco": "efficient",
    }
    token = aliases.get(token, token)
    return token if token in MODES else "stable"


def legacy_policy_token(mode: str) -> str:
    """The pre-v9.0.7 token, for code paths that still branch on it."""
    return {"efficient": "efficient", "stable": "normal", "intensive": "optimal"}[
        normalize_resource_mode(mode)
    ]


def normalize_resource_level(value) -> int:
    try:
        level = int(float(value))
    except (TypeError, ValueError):
        level = 3
    return max(LEVEL_MIN, min(LEVEL_MAX, level))


def normalize_device_resource(value: str) -> str:
    token = str(value or "adaptive").strip().lower()
    aliases = {
        "hemat": "saver", "less": "saver", "less_resource": "saver", "eco": "saver",
        "normal": "adaptive", "adaptif": "adaptive", "auto": "adaptive",
        "kualitas": "quality", "optimal": "quality", "max": "quality",
    }
    token = aliases.get(token, token)
    return token if token in DEVICE_MODES else "adaptive"


def continuum_index(mode: str, level: int) -> int:
    """Position on the light(1)->heavy(15) continuum."""
    mode = normalize_resource_mode(mode)
    level = normalize_resource_level(level)
    if mode == "efficient":
        return 6 - level          # maks(5)->W1 ... terendah(1)->W5
    if mode == "stable":
        return 11 - level         # maks(5)->W6 ... terendah(1)->W10
    return 10 + level             # terendah(1)->W11 ... maks(5)->W15


def _lerp(w: int, light: float, heavy: float) -> float:
    return light + (heavy - light) * (w - 1) / 14.0


@dataclass(frozen=True)
class ResourcePlan:
    mode: str
    level: int
    device_resource: str
    weight: int
    # --- audio realtime (multipliers over LocalRealtimePolicy) ---
    first_partial_scale: float
    partial_interval_scale: float
    endpoint_scale: float
    pause_scale: float
    window_scale: float
    context_words: int
    vad_default: str
    quality_guard: str            # relaxed | normal | strict
    specialist_correction: bool
    # --- shared compute ---
    thread_frac: float
    ct2_beam: int
    vram_min_free_mb: int
    preflight_max_steady_ms: int
    # --- OCR ---
    ocr_interval_scale: float
    ocr_resolution_delta: int
    # scan_sleep and queue are pure latency levers: they change how quickly a
    # frame is picked up and how much stale backlog is tolerated, and cost
    # nothing in OCR accuracy. They are what lets "Stabil" cut latency without
    # giving anything up, and what makes "Efisien Maks" feel instant.
    scan_sleep_scale: float
    queue_scale: float
    # Cap for EasyOCR's CRAFT working resolution. Bounds detector VRAM and time
    # at once; 0 means "leave the library default alone".
    detector_canvas: int
    # Hybrid OCR switching thresholds, in GB of free VRAM. `hybrid_critical_gb`
    # is when Hybrid gives up the GPU; `hybrid_recover_gb` is when it takes it
    # back. Efisien/Hemat hold the GPU down to a lower floor because their
    # footprint is genuinely smaller; Intensive needs more headroom to keep the
    # accuracy it exists for.
    hybrid_critical_gb: float
    hybrid_recover_gb: float

    def as_dict(self) -> dict:
        return {
            "resource_mode": self.mode,
            "resource_level": self.level,
            "resource_level_label": LEVEL_LABELS[self.level],
            "device_resource": self.device_resource,
            "resource_weight": self.weight,
            "first_partial_scale": round(self.first_partial_scale, 3),
            "partial_interval_scale": round(self.partial_interval_scale, 3),
            "endpoint_scale": round(self.endpoint_scale, 3),
            "pause_scale": round(self.pause_scale, 3),
            "window_scale": round(self.window_scale, 3),
            "context_words": self.context_words,
            "vad_default": self.vad_default,
            "quality_guard": self.quality_guard,
            "specialist_correction": self.specialist_correction,
            "thread_frac": round(self.thread_frac, 3),
            "ct2_beam": self.ct2_beam,
            "vram_min_free_mb": self.vram_min_free_mb,
            "preflight_max_steady_ms": self.preflight_max_steady_ms,
            "ocr_interval_scale": round(self.ocr_interval_scale, 3),
            "ocr_resolution_delta": self.ocr_resolution_delta,
            "scan_sleep_scale": round(self.scan_sleep_scale, 3),
            "queue_scale": round(self.queue_scale, 3),
            "detector_canvas": self.detector_canvas,
            "hybrid_critical_gb": round(self.hybrid_critical_gb, 2),
            "hybrid_recover_gb": round(self.hybrid_recover_gb, 2),
        }


def resolve_resource_plan(mode: str, level, device_resource: str = "adaptive") -> ResourcePlan:
    mode = normalize_resource_mode(mode)
    level = normalize_resource_level(level)
    device = normalize_device_resource(device_resource)
    w = continuum_index(mode, level)

    # Base curves along the continuum. Light end: everything short, cheap,
    # single-beam, permissive about skipping work. Heavy end: long windows,
    # wide beams, strict quality gates, GPU expected.
    first_partial = _lerp(w, 0.72, 1.30)
    partial_interval = _lerp(w, 0.90, 1.25)
    endpoint = _lerp(w, 0.68, 1.40)
    pause = _lerp(w, 0.70, 1.45)
    window = _lerp(w, 0.70, 1.40)
    # ORT_V9_0_7_R2: RECALIBRATION, driven by measurements on the target
    # machine rather than intuition.
    #   * Argos ja->en cost is superlinear in text length (60 ms at 16 chars,
    #     912 ms at 65). A 128-word context therefore buys a ~1 s bridge hop,
    #     so the heavy end is capped far lower than before.
    #   * CT2 beam 5 costs +78% time and produced output identical to beam 1 on
    #     3 of 5 real log lines (the other two were a wash). Beam is not an
    #     accuracy lever here, so it no longer climbs to 5; the budget goes to
    #     levers that actually pay.
    context = int(round(_lerp(w, 32, 96) / 8.0)) * 8
    threads = _lerp(w, 0.50, 1.00)
    beam = 1 if w <= 10 else 2
    vram = int(round(_lerp(w, 2600, 1100) / 50.0)) * 50
    preflight = int(round(_lerp(w, 800, 2000) / 50.0)) * 50
    ocr_interval = _lerp(w, 0.72, 1.10)
    # Resolution is deliberately piecewise rather than one straight line,
    # because the policy is not symmetric: ONLY Efisien is allowed to buy speed
    # with OCR accuracy. Stabil must tighten latency without giving anything
    # up, so its resolution delta starts at exactly 0 and only ever rises.
    # A single interpolation put Stabil-Maks at -2%, which silently broke that
    # rule. The launcher additionally clamps to the readability floor.
    if w <= 5:                      # Efisien W1..W5
        ocr_res_delta = int(round(_lerp(w, -10, -2) / 2.0)) * 2
    else:                           # Stabil W6..W10, Intensive W11..W15
        ocr_res_delta = int(round((12.0 * (w - 6) / 9.0) / 2.0)) * 2
    # Pure-latency levers: pushed hard at the light end, and still trimmed in
    # the middle so "Stabil" is measurably snappier without losing accuracy.
    scan_sleep = _lerp(w, 0.30, 1.10)
    queue = _lerp(w, 0.50, 1.25)
    # 960 measured as the floor that still holds accuracy (640 lost 11 points);
    # the heavy end hands control back to EasyOCR's own default.
    detector_canvas = 960 if w <= 5 else 1280 if w <= 10 else 0
    # Light end holds the GPU longest (small footprint, little to lose);
    # heavy end bails earlier because it needs room to stay accurate.
    hybrid_critical = _lerp(w, 0.28, 0.75)
    hybrid_recover = _lerp(w, 0.85, 2.10)

    # Mode character on top of the shared continuum.
    if mode == "efficient":
        # Latency is the virtue: finals must land fast even when accuracy pays.
        endpoint *= 0.90
        pause *= 0.90
        vad = "heuristic"
        guard = "relaxed" if w <= 4 else "normal"
        specialist = False
    elif mode == "stable":
        # Headroom is the virtue: decode less often, keep margins, never spike.
        partial_interval *= 1.10
        window *= 0.95
        vad = "hybrid"
        guard = "normal"
        specialist = False
        # Stability keeps the VRAM guard conservative even at its heavy end so
        # a running game can never evict the ASR mid-session.
        vram = max(vram, 1700)
    else:
        # Accuracy is the virtue: full sentences, strict gates, correction pass.
        pause *= 1.05
        window *= 1.10
        vad = "hybrid"
        guard = "strict" if w >= 12 else "normal"
        specialist = w >= 11

    # Device resource: about the machine, applied after mode character.
    if device == "saver":
        threads *= 0.70
        context = int(round(context * 0.75 / 8.0)) * 8
        # ORT_V9_0_7_R3: Hemat now LOWERS the VRAM bar instead of raising it.
        # Raising it was backwards: the whole point of this mode is to keep
        # running on the GPU with a minimal footprint, not to be pushed off it.
        # Measured on an RTX 4050 with canvas capped to 960, easyocr
        # ["ch_sim","en"]: weights 134 MB, peak allocation 207 MB. Allowing for
        # the CUDA context, ~600 MB free is a defensible bar -- demanding 2.6-3
        # GB was not based on anything the pipeline actually consumes.
        vram = min(vram, 600)
        beam = max(1, beam - 1)
        # Poll less often and hold less backlog: this is the machine axis, so
        # it trades a little responsiveness for CPU the game can use instead.
        scan_sleep *= 1.30
        queue *= 0.85
        # Saver caps the detector hard: this is what lets GPU/Hybrid stay on a
        # card with very little headroom instead of falling back to CPU.
        detector_canvas = 960 if detector_canvas == 0 else min(detector_canvas, 960)
        # Hemat is the mode that should cling to the GPU: its measured peak is
        # 207 MB, so it can keep running where heavier settings could not.
        hybrid_critical = min(hybrid_critical, 0.30)
        hybrid_recover = min(hybrid_recover, 0.90)
    elif device == "quality":
        threads = min(1.0, threads * 1.20)
        context = int(round(context * 1.25 / 8.0)) * 8
        vram = max(900, vram - 300)
        scan_sleep *= 0.85

    return ResourcePlan(
        mode=mode,
        level=level,
        device_resource=device,
        weight=w,
        first_partial_scale=first_partial,
        partial_interval_scale=partial_interval,
        endpoint_scale=endpoint,
        pause_scale=pause,
        window_scale=window,
        context_words=max(24, context),
        vad_default=vad,
        quality_guard=guard,
        specialist_correction=specialist,
        thread_frac=max(0.30, min(1.0, threads)),
        ct2_beam=beam,
        # Floor is 500 rather than 900 so Hemat's measured-footprint bar
        # (600 MB) survives; every non-saver path already sits above 900.
        vram_min_free_mb=max(500, vram),
        preflight_max_steady_ms=max(600, preflight),
        ocr_interval_scale=ocr_interval,
        ocr_resolution_delta=ocr_res_delta,
        scan_sleep_scale=max(0.20, scan_sleep),
        queue_scale=max(0.35, queue),
        detector_canvas=detector_canvas,
        hybrid_critical_gb=max(0.20, hybrid_critical),
        hybrid_recover_gb=max(0.60, hybrid_recover),
    )


def resolve_plan_from_env(environ=None) -> ResourcePlan:
    env = os.environ if environ is None else environ
    mode = env.get("ORT_AUDIO_RESOURCE_MODE") or env.get("ORT_AUDIO_RESOURCE_POLICY") or "stable"
    level = env.get("ORT_AUDIO_RESOURCE_LEVEL", "3")
    device = env.get("ORT_DEVICE_RESOURCE", "adaptive")
    return resolve_resource_plan(mode, level, device)


def scaled_threads(base_threads: int, plan: ResourcePlan) -> int:
    return max(1, int(round(max(1, int(base_threads)) * plan.thread_frac)))
