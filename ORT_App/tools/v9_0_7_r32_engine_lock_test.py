"""ORT v9.0.7 R32 -- CPU/GPU are locks, Adaptif is the only one that may switch.

The field session was started with the engine set to GPU and still ran on the
CPU: `lite_gpu=cpu_fallback_low_vram | reason=VRAM too low for safe GPU Lite
(1.03GB free)`. The guard treated the choice as a hint. The consequence was not
subtle -- CPU threads dropped to 1 and the worst backend frame took 6.1 s.

R32 makes the three entries mean what they say:

    CPU      locked  -- never moved to the GPU
    GPU      locked  -- never moved to the CPU, at any VRAM level; the run is
                        narrowed into a minimum-VRAM shape instead
    Adaptif  prefers the GPU, and is the ONLY entry allowed to switch

Lite's safe floor also drops 1.10 -> 0.75 GB, because being the lightest core is
its entire job. The R3 measurement on this card bounds the cost: detector canvas
960 peaks at 207 MB with accuracy unchanged (88.9% -> 89.2%), so under a
gigabyte is workable as long as the canvas and queue are clamped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.runtime.lite_gpu_guard as G  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


_real_query = G._query_vram


def at_vram(gb):
    G._query_vram = lambda: (gb, 6.00)


def lite(engine):
    return G.decide_lite_gpu(model_key="lite_v1", group="lite", game="GFL2_EXILIUM",
                             requested_engine=engine, requested_ocr=47)


def normal(engine):
    return G.decide_vram_safety(model_key="v2", group="normal", game="GFL2_EXILIUM",
                                requested_engine=engine)


try:
    # --- a locked GPU is never relocated, however little VRAM is left --------
    for gb in (1.03, 0.60, 0.30, 0.05):
        at_vram(gb)
        for name, d in (("lite", lite("gpu")), ("normal", normal("gpu"))):
            assert_true(d.device == "cuda", f"{name} at {gb}GB left the GPU: {d.device} ({d.profile})")
            assert_true(not d.fallback_cpu, f"{name} at {gb}GB reported a CPU fallback")
    results["gpu_lock_never_switches"] = "PASS (4 VRAM levels x 2 paths)"

    # A locked CPU stays on the CPU even when VRAM is plentiful.
    at_vram(5.50)
    assert_true(lite("cpu").device == "cpu", "locked CPU was moved to the GPU")
    assert_true(normal("cpu").device == "cpu", "locked CPU was moved to the GPU")
    results["cpu_lock_never_switches"] = "PASS"

    # --- Adaptif is the one that may switch ---------------------------------
    at_vram(0.30)
    assert_true(lite("hybrid").fallback_cpu, "Adaptif refused to switch when VRAM ran out")
    assert_true(normal("hybrid").fallback_cpu, "Adaptif refused to switch when VRAM ran out")
    at_vram(5.50)
    assert_true(lite("hybrid").device == "cuda", "Adaptif did not prefer the GPU when VRAM was free")
    results["adaptive_switches_only_when_needed"] = "PASS"

    # --- Lite is genuinely the lightest core --------------------------------
    safe, low, healthy = G.tier_vram_floors("lite_v1", "lite")
    n_safe = G.tier_vram_floors("v2", "normal")[0]
    assert_true(safe <= 0.80, f"Lite safe floor is still high: {safe}GB")
    assert_true(safe < n_safe, "Lite's floor is not below Normal's")
    at_vram(1.03)
    d = lite("hybrid")
    assert_true(d.device == "cuda", f"Lite fell off the GPU at 1.03GB even on Adaptif ({d.profile})")
    results["lite_runs_on_gpu_at_1gb"] = f"PASS (floor {safe}GB)"

    # The minimum-VRAM shape must actually clamp the levers, not just be named.
    at_vram(0.40)
    env: dict[str, str] = {}
    G.apply_lite_gpu_env(env, model_key="lite_v1", group="lite", game="GFL2_EXILIUM",
                         requested_engine="gpu", requested_ocr=47,
                         base_dir=Path(__file__).resolve().parents[2])
    assert_true(env.get("ORT_LITE_MIN_VRAM_SHAPE") == "1", "minimum-VRAM shape was not flagged")
    canvas = int(env.get("ORT_OCR_DETECTOR_CANVAS", "0") or 0)
    assert_true(canvas == 960, f"detector canvas not clamped to the measured floor: {canvas}")
    assert_true(env.get("TITAN_CT2_DEVICE") == "cuda", "CT2 was moved off the locked GPU")
    results["min_vram_shape_clamps_levers"] = f"PASS (canvas {canvas})"

    # --- the picker must offer exactly these three, on both pages -----------
    src = (Path(__file__).resolve().parent.parent / "webui.py").read_text(encoding="utf-8", errors="replace")
    assert_true(src.count("_ocr_engine_device_choices(") >= 3,
                "main page and Lab no longer share one device picker")
    for token in ("CPU · terkunci", "GPU · terkunci", "Adaptif · utamakan GPU"):
        assert_true(token in src, f"picker label missing: {token}")
    assert_true("Hybrid · GPU dengan penyelamat CPU" not in src,
                "old ambiguous Hybrid label is still shown")
    results["picker_labels_and_shared_by_both_pages"] = "PASS"

    results["passed"] = True
    print(json.dumps(results, ensure_ascii=False, indent=2))
finally:
    G._query_vram = _real_query
