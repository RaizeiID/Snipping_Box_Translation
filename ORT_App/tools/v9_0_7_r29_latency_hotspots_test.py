"""ORT v9.0.7 R29 -- the two hotspots the field logs actually pointed at.

Breaking a real 3-minute session down per stage overturned the assumption that
the translator was the bottleneck:

    ocr_body_ms                median  40 ms   p90 169 ms   max 1265 ms
    backend_translate_ms       median   0 ms   p90 106 ms   max  490 ms
    ocr_readability_rescue_ms  median   0 ms   p90  80 ms   max  184 ms
    name_roi_ms                median  14 ms   p90  31 ms   max   64 ms

Hotspot 1 -- the readability rescue was firing on 59% of frames, and 264 of
those 311 rescues were triggered by `low_story_profile`: the player had set OCR
to 47% and the story floor is 50, which made `low_profile` unconditionally true.
Those 264 cost 21.0 of the run's 22.9 rescue-seconds and returned identical text
232 times, SHORTER text 26 times, and recovered words 6 times.

Hotspot 2 -- R21 put its word floor on every complete sentence, so a short
opener cancelled the split for a whole block. 21 of 100 long blocks were refused
that way, and an unsplit block is exactly where CT2 drops clauses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ocr.readability_guard import score_text  # noqa: E402
from translation_engine import _WORD_RE, _split_sentences  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


# --- Hotspot 1: low resolution alone must not force a re-read ----------------
CLEAN = (
    "As an archive considered bad luck by everyone in Mangi Security, nearly "
    "everyone has forgotten about its existence. So it is the best place for hiding intel"
)
a = score_text(CLEAN, 47, 50)
assert_true(a.score >= 0.78, f"test premise stale: clean line scored {a.score}")
assert_true(not a.needs_rescue, f"clean 47% read still forced a rescue ({a.reason})")
results["clean_low_res_not_rescued"] = f"PASS (score {a.score})"

# The same line at a healthy resolution must also pass -- nothing regressed.
assert_true(not score_text(CLEAN, 60, 50).needs_rescue, "clean 60% read was rescued")
results["clean_normal_res_not_rescued"] = "PASS"

# Genuinely corrupted text must STILL be rescued; that trigger earned its keep
# (23 firings, 39% improved) and R29 must not weaken it.
NOISY = "Iltn B4lth1lde Wh4t 4b0ut y0u? Tr4pp3d bec4use y0ure 1n t0 d33p"
assert_true(score_text(NOISY, 60, 50).needs_rescue, "corrupted text was not rescued")
results["corruption_still_rescued"] = "PASS"

# Low resolution raises the bar rather than bypassing it: a middling read that
# passes at 60% must still be caught at 47%.
MIDDLING = "Ilu Balthllde see Followlng that wornan hablt of always plannlng for the"
low = score_text(MIDDLING, 47, 50)
high = score_text(MIDDLING, 60, 50)
assert_true(
    low.needs_rescue or not high.needs_rescue,
    "low resolution must be at least as suspicious as normal resolution",
)
results["low_res_is_stricter"] = "PASS"

# Empty or wordless output is still a rescue case.
assert_true(score_text("", 47, 50).reason == "empty_or_no_words", "empty text mishandled")
results["empty_still_flagged"] = "PASS"


# --- Hotspot 2: the word floor belongs on the tail, not on finished sentences -
def splits(text, min_words=3):
    parts = _split_sentences(text)
    if len(parts) < 2:
        return False
    tail = [c for c, done, _ in parts if not done and c.strip()]
    if tail and len(_WORD_RE.findall(tail[-1])) < min_words:
        return False
    return True


# A short opener must no longer cancel the split of a long block.
for line in (
    "Don't worry. Right now, you're officially registered as a Doll under Mangi Security",
    "How wonderful. That child has found the place of belonging she hoped for",
    "Exactly. And for someone who doesn't trust Dolls, this is the ideal storage location",
):
    assert_true(splits(line), f"short opener still cancels the split: {line[:40]!r}")
results["short_opener_no_longer_blocks"] = "PASS (3 lines)"

# The case the floor was written for is still protected: there the TAIL is the
# one-word fragment, and translating "I" alone is worse than translating "No. I".
for line in ("No. I", "Yes. I", "Right. We"):
    assert_true(not splits(line), f"tiny tail was split: {line!r}")
results["tiny_tail_still_protected"] = "PASS"

# A complete short sentence is a legitimate unit once the tail is substantial.
assert_true(splits("No. I will go and find her now."), "complete short sentence blocked a valid split")
results["complete_short_sentence_allowed"] = "PASS"

# The floor must stay configurable and must not fire when disabled.
assert_true(splits("No. I", min_words=0), "floor of 0 still blocked a split")
results["floor_configurable"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
