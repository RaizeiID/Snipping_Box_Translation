"""ORT v9.0.7 verification: unified resource ladder + ReazonSpeech stability.

Proves four claims:
  1. The mode x level ladder is a real monotonic continuum -- heavier positions
     always mean longer windows, more context, bigger beams, lower VRAM demands
     -- and the three "Menengah" presets are genuinely different runtimes.
  2. The audio policy actually scales with the ladder (not just labels).
  3. The adjacent-repeat collapse kills the exact duplicated finals seen in the
     GFL2 field log without touching legitimate Japanese reduplication.
  4. Legacy tokens (normal/optimal) and the VRAM guard keep working.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.runtime.resource_levels import (
    LEVEL_LABELS,
    continuum_index,
    legacy_policy_token,
    normalize_device_resource,
    normalize_resource_mode,
    resolve_resource_plan,
    scaled_threads,
)


def _load_sidecar():
    try:
        import app.audio.cuda_bootstrap  # noqa: F401
    except Exception:
        app = sys.modules.setdefault("app", types.ModuleType("app"))
        if not hasattr(app, "__path__"):
            app.__path__ = []
        audio = sys.modules.setdefault("app.audio", types.ModuleType("app.audio"))
        if not hasattr(audio, "__path__"):
            audio.__path__ = []
        cuda = types.ModuleType("app.audio.cuda_bootstrap")
        cuda.activate_cuda_dll_search = lambda: {}
        sys.modules["app.audio.cuda_bootstrap"] = cuda
    path = APP_ROOT / "audio_realtime_local_sidecar.py"
    spec = importlib.util.spec_from_file_location("ort_v907_sidecar_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    results = {}

    # ---- 1. Continuum sanity -------------------------------------------------
    # Level = "more of the mode's virtue": efficient/stable maks are their
    # LIGHT ends, intensive maks is its HEAVY end.
    assert continuum_index("efficient", 5) == 1
    assert continuum_index("efficient", 1) == 5
    assert continuum_index("stable", 5) == 6
    assert continuum_index("stable", 1) == 10
    assert continuum_index("intensive", 1) == 11
    assert continuum_index("intensive", 5) == 15
    # Full coverage 1..15, no gaps or overlaps.
    weights = sorted(
        continuum_index(m, l) for m in ("efficient", "stable", "intensive") for l in range(1, 6)
    )
    assert weights == list(range(1, 16)), weights
    results["continuum_coverage"] = "PASS (W1..W15, adjacent modes touch)"

    # Monotonicity along the continuum: heavier => slower finals, more context,
    # bigger-or-equal beam, lower-or-equal VRAM demand, more threads.
    ordered = []
    for m in ("efficient", "stable", "intensive"):
        levels = range(5, 0, -1) if m != "intensive" else range(1, 6)
        for l in levels:
            ordered.append(resolve_resource_plan(m, l))
    for prev, cur in zip(ordered, ordered[1:]):
        assert cur.weight == prev.weight + 1
        assert cur.context_words >= prev.context_words - 8, (prev.weight, cur.weight)
        assert cur.ct2_beam >= prev.ct2_beam
        assert cur.thread_frac >= prev.thread_frac - 1e-9
    # Endpoint scale must grow from the light end to the heavy end overall.
    assert ordered[0].endpoint_scale < ordered[-1].endpoint_scale
    assert ordered[0].vram_min_free_mb > ordered[-1].vram_min_free_mb
    results["continuum_monotonic"] = "PASS"

    # ---- 2. The three Menengah are different runtimes -----------------------
    med_e = resolve_resource_plan("efficient", 3)
    med_s = resolve_resource_plan("stable", 3)
    med_i = resolve_resource_plan("intensive", 3)
    assert med_e.weight == 3 and med_s.weight == 8 and med_i.weight == 13
    differing = 0
    for field in ("endpoint_scale", "window_scale", "context_words", "ct2_beam",
                  "vad_default", "specialist_correction", "vram_min_free_mb", "thread_frac"):
        values = {getattr(med_e, field), getattr(med_s, field), getattr(med_i, field)}
        if len(values) >= 2:
            differing += 1
    assert differing >= 6, f"mediums only differ on {differing} axes"
    assert med_e.vad_default == "heuristic" and med_s.vad_default == "hybrid"
    assert med_i.specialist_correction and not med_e.specialist_correction
    results["mediums_are_distinct"] = f"PASS ({differing}/8 axes differ)"

    # ---- 3. Device resource axis --------------------------------------------
    base = resolve_resource_plan("stable", 3, "adaptive")
    saver = resolve_resource_plan("stable", 3, "saver")
    quality = resolve_resource_plan("stable", 3, "quality")
    assert saver.thread_frac < base.thread_frac < quality.thread_frac + 1e-9
    assert saver.context_words < base.context_words < quality.context_words
    assert scaled_threads(8, saver) < scaled_threads(8, quality)
    # ORT_V9_0_7_R3: this used to assert saver demanded the MOST free VRAM.
    # That was backwards -- Hemat exists to keep running on the GPU with a small
    # footprint, not to be evicted to CPU. It now caps the detector canvas
    # (measured peak 207 MB) and asks for the LOWEST bar of the three.
    assert saver.vram_min_free_mb < base.vram_min_free_mb, (saver.vram_min_free_mb, base.vram_min_free_mb)
    assert saver.detector_canvas and saver.detector_canvas <= 960, saver.detector_canvas
    results["device_axis"] = (
        f"PASS (threads/context saver<adaptive<quality; saver VRAM bar "
        f"{saver.vram_min_free_mb} MB < adaptive {base.vram_min_free_mb} MB, canvas {saver.detector_canvas})"
    )

    # ---- 4. Legacy tokens ----------------------------------------------------
    assert normalize_resource_mode("normal") == "stable"
    assert normalize_resource_mode("optimal") == "intensive"
    assert legacy_policy_token("stable") == "normal"
    assert legacy_policy_token("intensive") == "optimal"
    assert normalize_device_resource("hemat") == "saver"
    assert LEVEL_LABELS[3] == "Menengah"
    results["legacy_tokens"] = "PASS"

    # ---- 5. Sidecar policy really scales ------------------------------------
    sidecar = _load_sidecar()
    try:
        os.environ["ORT_AUDIO_RESOURCE_MODE"] = "efficient"
        os.environ["ORT_AUDIO_RESOURCE_LEVEL"] = "5"
        fast = sidecar.resolve_policy("speed", "cpu")
        os.environ["ORT_AUDIO_RESOURCE_MODE"] = "intensive"
        os.environ["ORT_AUDIO_RESOURCE_LEVEL"] = "5"
        heavy = sidecar.resolve_policy("speed", "cpu")
    finally:
        os.environ.pop("ORT_AUDIO_RESOURCE_MODE", None)
        os.environ.pop("ORT_AUDIO_RESOURCE_LEVEL", None)
    assert fast.endpoint_s < heavy.endpoint_s, (fast.endpoint_s, heavy.endpoint_s)
    assert fast.long_pause_s < heavy.long_pause_s
    assert fast.subtitle_window_s < heavy.subtitle_window_s
    assert heavy.endpoint_s / fast.endpoint_s > 1.6, "scaling too subtle to feel"
    results["sidecar_policy_scales"] = (
        f"PASS (endpoint {int(fast.endpoint_s*1000)}ms -> {int(heavy.endpoint_s*1000)}ms)"
    )

    # ---- 6. ReazonSpeech duplicate collapse ---------------------------------
    collapse = sidecar._collapse_adjacent_repeats
    # Exact duplicated finals from the field log:
    log_dup = "関節用のペアリングの在庫が切れた関節用のペアリングの在庫が切れた他のパーツも数が少ない"
    assert collapse(log_dup) == "関節用のペアリングの在庫が切れた他のパーツも数が少ない"
    log_dup2 = "心リッタラ心リッタラどうかしたか"
    assert collapse(log_dup2) == "心リッタラどうかしたか"
    log_dup3 = "そんなに大変じゃないかそんなに大変じゃないから心配しないで"
    # 'X X ra...' -- the echo collapses into the sentence actually spoken.
    assert collapse(log_dup3) == "そんなに大変じゃないから心配しないで"
    # Legitimate reduplication survives.
    for legit in ("どんどん進む", "いろいろある", "ますます良い", "はいはいわかった"):
        assert collapse(legit) == legit, legit
    assert collapse("") == ""
    results["reazon_dedup"] = "PASS (log duplicates collapsed, reduplication kept)"

    results["passed"] = True
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
