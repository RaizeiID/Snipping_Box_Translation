"""ORT v9.0.7-R11: progressive (typewriter) dialogue must reach the overlay.

Field report from GFL2 auto-story: the translation only ever showed the text
that had already finished appearing, never the dialogue as it typed out. The
log showed OCR tracking every growth step correctly, while the overlay gate
discarded them:

    [OCR] Lentine War. War never changes. Only by main
    [OCR] ...Only by maintaining a balance of
    [COMMIT] suppress | state=FINAL_LOCKED | reason=single_final_per_turn_locked
    [COMMIT] suppress | state=FINAL_LOCKED | reason=single_final_per_turn_locked

    overlay_committed=34 | overlay_suppressed=63 | multi_final_prevented=63

Two thirds of the typewriter never rendered. The single-final-per-turn lock is
meant to stop a turn re-rendering when the translator rephrases the SAME
sentence; it was also catching genuine new dialogue arriving in the same turn.

These sequences are taken verbatim from that log.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.runtime.overlay_commit_gate import (
    OverlayCommitGate,
    _is_progressive_growth,
    _normalise_for_growth,
)

results = {}

# ---- 1. Growth detection on the real captured sequence ------------------
TYPEWRITER = [
    "u Lentine War. War",
    "Lentine War. War never changes. Only by main",
    "Lentine War. War never changes. Only by maintaining a balance of",
    "ar. War never changes. Only by maintaining a balance of power bet",
    "ar. War never changes. Only by maintaining a balance of power between factio",
    "ar. War never changes. Only by maintaining a balance of power between factions can we",
    "ar. War never changes. Only by maintaining a balance of power between factions can we temporarily",
]
steps = list(zip(TYPEWRITER, TYPEWRITER[1:]))
detected = [_is_progressive_growth(a, b) for a, b in steps]
assert all(detected), [i for i, ok in enumerate(detected) if not ok]
results["growth_detected"] = f"PASS ({sum(detected)}/{len(steps)} progressive steps)"

# The leading noise genuinely changes shape between frames, which is why the
# check anchors on the tail instead of a prefix match.
assert not TYPEWRITER[3].startswith(TYPEWRITER[2][:10])
results["tolerates_unstable_prefix"] = "PASS (anchor is the tail, not startswith)"

# Net length can barely move while real text arrives, so growth is measured
# from what is appended after the anchor, not from total length.
a, b = TYPEWRITER[2], TYPEWRITER[3]
assert len(_normalise_for_growth(b)) - len(_normalise_for_growth(a)) < 6
assert _is_progressive_growth(a, b)
results["measures_appended_not_total"] = "PASS (net length +1, still detected)"

# ---- 2. Real turn changes must STAY locked ------------------------------
NEW_TURNS = [
    ("ar. War never changes. Only by maintaining a balance of power between factions can we",
     "Kenny Fabricating info, erasing evidence of the Conglomerate's connection"),
    ("Kenny Even if we do all that", "Kenny Even if we do all that"),
    ("Hurry up with your work. Don't dawdle", "After instructing her subordinates to maintain"),
    ("Lentine Trust me the people at the top", "Trust me- the people at the top"),
    ("Colphne Are we too late", "Groza Judging by the explosions"),
]
false_positives = [(a, b) for a, b in NEW_TURNS if _is_progressive_growth(a, b)]
assert not false_positives, false_positives
results["new_turns_stay_locked"] = f"PASS (0/{len(NEW_TURNS)} false positives)"

# ---- 3. End to end through the gate ------------------------------------
gate = OverlayCommitGate(min_visible_ms=0)
turn = "t000001-0e58b8ed"
committed, suppressed = 0, 0
for index, source in enumerate(TYPEWRITER):
    decision = gate.decide(
        speaker_html="<b>Lentine</b>",
        dialog_html=f"<p>ID {index}: {source}</p>",
        plain_translation=f"ID {index}: {source}",
        source_text=source,
        turn_id=turn,
        generation_id=index + 1,
        # The first step commits a final, which is what used to lock the rest.
        final=(index == 0),
        force_complete=(index == 0),
        source_stable=(index == 0),
    )
    if decision.commit:
        committed += 1
        gate.mark_committed(
            speaker_html="<b>Lentine</b>",
            dialog_html=f"<p>ID {index}: {source}</p>",
            plain_translation=f"ID {index}: {source}",
            source_text=source,
            turn_id=turn,
            generation_id=index + 1,
            signature=decision.signature,
            state=decision.state,
            final=decision.final,
        )
    else:
        suppressed += 1

assert committed == len(TYPEWRITER), f"only {committed}/{len(TYPEWRITER)} rendered"
results["end_to_end"] = f"PASS ({committed} committed, {suppressed} suppressed)"

# A genuinely different sentence in the same turn is still refused.
blocked = gate.decide(
    speaker_html="<b>Lentine</b>",
    dialog_html="<p>benar benar kalimat lain</p>",
    plain_translation="benar benar kalimat lain",
    source_text="Kenny Fabricating info, erasing evidence",
    turn_id=turn,
    generation_id=99,
)
assert not blocked.commit and blocked.state == "FINAL_LOCKED", blocked
results["protection_intact"] = f"PASS (unrelated text still {blocked.reason})"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
