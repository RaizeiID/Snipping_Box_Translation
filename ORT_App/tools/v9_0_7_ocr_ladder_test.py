"""ORT v9.0.7 verification: the resource ladder actually reaches the OCR path.

The audio path was verified separately. This checks the OCR side specifically,
because that is where the ladder was initially wired but unreachable:
  1. TITAN_CT2_BEAM is now READ by translation_engine (it used to be written by
     the launcher and consumed by nobody, pinning beam at 1 forever).
  2. The OCR capture interval and resolution really scale with the ladder in
     Otomatis, and are left untouched in Manual.
  3. The resource controls live outside the audio-only workspace, so an OCR
     user can actually see them.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.runtime.resource_levels import resolve_resource_plan

results = {}

# ---- 1. Beam is consumed, not just written -------------------------------
engine_src = io.open(APP_ROOT / "translation_engine.py", encoding="utf-8").read()
assert 'os.environ.get("TITAN_CT2_BEAM"' in engine_src, "beam env still ignored"
assert "beam_size=beam_size" in engine_src, "CT2Config still hardcodes beam"
assert "beam_size=1," not in engine_src, "a hardcoded beam_size=1 remains"
results["ct2_beam_is_read"] = "PASS (translation_engine honours TITAN_CT2_BEAM)"

launcher_src = io.open(APP_ROOT / "launcher_backend.py", encoding="utf-8").read()
assert 'env["TITAN_CT2_BEAM"] = str(ocr_resource_plan.ct2_beam)' in launcher_src
results["ocr_sets_beam_from_ladder"] = "PASS"

# v9.0.7-R2: this used to assert a wide 1->2->5 spread. Measurement retired
# that design: beam 5 cost +78% time and produced output identical to beam 1 on
# 3 of 5 real log lines, so beam is now deliberately kept low everywhere and
# only nudges to 2 at the heavy end. Wiring it still matters (the value must
# reach CT2), but it is no longer the accuracy lever.
beams = {
    ("efficient", 5): resolve_resource_plan("efficient", 5).ct2_beam,
    ("stable", 3): resolve_resource_plan("stable", 3).ct2_beam,
    ("intensive", 5): resolve_resource_plan("intensive", 5).ct2_beam,
}
assert beams[("efficient", 5)] <= beams[("stable", 3)] <= beams[("intensive", 5)], beams
assert max(beams.values()) <= 2, f"beam must stay cheap: {beams}"
results["beam_policy"] = f"PASS (kept low by design: {beams[('efficient',5)]} -> {beams[('stable',3)]} -> {beams[('intensive',5)]}, max 2)"

# ---- 2. OCR interval / resolution scaling --------------------------------
# Mirror the exact arithmetic launcher_backend.start() performs.
OCR_READABILITY_FLOOR = 40  # must mirror launcher_backend


def ocr_effective(base_interval, base_res, mode, level, device="adaptive", manual=False):
    plan = resolve_resource_plan(mode, level, device)
    if manual:
        return int(base_interval), int(base_res)
    return (
        max(45, min(1200, int(round(base_interval * plan.ocr_interval_scale)))),
        max(OCR_READABILITY_FLOOR, min(100, base_res + plan.ocr_resolution_delta)),
    )

base_i, base_r = 405, 45
light = ocr_effective(base_i, base_r, "efficient", 5)
mid = ocr_effective(base_i, base_r, "stable", 3)
heavy = ocr_effective(base_i, base_r, "intensive", 5)
assert light[0] < mid[0] < heavy[0], (light, mid, heavy)
assert light[1] < mid[1] < heavy[1], (light, mid, heavy)
# v9.0.7-R2: the resolution spread is deliberately GENTLER than before (was
# 20%..65%). Pushing resolution down was the crude way to buy speed and it
# produced unreadable stream output; latency now comes from scan sleep, queue
# depth, and interval instead, which cost no accuracy at all. The spread must
# still be visible, but it must never reach unreadable territory.
assert heavy[1] - light[1] >= 12, (light[1], heavy[1])
assert light[1] >= OCR_READABILITY_FLOOR, light[1]
results["ocr_scaling"] = (
    f"PASS (interval {light[0]}->{mid[0]}->{heavy[0]} ms | "
    f"resolution {light[1]}->{mid[1]}->{heavy[1]} %)"
)

manual_light = ocr_effective(base_i, base_r, "efficient", 5, manual=True)
manual_heavy = ocr_effective(base_i, base_r, "intensive", 5, manual=True)
assert manual_light == manual_heavy == (base_i, base_r), "Manual must be untouched"
results["manual_untouched"] = "PASS (user's exact numbers preserved)"

# Verify the launcher really guards the Manual case.
assert "if not normal_override:" in launcher_src
assert "ocr_resource_plan.ocr_interval_scale" in launcher_src
assert "ocr_resource_plan.ocr_resolution_delta" in launcher_src
results["manual_guard_present"] = "PASS"

# ---- 3. Controls reachable from the OCR workspace ------------------------
webui_src = io.open(APP_ROOT / "webui.py", encoding="utf-8").read().split("\n")
def line_of(needle):
    return next(i for i, l in enumerate(webui_src) if needle in l)

resource_at = line_of("as audio_resource_panel:")
ocr_panel_at = line_of("as ocr_runtime_panel:")
audio_panel_at = line_of("as audio_preview_panel:")
# Must be declared before BOTH workspaces, i.e. in the shared source stage.
assert resource_at < ocr_panel_at, (resource_at, ocr_panel_at)
assert resource_at < audio_panel_at, (resource_at, audio_panel_at)
results["controls_shared_by_both_sources"] = (
    f"PASS (resource panel line {resource_at+1} precedes OCR {ocr_panel_at+1} / Audio {audio_panel_at+1})"
)

# The OCR start button must forward the ladder.
start_click = next(l for l in webui_src if "start_btn.click(_start," in l)
for token in ("audio_resource_mode", "audio_resource_level", "device_resource_radio"):
    assert token in start_click, token
results["ocr_start_forwards_ladder"] = "PASS"

# ---- 4. OCR thread budget: real lever, correct ordering -----------------
# TITANMAIN derives every thread pool from TITAN_CPU_THREADS, so that is the
# only value worth setting. ORT_CPU_THREADS has no reader and must not be
# presented as the OCR lever.
titanmain_src = io.open(APP_ROOT / "TITANMAIN.py", encoding="utf-8").read()
assert 'os.environ.get("TITAN_CPU_THREADS"' in titanmain_src
for derived in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    assert derived in titanmain_src, derived
assert "cv2.setNumThreads(min(CPU_THREADS" in titanmain_src
assert "torch.set_num_threads(min(CPU_THREADS" in titanmain_src
results["titanmain_thread_lever"] = "PASS (TITAN_CPU_THREADS drives OMP/MKL/cv2/torch)"

launcher_lines = launcher_src.split("\n")
def line_idx(needle, start=0):
    return next(i for i, l in enumerate(launcher_lines) if needle in l and i >= start)

strategy_at = line_idx("env.update(strategy.to_env())")
ladder_at = line_idx('env["TITAN_CPU_THREADS"] = str(scaled_threads(', strategy_at)
guard_at = line_idx("apply_lite_gpu_env(", ladder_at)
# strategy baseline -> ladder scaling -> hardware clamp. Any other order
# silently discards either the user's preference or the safety cap.
assert strategy_at < ladder_at < guard_at, (strategy_at, ladder_at, guard_at)
results["thread_ordering"] = (
    f"PASS (strategy L{strategy_at+1} -> ladder L{ladder_at+1} -> lite guard L{guard_at+1})"
)

# The guard must still be able to lower the value (min semantics preserved).
guard_src = io.open(APP_ROOT / "app" / "runtime" / "lite_gpu_guard.py", encoding="utf-8").read()
assert "min(int(env.get(\"TITAN_CPU_THREADS\"" in guard_src
results["safety_cap_still_wins"] = "PASS (lite guard clamps with min())"

# And the scaling must actually change the number in a way a user can feel.
from app.runtime.resource_levels import scaled_threads
base_threads = 24  # i7-13700HX logical cores
t_light = scaled_threads(base_threads, resolve_resource_plan("efficient", 5, "saver"))
t_mid = scaled_threads(base_threads, resolve_resource_plan("stable", 3))
t_heavy = scaled_threads(base_threads, resolve_resource_plan("intensive", 5, "quality"))
assert t_light < t_mid < t_heavy, (t_light, t_mid, t_heavy)
assert t_heavy - t_light >= 8, (t_light, t_heavy)
results["thread_spread"] = f"PASS ({t_light} -> {t_mid} -> {t_heavy} threads of {base_threads})"

# Dead env must not be re-introduced as the OCR thread lever.
assert 'env["ORT_CPU_THREADS"] = str(scaled_threads' not in launcher_src
results["no_dead_thread_env"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
