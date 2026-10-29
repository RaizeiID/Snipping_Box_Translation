"""ORT v9.0.7 R23 -- digits and the letter "i" must survive to the merged line.

Reported symptom: "ocr sulit membaca angka atau huruf i, sehingga jika bertemu
angka atau huruf i terkadang dilewati."

It was never a recognition problem. EasyOCR returned those boxes; the fast scan
threw them away before merging, in two places that were both written for whole
lines and applied to single boxes:

  * _is_fast_text_ok rejects len < 2 and pure digits -- correct for a line that
    is nothing but "5" (an ammo counter), fatal for the "I" inside a sentence.
  * a flat `w < 22` pixel floor -- reasonable for a word, but "I" and "1" are
    the narrowest glyphs in the font, roughly 6 px at a 20 px line height.

Both ran per box, so the word was gone before the line existed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


# --- the predicates under test, imported without dragging in the whole app ----
SRC = (Path(__file__).resolve().parent.parent / "TITANMAIN.py").read_text(
    encoding="utf-8", errors="replace"
)


def _extract(name: str):
    m = re.search(rf"^def {name}\(.*?(?=^def |\Z)", SRC, re.S | re.M)
    assert_true(m, f"{name} not found in TITANMAIN.py")
    ns: dict = {"re": re}
    exec(m.group(0), ns)
    return ns[name]


is_line_ok = _extract("_is_fast_text_ok")
is_item_ok = _extract("_is_fast_item_ok")

# --- box-level: the characters that went missing ------------------------------
SURVIVORS = ["I", "i", "a", "5", "3", "100", "1999", "12", "!", "A"]
for token in SURVIVORS:
    assert_true(is_item_ok(token), f"box {token!r} was dropped before line merge")
results["boxes_survive"] = f"PASS ({len(SURVIVORS)} tokens)"

# The box gate still has to remove genuinely unusable boxes.
for junk in ["", "   ", "@#$%^*", "~`<>=_@"]:
    assert_true(not is_item_ok(junk), f"unusable box {junk!r} was kept")
results["junk_boxes_rejected"] = "PASS"

# --- line-level: the original intent must be untouched ------------------------
# A line that is only a number is still HUD noise, not dialogue.
for hud in ["5", "100", "1999", "7"]:
    assert_true(not is_line_ok(hud), f"HUD line {hud!r} leaked into dialogue")
for line in ["I have 3 rounds left.", "It is 1999.", "No. I", "OK"]:
    assert_true(is_line_ok(line), f"real line {line!r} was rejected")
results["line_gate_unchanged"] = "PASS"

# --- the reported failure, end to end ----------------------------------------
# Boxes as EasyOCR hands them over: (text, width, height). "I" and "3" are the
# narrow ones that used to be filtered out.
BOXES = [("I", 6, 20), ("have", 48, 20), ("3", 9, 20), ("rounds", 62, 20), ("left.", 40, 20)]
MIN_H = 14


def merge(boxes, *, item_gate, narrow_rule):
    kept = []
    for txt, w, h in boxes:
        if not item_gate(txt):
            continue
        if h < MIN_H:
            continue
        if w < 22 and not narrow_rule(txt, w, h):
            continue
        kept.append(txt)
    return " ".join(kept)


never = lambda txt, w, h: False
r23 = lambda txt, w, h: len(txt) <= 2 and w >= max(3, int(h * 0.18))

old = merge(BOXES, item_gate=is_line_ok, narrow_rule=never)
new = merge(BOXES, item_gate=is_item_ok, narrow_rule=r23)

assert_true(old == "have rounds left.", f"old behaviour not reproduced, got {old!r}")
assert_true(new == "I have 3 rounds left.", f"line still incomplete: {new!r}")
results["reported_symptom"] = {"before": old, "after": new}

# A box that is narrow AND long is still noise -- a 6 px wide "rounds" is a
# detector artefact, so the narrow exemption must not apply to it.
assert_true(not r23("rounds", 6, 20), "narrow exemption leaked to a long token")
# And a zero-width box stays rejected however short its text.
assert_true(not r23("I", 1, 20), "degenerate 1 px box was accepted")
results["narrow_exemption_bounded"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
