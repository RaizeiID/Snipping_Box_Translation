"""ORT v9.0.7 R27 -- registry-backed name repair, and the collisions it must survive.

The registry knew every character's spelling but never used it to repair a
misread one, so "Nlkketa", "Ra1zei", "C0lphne" and "UIIrid" reached the
translator as written.

The risk in fixing that is the cast itself: Helen and Helena, Balthilde and
Bathilde, Heli. Turning one character into another mid-scene is worse than
leaving a typo alone, so this test spends most of its length on refusals rather
than repairs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ocr.name_autocorrect import NameAutoCorrector, fold  # noqa: E402
from app.runtime.prediction_guard import PredictionGuard  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


guard = PredictionGuard.from_env()
corrector = guard._name_corrector()
assert_true(corrector is not None, "auto-corrector did not build from the registry")

# --- 1. the structural property the whole design rests on --------------------
# If two names ever fold together the index must refuse them, not guess.
assert_true(
    not corrector.collisions,
    f"folds collide, repair would be a coin toss: {corrector.collisions}",
)
for a, b in (("Helen", "Helena"), ("Balthilde", "Bathilde"), ("Helen", "Heli")):
    assert_true(fold(a) != fold(b), f"{a} and {b} fold together")
results["no_fold_collisions"] = f"PASS ({len(corrector.names)} names)"

# --- 2. correct spellings are never candidates -------------------------------
for name in corrector.names:
    out, canonical, reason = corrector.correct_token(name)
    assert_true(out == name and canonical is None, f"{name!r} was rewritten to {out!r}")
    assert_true(reason in ("already_exact", "too_short"), f"{name}: {reason}")
results["exact_names_untouched"] = "PASS"

# --- 3. glyph corruption is repaired -----------------------------------------
REPAIR = {
    "Nlkketa": "Nikketa",
    "Ra1zei": "Raizei",
    "C0lphne": "Colphne",
    "Gr0za": "Groza",
    "UIIrid": "Ullrid",
    "Lentlne": "Lentine",
    "Klukal": "Klukai",
    "HeIen": "Helen",
    "HeIena": "Helena",
    "Ba1thilde": "Balthilde",
    # The collision pair must repair to DIFFERENT names, not to each other.
    "Balthllde": "Balthilde",
    "Bathllde": "Bathilde",
}
for src, want in REPAIR.items():
    _, got, _ = corrector.correct_token(src)
    assert_true(got == want, f"{src!r} -> {got!r}, expected {want!r}")
results["glyph_corruption_repaired"] = f"PASS ({len(REPAIR)} tokens)"

# A possessive belongs to the sentence. Matching used to swallow it, deleting
# the 's from "Dushevnaya's" 176 times across the logs.
for src, want in (("Berryfleld's", "Berryfield's"), ("Nlkketa's", "Nikketa's"),
                  ("Dushevnaya's", "Dushevnaya's"), ("Cocoon's", "Cocoon's")):
    got, _, _ = corrector.correct_token(src)
    assert_true(got == want, f"possessive mangled: {src!r} -> {got!r}, expected {want!r}")
results["possessive_preserved"] = "PASS"

# Folding erases apostrophes, so "he'll" collapses onto "Heli". No registered
# name contains one, which makes the character itself the discriminator.
for src in ("he'll", "we'll", "she'll", "it'll", "he'Il"):
    _, got, reason = corrector.correct_token(src)
    assert_true(got is None, f"contraction {src!r} became {got!r}")
    assert_true(reason == "contraction", f"{src}: refused for the wrong reason ({reason})")
results["contractions_safe"] = "PASS"

# Tier 2 is off by default, because on real lines it turned "care" into Carmen
# (54x), "making" into Mayling (41x) and "realize" into Raizei (13x). The margin
# rule cannot catch those: no other NAME is close, and the module has no
# dictionary to know they are words.
from app.ocr.name_autocorrect import fuzzy_enabled  # noqa: E402

assert_true(not fuzzy_enabled(), "fuzzy tier must default to off")
_, got, reason = corrector.correct_token("nketta")
assert_true(got is None and reason == "no_exact_fold", f"fuzzy ran while disabled: {got!r}")
for word in ("care", "came", "cared", "making", "sweep", "realize", "charm"):
    _, got, _ = corrector.correct_token(word)
    assert_true(got is None, f"ordinary word {word!r} became {got!r} with fuzzy off")
results["fuzzy_tier_off_by_default"] = "PASS"

# When deliberately enabled it must still reach the deep corruptions, and still
# refuse the ambiguous ones -- that is the whole point of the margin.
os.environ["ORT_NAME_AUTOCORRECT_FUZZY"] = "1"
try:
    for src, want in (("nketta", "Nikketa"), ("Nkketa", "Nikketa"), ("DushevnaVa", "Dushevnaya")):
        _, got, reason = corrector.correct_token(src)
        assert_true(got == want, f"{src!r} -> {got!r}, expected {want!r}")
        assert_true(reason == "fuzzy_margin", f"{src}: reached via {reason}")
    for token in ("Helenna", "Helenaa", "Helenia"):
        _, got, _ = corrector.correct_token(token)
        assert_true(got is None, f"ambiguous {token!r} was guessed as {got!r} with fuzzy on")
finally:
    os.environ["ORT_NAME_AUTOCORRECT_FUZZY"] = "0"
    corrector._cache.clear()
results["fuzzy_tier_when_enabled"] = "PASS"

# --- 4. refusals: the part that protects the cast ----------------------------
# Each of these sits between Helen and Helena. Guessing is not allowed, whether
# the fuzzy tier is on (refused on margin) or off (never reached at all).
for token in ("Helenna", "Helenaa", "Helenia", "Helenn", "Helenae"):
    _, got, reason = corrector.correct_token(token)
    assert_true(got is None, f"ambiguous {token!r} was guessed as {got!r}")
    assert_true(
        reason in ("ambiguous_or_far", "no_exact_fold"),
        f"{token}: refused for the wrong reason ({reason})",
    )
results["ambiguous_refused"] = "PASS"

# Ordinary words must not be dragged onto a name.
for word in ("because", "commander", "helicopter", "believe", "children", "collapse"):
    _, got, _ = corrector.correct_token(word)
    assert_true(got is None, f"ordinary word {word!r} was rewritten to {got!r}")
results["ordinary_words_safe"] = "PASS"

# The collision that folding alone does NOT catch: registry names were checked
# against each other, never against the language. "Hell" and "Heli" fold to the
# same key, so an English word landed on a character. Both guards must hold --
# the module's own stoplist, and the registry blocklist the caller injects.
for word in ("Hell", "hell", "Hall", "Hill", "Well"):
    _, got, reason = corrector.correct_token(word)
    assert_true(got is None, f"English word {word!r} became {got!r}")
assert_true(fold("Hell") == fold("Heli"), "test premise stale: Hell no longer folds onto Heli")
blocked = corrector.correct_token("Hell", is_blocked=lambda t: True)
assert_true(blocked[1] is None, "caller veto was ignored")
for line in ("Hell is not a speaker", "Hell is empty tonight"):
    assert_true(guard.apply(line, raw_text=line).text == line, f"{line!r} was rewritten")
results["english_words_not_names"] = "PASS"

# --- 5. end to end through the guard, and cache honesty ----------------------
r = guard.apply("Nlkketa looks at the frame", raw_text="Nlkketa looks at the frame")
assert_true("Nikketa" in r.text, f"repair did not reach the guard output: {r.text!r}")
assert_true(r.final_cache_blocked, "a guessed repair must not be cached as final")

untouched = "Helen and Helena spoke at once."
assert_true(guard.apply(untouched, raw_text=untouched).text == untouched, "clean line was altered")
results["end_to_end"] = "PASS"

# --- 6. cost ------------------------------------------------------------------
sample = [
    "Nlkketa looks at the frame while Ra1zei waits by the door.",
    "The convoy arrives in 15 minutes, Commander.",
    "C0lphne and Gr0za went ahead without telling anyone about it.",
] * 400
for _ in range(200):
    corrector.correct(sample[0])
t0 = time.perf_counter()
for line in sample:
    corrector.correct(line)
per_line_ms = (time.perf_counter() - t0) / len(sample) * 1000
# Frames arrive about every 100 ms; anything near that is a regression.
assert_true(per_line_ms < 1.0, f"too slow for the frame budget: {per_line_ms:.3f} ms/line")
results["cost_ms_per_line"] = round(per_line_ms, 4)

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
