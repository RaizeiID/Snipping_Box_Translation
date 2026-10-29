"""ORT v9.0.7 R25 -- stop the noise filters from eating dialogue.

Reported: OCR skips numbers, skips i/I/l, and skips GFL codenames that are not
words -- 416, UMP45, AK12 -- and drops the numbers when a character reads out
coordinates.

None of that was recognition. Three filters in ocr_noise_normalizer removed the
text after it was read:

  LEADING_NOISE       had no boundary after the glyph run, so it ate the first
                      letter of real words: "Move to grid" -> "ove to grid",
                      "We lost 42" -> "e lost 42".
  TRAILING_UI_NOISE   carried `[A-Z]{0,3}\\d{2,}[A-Z0-9]{0,4}` and ran anywhere
                      in the line, so every standalone 2+ digit number died:
                      "in 15 minutes" -> "in minutes".
  SHORT_NOISE_TOKEN   drops vowel-less alphanumeric tokens, which is the exact
                      shape of a codename: 416, G11, PPK, KSVK, HK416.

Measured on the user's own logs: 4529 of 73763 real lines (6.1%) lost words.
After R25, 326 (0.4%) -- and spot-checking those shows apostrophe normalisation,
not content loss.

The rule R25 adds is positional: HUD artifacts sit at the EDGES of a captured
line, dialogue numbers sit BETWEEN words.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ocr.ocr_noise_normalizer import (  # noqa: E402
    normalize_ocr_noise,
    repair_confusable_glyphs,
)

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


# --- 1. codenames and coordinates must survive verbatim ----------------------
INTACT = [
    "I saw 416 near the checkpoint.",
    "HK416 is waiting for you.",
    "UMP45 and AK12 are on standby.",
    "Send G11 to sector 7.",
    "DSR-50 reported in.",
    "WA2000 has the high ground.",
    "M4A1 leads the squad.",
    "PPK is missing.",
    "KSVK covered the retreat.",
    "416 and UMP45 are ready.",
    "Move to grid 4512 immediately.",
    "Coordinates are 3387 by 9021.",
    "The convoy arrives in 15 minutes.",
    "We lost 42 operatives.",
    "Only 5 of the 20 returned.",
    "Report back at 0600 sharp.",
]
for line in INTACT:
    got = normalize_ocr_noise(line)
    assert_true(got.strip() == line.strip(), f"content lost:\n  in : {line}\n  out: {got}")
results["codenames_and_numbers_intact"] = f"PASS ({len(INTACT)} lines)"

# The first word must never lose its first letter -- that was LEADING_NOISE.
for word in ("Move", "We", "My", "Us", "Nothing", "Just", "It", "Where", "Understood"):
    line = f"{word} is here."
    assert_true(normalize_ocr_noise(line).startswith(word), f"{word!r} lost its first letter")
results["first_word_survives"] = "PASS"

# --- 2. glyph repair, on the patterns actually counted in the logs -----------
GLYPH = {
    "1can flank the enemy.": "I can flank the enemy.",
    "1've never heard that.": "I've never heard that.",
    "lWas my fault.": "I Was my fault.",
    "It5 possible.": "Its possible.",
}
for src, want in GLYPH.items():
    got = normalize_ocr_noise(src)
    assert_true(got == want, f"glyph repair:\n  in : {src}\n  out: {got}\n  want: {want}")
results["glyph_repair"] = f"PASS ({len(GLYPH)} patterns)"

# Repair must never touch a codename or a real number -- that would be a new
# bug traded for the old one.
for token in ("M4A1", "UMP45", "HK416", "416", "AK12", "1.000", "2042", "15", "1st"):
    assert_true(
        repair_confusable_glyphs(token) == token,
        f"glyph repair corrupted {token!r} -> {repair_confusable_glyphs(token)!r}",
    )
results["repair_skips_codes_and_numbers"] = "PASS"

# --- 3. the original purpose still holds -------------------------------------
# HUD junk at the edges must still go, or R25 traded content loss for noise.
NOISY = [
    ("Lv 153 EXP 4200", "4200"),
    ("She looked away SILJLI", "SILJLI"),
    ("Hold the line 3963", "3963"),
]
for line, junk in NOISY:
    got = normalize_ocr_noise(line)
    assert_true(junk not in got, f"edge noise {junk!r} survived in {got!r}")
results["edge_noise_still_stripped"] = "PASS"

# The same token mid-sentence is content, not noise -- this is the whole rule.
mid = normalize_ocr_noise("Hold the line 3963 until dawn.")
assert_true("3963" in mid, f"mid-sentence number was stripped: {mid!r}")
results["position_is_the_rule"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
