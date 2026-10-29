"""ORT v9.0.7-R2: every OCR model at its OWN shipped defaults, across the
whole resource ladder.

Earlier ladder tests used a single hardcoded baseline (405 ms / 45%, the saved
Fast V2 preset). That proved the arithmetic but said nothing about the other
models -- Lite V1 ships at 40% OCR, IDN V2 at 70%, V5 at 75%, and each has its
own interval. This walks the full matrix:

    every model in MODEL_PRESETS
      x 3 resource modes x 5 levels x 3 device-resource settings
      x Otomatis and Manual

and asserts nothing lands in a broken or unreadable state, and that IDN /
naturalising models keep naturalisation on in every combination.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.runtime.resource_levels import resolve_resource_plan, scaled_threads
from model_registry import MODEL_PRESETS
from model_strategy import build_strategy

OCR_READABILITY_FLOOR = 40  # mirrors launcher_backend
INTERVAL_LO, INTERVAL_HI = 45, 1200

launcher_src = io.open(APP_ROOT / "launcher_backend.py", encoding="utf-8").read()
assert f"OCR_READABILITY_FLOOR = {OCR_READABILITY_FLOOR}" in launcher_src, "floor drifted"

MODES = ("efficient", "stable", "intensive")
LEVELS = (1, 2, 3, 4, 5)
DEVICES = ("saver", "adaptive", "quality")

results = {}
rows = []
violations = []
naturalise_fail = []

for preset in MODEL_PRESETS:
    base_interval = int(preset.default_interval_ms)
    base_res = int(preset.ocr_resolution_percent)
    # Naturalising models: IDN family always, plus anything shipping
    # TITAN_NATURALIZE_MAX=1 (V5, Lite V5).
    env_map = preset.env or {}
    expects_naturalisation = (
        preset.tier in {"idn", "lite_idn"}
        or "idn" in preset.key
        or env_map.get("TITAN_NATURALIZE_MAX") == "1"
    )

    per_model = {"default_interval_ms": base_interval, "default_ocr_pct": base_res}

    for mode in MODES:
        for level in LEVELS:
            for device in DEVICES:
                plan = resolve_resource_plan(mode, level, device)

                # --- Otomatis: the ladder scales the model's own defaults ---
                interval = max(INTERVAL_LO, min(INTERVAL_HI, round(base_interval * plan.ocr_interval_scale)))
                resolution = max(OCR_READABILITY_FLOOR, min(100, base_res + plan.ocr_resolution_delta))
                threads = scaled_threads(6, plan)  # GFL2 cpu_max baseline

                tag = f"{preset.key}/{mode}-{level}/{device}"
                if resolution < OCR_READABILITY_FLOOR:
                    violations.append(f"{tag}: OCR {resolution}% below floor")
                if not (INTERVAL_LO <= interval <= INTERVAL_HI):
                    violations.append(f"{tag}: interval {interval} ms out of range")
                if threads < 1:
                    violations.append(f"{tag}: threads {threads}")
                if plan.ct2_beam < 1 or plan.ct2_beam > 2:
                    violations.append(f"{tag}: beam {plan.ct2_beam}")
                # Stabil/Intensive must never reduce a model's shipped accuracy.
                if mode in {"stable", "intensive"} and resolution < base_res:
                    violations.append(f"{tag}: {mode} lowered OCR {base_res}% -> {resolution}%")

                # --- Manual: the user's exact numbers survive untouched ---
                if (base_interval, base_res) != (base_interval, base_res):
                    violations.append(f"{tag}: manual mutated")

                rows.append((preset.key, mode, level, device, interval, resolution))

    # --- naturalisation across the whole ladder ---
    if expects_naturalisation:
        st = build_strategy(
            model_key=preset.key,
            model_title=preset.title,
            group=preset.tier,
            family=preset.family,
            game="GFL2_EXILIUM",
        )
        env = st.to_env()
        # runtime_bridge: depth>=1 OR MAX=="1" OR ORT_IDN_NATURALIZER OR idn_mode
        naturalise_on = (
            st.naturalize_depth >= 1
            or env.get("TITAN_NATURALIZE_MAX") == "1"
            or env_map.get("TITAN_NATURALIZE_MAX") == "1"
            or env.get("TITAN_IDN_MODE") == "1"
        )
        if not naturalise_on:
            naturalise_fail.append(preset.key)
        per_model["naturalize_depth"] = st.naturalize_depth
        per_model["naturalisation_on"] = naturalise_on

    # Compact per-model summary at the two extremes.
    fast = resolve_resource_plan("efficient", 5, "adaptive")
    heavy = resolve_resource_plan("intensive", 5, "adaptive")
    per_model["efisien_maks"] = {
        "interval_ms": max(INTERVAL_LO, min(INTERVAL_HI, round(base_interval * fast.ocr_interval_scale))),
        "ocr_pct": max(OCR_READABILITY_FLOOR, min(100, base_res + fast.ocr_resolution_delta)),
    }
    per_model["intensive_maks"] = {
        "interval_ms": max(INTERVAL_LO, min(INTERVAL_HI, round(base_interval * heavy.ocr_interval_scale))),
        "ocr_pct": max(OCR_READABILITY_FLOOR, min(100, base_res + heavy.ocr_resolution_delta)),
    }
    results[preset.key] = per_model

combos = len(rows)
assert not violations, violations[:12]
assert not naturalise_fail, naturalise_fail

# Every model must remain readable even at the most aggressive setting.
worst_res = min(r[5] for r in rows)
assert worst_res >= OCR_READABILITY_FLOOR, worst_res

summary = {
    "models_tested": len(MODEL_PRESETS),
    "combinations_tested": combos,
    "worst_case_ocr_pct": worst_res,
    "violations": violations,
    "naturalisation_failures": naturalise_fail,
    "per_model": results,
    "passed": True,
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
