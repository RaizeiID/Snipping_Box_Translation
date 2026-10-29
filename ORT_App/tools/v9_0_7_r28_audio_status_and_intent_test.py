"""ORT v9.0.7 R28 -- the two Audio-page defects found by exploratory testing.

Bug 1. The audio status is rendered by TWO components -- `source_status` under
"Sumber aktif" and `audio_availability` in the AUDIO WORKSPACE -- but each
handler updated only one of them. Switching the source refreshed the first;
changing the device, engine or usage refreshed the second. Both are visible at
once, so the page could state two different devices simultaneously:

    Mesin efektif=LOCAL_LIVE; perangkat lokal=HYBRID     (top)
    Mesin efektif=LOCAL_LIVE; perangkat lokal=CPU        (workspace)

Reproduced in both directions in a live browser session.

Bug 2. The combination card sat inside `ocr_runtime_panel`, so switching to
Audio blanked it -- even though the audio launcher calls resolve_resource_plan
with the very same ladder. The knobs kept working; only the explanation
disappeared.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


SRC = (Path(__file__).resolve().parent.parent / "webui.py").read_text(
    encoding="utf-8", errors="replace"
)

# --- Bug 1: every handler must feed BOTH status components -------------------
# Each wiring line that names one of the two must name the other as well.
wirings = re.findall(r"outputs=\[([^\]]*)\]", SRC)
paired = [w for w in wirings if "audio_availability" in w or "source_status" in w]
assert_true(len(paired) >= 8, f"expected the audio wirings, found {len(paired)}")
for w in paired:
    assert_true(
        "audio_availability" in w and "source_status" in w,
        f"one-sided status wiring, the two cards can drift: outputs=[{w.strip()}]",
    )
results["both_status_components_wired"] = f"PASS ({len(paired)} wirings)"


# The handlers must actually RETURN the same html twice, not just be wired for it.
def returns_of(func_name):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    if isinstance(sub.value, ast.Tuple):
                        return [ast.unparse(e) for e in sub.value.elts]
                    return [ast.unparse(sub.value)] if sub.value else []
    raise AssertionError(f"{func_name} not found")


HANDLERS = [
    "_refresh_audio_devices_ui", "_setup_audio_ui", "_audio_mode_updates",
    "_audio_engine_updates", "_audio_usage_updates", "_setup_audio_cloud_ui",
    "_save_audio_cloud_ui", "_clear_audio_cloud_ui",
]
for name in HANDLERS:
    parts = returns_of(name)
    assert_true(
        parts.count("status_html") >= 2,
        f"{name} returns the status once ({parts}); the second component keeps a stale value",
    )
results["handlers_return_status_twice"] = f"PASS ({len(HANDLERS)} handlers)"

# _translation_source_updates feeds both too, with the audio card always audio.
parts = returns_of("_translation_source_updates")
assert_true(len(parts) == 6, f"expected 6 outputs, got {len(parts)}: {parts}")
assert_true(
    "audio" in parts[-1] and "_translation_source_status_html" in parts[-1],
    f"source switch does not refresh the workspace card: {parts[-1]}",
)
results["source_switch_refreshes_both"] = "PASS"

# --- Bug 2: audio gets its own combination card ------------------------------
assert_true("audio_intent_summary_box" in SRC, "audio combination card was not added")
# It must sit above the overlay group, matching the OCR page's placement.
card_at = SRC.index("audio_intent_summary_box = gr.HTML")
overlay_after = SRC.index("audio_overlay_jump_btn")
assert_true(card_at < overlay_after, "audio card is not above Overlay subtitle")
results["audio_card_placed"] = "PASS"

from app.runtime.user_intent import (  # noqa: E402
    ACCURACY_FIRST, BALANCED, SPEED_ONLY, resolve_audio_intent,
)

# It must read the same way the OCR card does: profile+engine tilt, ladder tilt.
assert_true(
    resolve_audio_intent(profile="speed", engine="local",
                         resource_mode="efficient", resource_level=5,
                         device_resource="adaptive").goal == SPEED_ONLY,
    "Instant + Local + Efisien Maks should be pure speed",
)
assert_true(
    resolve_audio_intent(profile="accurate", engine="azure",
                         resource_mode="intensive", resource_level=5,
                         device_resource="quality").goal == ACCURACY_FIRST,
    "Accurate + Azure + Intensive Maks should be accuracy first",
)
assert_true(
    resolve_audio_intent(profile="normal", engine="azure_fallback",
                         resource_mode="stable", resource_level=3,
                         device_resource="adaptive").goal == BALANCED,
    "Balanced + fallback + Stabil Menengah should be balanced",
)
results["audio_intent_anchors"] = "PASS"

# Pushing the ladder toward Intensive must never become MORE speed-biased.
order = [SPEED_ONLY, "speed_accurate", BALANCED, ACCURACY_FIRST]
prev = -1
for mode, lvl in (("efficient", 5), ("efficient", 1), ("stable", 3), ("intensive", 1), ("intensive", 5)):
    g = resolve_audio_intent(profile="normal", engine="azure_fallback",
                             resource_mode=mode, resource_level=lvl,
                             device_resource="adaptive").goal
    idx = order.index(g) if g in order else order.index(ACCURACY_FIRST)
    assert_true(idx >= prev, f"{mode} L{lvl} moved backwards to {g}")
    prev = idx
results["audio_ladder_monotonic"] = "PASS"

# Every UI choice must resolve -- the radio offers three profiles, not two.
for prof in ("speed", "normal", "accurate"):
    for eng in ("local", "azure", "azure_fallback"):
        intent = resolve_audio_intent(profile=prof, engine=eng)
        assert_true(intent.goal, f"{prof}/{eng} produced no goal")
        assert_true("Kesimpulan" in intent.summary, f"{prof}/{eng} summary malformed")
results["all_ui_choices_resolve"] = "PASS (3 profiles x 3 engines)"

# Unknown values must fall back, never raise -- prefs files can hold anything.
for bad in ("", "bogus", None):
    assert_true(resolve_audio_intent(profile=bad, engine=bad).goal, f"{bad!r} did not fall back")
results["unknown_values_safe"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
