"""ORT v9.0.7 R17 -- backend backpressure regression test.

Auto pacing was a fixed constant, set with no regard for how long a translation
actually takes. Measured on this machine the backend runs ~55 ms on a short line
but 400-500 ms on a long one once the GPU is shared with EasyOCR and the game,
while the commit floor sat at 140 ms -- so long lines queued faster than they
drained. Field log 15:19-15:20 shows backend=428 ms with the queue still
filling, then 479, then a 1184 ms round trip.

The scheduler now raises its commit interval to match the observed round trip,
and relaxes again when the backend recovers.

Checks:
  1. no measurement -> behaviour is exactly the old fixed pacing
  2. a fast backend does not slow pacing down (Auto stays snappy)
  3. a sustained slow backend raises pacing toward the drain rate
  4. recovery brings pacing back down within a few frames
  5. pacing is bounded, and junk input is ignored
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("ORT_DIALOG_SCHEDULER_PROFILE", "auto_story")

from app.runtime.story_dialogue_scheduler import StoryDialogueScheduler  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def pacing(scheduler):
    """Effective floor the decide() path would apply."""
    floor = max(
        scheduler.progressive_min_ms,
        int(os.environ.get("ORT_AUTO_SMOOTH_MIN_MS", "220")),
    )
    if scheduler.backend_pace_ms > 0:
        headroom = float(os.environ.get("ORT_BACKPRESSURE_HEADROOM", "1.15"))
        ceiling = int(os.environ.get("ORT_BACKPRESSURE_MAX_MS", "900"))
        floor = max(floor, min(ceiling, int(scheduler.backend_pace_ms * headroom)))
    return floor

# 1 -- untouched without feedback
fresh = StoryDialogueScheduler.from_env()
assert_true(fresh.backend_pace_ms == 0, "fresh scheduler must carry no measurement")
baseline = pacing(fresh)
results["no_feedback_unchanged"] = f"PASS (floor {baseline} ms)"

# 2 -- a fast backend must not slow anything down
fast = StoryDialogueScheduler.from_env()
for _ in range(10):
    fast.note_backend_latency(55)
assert_true(pacing(fast) == baseline, f"fast backend changed pacing to {pacing(fast)}")
results["fast_backend_stays_snappy"] = f"PASS (still {pacing(fast)} ms at 55 ms backend)"

# 3 -- a sustained slow backend raises pacing toward the drain rate
slow = StoryDialogueScheduler.from_env()
for _ in range(12):
    slow.note_backend_latency(480)
slow_pace = pacing(slow)
assert_true(slow_pace > baseline, "slow backend did not raise pacing")
assert_true(slow_pace >= 400, f"pacing {slow_pace} ms still queues faster than a 480 ms drain")
results["slow_backend_backs_off"] = f"PASS ({baseline} -> {slow_pace} ms at 480 ms backend)"

# 4 -- recovery
for _ in range(12):
    slow.note_backend_latency(55)
assert_true(
    pacing(slow) == baseline,
    f"pacing stuck at {pacing(slow)} ms after the backend recovered",
)
results["recovers_when_backend_frees"] = f"PASS (back to {pacing(slow)} ms)"

# 5 -- bounded, and junk ignored
wild = StoryDialogueScheduler.from_env()
for _ in range(30):
    wild.note_backend_latency(99999)
assert_true(pacing(wild) <= int(os.environ.get("ORT_BACKPRESSURE_MAX_MS", "900")), "pacing exceeded its ceiling")
before = wild.backend_pace_ms
for junk in (None, "abc", -5, 0, float("nan"), float("inf")):
    try:
        wild.note_backend_latency(junk)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"note_backend_latency raised on {junk!r}: {exc}")
    # NaN is the dangerous one: it fails every comparison, so a naive
    # `value <= 0` guard lets it through and the average never recovers.
    assert_true(
        wild.backend_pace_ms == before,
        f"junk input {junk!r} changed the average to {wild.backend_pace_ms}",
    )
results["bounded_and_junk_safe"] = f"PASS (ceiling {pacing(wild)} ms)"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
