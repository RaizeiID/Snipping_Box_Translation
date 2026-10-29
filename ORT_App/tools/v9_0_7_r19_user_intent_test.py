"""ORT v9.0.7 R19 -- combination-goal regression test.

Each knob was read in isolation, so nothing asked what the user was actually
after. That mattered because the strict-CT2 story guard held 97 frames in one
field session (80 mid-sentence) regardless of goal -- correct for V3+Intensive,
wrong for Fast+Efisien Maks, where the player picked the speed core precisely to
see words early.

The anchors below are the combinations the user named, in their words.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.runtime.user_intent import (  # noqa: E402
    ACCURACY_FIRST,
    ACCURACY_LIGHT,
    BALANCED,
    SPEED_ACCURATE,
    SPEED_ONLY,
    resolve_intent,
)

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def goal_of(**kw):
    return resolve_intent(**kw).goal


# name -> (kwargs, expected goal). Every entry traces to something the user said.
ANCHORS = {
    # "core fast efisien maks ... targetnya adalah kecepatan dan bukan akurasi"
    "fast_efficient_max": (
        dict(group="fast", model_key="fast_v1", level=1,
             resource_mode="efficient", resource_level=5, device_resource="adaptive"),
        SPEED_ONLY,
    ),
    # same, with the headroom the user mentioned ("high resource") -- goal is
    # unchanged, because device is capability and not intent.
    "fast_efficient_max_quality": (
        dict(group="fast", model_key="fast_v1", level=1,
             resource_mode="efficient", resource_level=5, device_resource="quality"),
        SPEED_ONLY,
    ),
    # "core v1 atau bahkan core fast dengan intensive ... dengan resource optimal
    #  ... ingin kualitas bagus tetapi proses cepat"
    "fast_intensive_quality": (
        dict(group="fast", model_key="fast_v1", level=1,
             resource_mode="intensive", resource_level=5, device_resource="quality"),
        SPEED_ACCURATE,
    ),
    # "core v2, resource stabil, adaptif ... benar benar seimbang"
    "v2_stable_adaptive": (
        dict(group="normal", model_key="v2", level=2,
             resource_mode="stable", resource_level=3, device_resource="adaptive"),
        BALANCED,
    ),
    # "memilih efisien dan optimal ... ingin prosesnya efisien tetapi tetap
    #  menjaga sedikit keakuratan"
    "v2_efficient_quality": (
        dict(group="normal", model_key="v2", level=2,
             resource_mode="efficient", resource_level=3, device_resource="quality"),
        SPEED_ACCURATE,
    ),
    "v3_intensive_max": (
        dict(group="normal", model_key="v3", level=3,
             resource_mode="intensive", resource_level=5, device_resource="quality"),
        ACCURACY_FIRST,
    ),
    "idn_v5_intensive_max": (
        dict(group="idn", model_key="idn_v5", level=5,
             resource_mode="intensive", resource_level=5, device_resource="quality"),
        ACCURACY_FIRST,
    ),
    # accuracy still the goal, but on a light runtime
    "idn_v5_efficient_max": (
        dict(group="idn", model_key="idn_v5", level=5,
             resource_mode="efficient", resource_level=5, device_resource="adaptive"),
        ACCURACY_LIGHT,
    ),
}

for name, (kwargs, expected) in ANCHORS.items():
    got = goal_of(**kwargs)
    assert_true(got == expected, f"{name}: expected {expected}, got {got}")
results["user_stated_anchors"] = f"PASS ({len(ANCHORS)} combinations)"

# Hemat means the machine is the constraint: never sit on a heavy accuracy goal.
heavy = dict(group="normal", model_key="v3", level=3,
             resource_mode="intensive", resource_level=5)
assert_true(goal_of(**heavy, device_resource="quality") == ACCURACY_FIRST, "quality should stay accuracy-first")
assert_true(goal_of(**heavy, device_resource="saver") != ACCURACY_FIRST, "saver must step back from the heavy goal")
results["saver_steps_back"] = "PASS"

# The fragment policy has to follow the goal, since that is the whole point.
POLICY = {
    SPEED_ONLY: True, SPEED_ACCURATE: True, BALANCED: True,
    ACCURACY_FIRST: False, ACCURACY_LIGHT: False,
}
seen = set()
for kwargs, _ in ANCHORS.values():
    intent = resolve_intent(**kwargs)
    seen.add(intent.goal)
    assert_true(
        intent.release_fragments == POLICY[intent.goal],
        f"{intent.goal} released={intent.release_fragments}, contradicts its own policy",
    )
    if intent.release_fragments:
        assert_true(intent.fragment_min_words >= 1, "release without a word floor")
    # Only pure speed may skip the accurate final.
    assert_true(
        intent.prefer_final_accuracy == (intent.goal != SPEED_ONLY),
        f"{intent.goal}: wrong final-accuracy policy",
    )
assert_true(len(seen) >= 4, f"anchors only covered {len(seen)} goals, coverage too thin")
results["policy_follows_goal"] = f"PASS ({len(seen)} distinct goals covered)"

# Monotonic: pushing the ladder toward Intensive must never make it MORE
# speed-biased. This is what stops the scale being arbitrary.
order = [SPEED_ONLY, SPEED_ACCURATE, BALANCED, ACCURACY_FIRST]
prev = -1
for mode, lvl in (("efficient", 5), ("efficient", 1), ("stable", 3), ("intensive", 1), ("intensive", 5)):
    g = goal_of(group="normal", model_key="v2", level=2,
                resource_mode=mode, resource_level=lvl, device_resource="adaptive")
    idx = order.index(g) if g in order else order.index(ACCURACY_FIRST)
    assert_true(idx >= prev, f"{mode} L{lvl} moved backwards to {g}")
    prev = idx
results["ladder_is_monotonic"] = "PASS"

# Every goal must produce a readable summary; the card renders it verbatim.
for kwargs, _ in ANCHORS.values():
    intent = resolve_intent(**kwargs)
    assert_true(len(intent.summary) > 60, "summary too short to be useful")
    assert_true("Kesimpulan" in intent.summary, "summary missing its conclusion")
results["summary_renderable"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
