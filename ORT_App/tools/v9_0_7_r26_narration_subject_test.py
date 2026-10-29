"""ORT v9.0.7 R26 -- a character name in narration is the subject, not a label.

A name at the head of a line was always treated as a speaker prefix: moved into
the speaker field and stripped from the body. Correct for "Helen We should move
now", wrong for narration -- "Nikketa looks at Balthilde's battered frame" came
out as "looks at Balthilde's battered frame", a sentence with nobody in it.
Across the user's own logs, 691 lines lost their subject that way.

English separates the cases by capitalisation: a speaker label is followed by
the opening of an utterance (capital); a subject is followed by its verb or a
conjunction (lower case). The lower-case words that actually follow a name in
those logs are don't, has, and, once, made, you're, will, thought, fought,
lunges, the, would -- all sentence continuations, none a line of dialogue.

Note what R26 does NOT change. v8.8.8 and v8.8.9 deliberately require
"Poludnitsa delivered something" and "bathildel should retreat immediately" to
resolve a speaker, and those are the same shape. So the speaker still resolves;
only the deletion from the body stops. The name now appears in both places,
which is the conservative reading -- a redundant label is recoverable, a deleted
subject is not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.runtime.prediction_guard import PredictionGuard  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


guard = PredictionGuard.from_env()


def run(line):
    return guard.apply(line, raw_text=line)


# --- narration keeps its subject and gains no speaker ------------------------
NARRATION = [
    ("Nikketa looks at the frame", "Nikketa"),
    ("Balthilde and Dushevnaya sent over a message in secret.", "Balthilde"),
    ("Helen once fought beside her.", "Helen"),
    ("Raizei doesn't know what happened.", "Raizei"),
]
for line, name in NARRATION:
    r = run(line)
    assert_true(name in r.text, f"subject {name!r} was stripped from narration: {r.text!r}")
results["narration_keeps_subject"] = f"PASS ({len(NARRATION)} lines)"

# A misspelled subject must be repaired in the BODY, not only in the label.
for src, want in (("Nlkketa looks at Balthildes battered frame", "Nikketa"),
                  ("bathildel should retreat immediately", "Balthilde")):
    r = run(src)
    assert_true(want in r.text, f"subject not repaired in body: {r.text!r}")
results["misspelled_subject_repaired_in_body"] = "PASS"

# The speaker side is v8.8.8/v8.8.9 territory and must be left intact.
for src, want in (("Poludnitsa delivered something", "Poludnitsa"),
                  ("bathildel should retreat immediately", "Balthilde")):
    assert_true(run(src).speaker == want, f"speaker resolution regressed for {src!r}")
results["speaker_resolution_preserved"] = "PASS"

# --- speaker labels must keep working; that is the feature being protected ---
SPEAKERS = [
    ("Helen We should move now.", "Helen", "We should move now."),
    ("Mangi Security Team Leader Requesting backup", "Mangi Security Team Leader", "Requesting backup"),
]
for line, want_speaker, want_body in SPEAKERS:
    r = run(line)
    assert_true(r.speaker == want_speaker, f"speaker lost: {r.speaker!r} != {want_speaker!r}")
    assert_true(r.text.strip() == want_body, f"body wrong: {r.text!r} != {want_body!r}")
results["speaker_labels_unchanged"] = f"PASS ({len(SPEAKERS)} lines)"

# --- the discriminator itself ------------------------------------------------
# An explicit separator means a label whatever follows it, so a lower-case
# utterance after a colon is not mistaken for narration.
assert_true(
    not guard._is_narration_subject("Helen: we should move", "Helen"),
    "explicit separator was read as narration",
)
assert_true(
    guard._is_narration_subject("Helen once fought beside her.", "Helen"),
    "lower-case continuation was not read as narration",
)
assert_true(
    not guard._is_narration_subject("Helen We should move", "Helen"),
    "capitalised utterance was read as narration",
)
# Nothing after the name at all is a bare label, not a subject.
assert_true(
    not guard._is_narration_subject("Helen", "Helen"),
    "a bare name was read as narration",
)
results["discriminator"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
