from __future__ import annotations

"""Number-safe OCR and translation helpers for ORT v8.5.1.

The OCR engine can confuse digits with similar glyphs (I/l/|/1, O/0, S/5),
especially inside wide visual-novel dialog boxes.  These helpers are purposely
rule-based and conservative: they correct high-confidence numeric contexts,
reject obvious UI numeric garbage, and preserve numeric tokens after translation.
"""

from dataclasses import dataclass
import re
from typing import List, Tuple

NUM_UNIT_RE = re.compile(
    r"(?i)\b(?:\d+(?:[\.,]\d+)?|[Il|](?:[\.,]\d+)|\d+[Oo]\d?)\s*"
    r"(?:m|meter|meters|cm|mm|km|degrees?|deg|°|percent|%|o'clock)?\b"
)
NOISE_NUM_TOKEN_RE = re.compile(
    r"(?i)^(?:[0-9Il|]{2,}[+;:_\-,][0-9A-ZIl|]{1,}|[+;:_\-]*[0-9Il|]{5,}[A-Z0-9Il|]*|[A-Z]{0,4}\d{2,}[A-Z]{1,4}|[TIl|]{3,}\d*)$"
)
MEANINGFUL_UNIT_RE = re.compile(r"(?i)\b(?:meter|meters|cm|mm|km|degree|degrees|deg|°|percent|%)\b")

_DIGIT_WORD_CONTEXT = re.compile(
    r"(?i)\b(?:meter|meters|cm|mm|km|degree|degrees|deg|°|percent|o'clock|clock|floor|level|phase|type|unit|units|elid|elids|enemy|enemies)\b"
)

@dataclass
class NumberProtection:
    source: str
    protected: str
    numbers: List[str]
    placeholders: List[str]


def normalize_numeric_ocr(text: str) -> str:
    """Normalize high-confidence digit OCR confusions without changing prose."""
    s = str(text or "")
    if not s:
        return s

    # Decimal-leading OCR confusions: I.5 / l,5 / |.5 -> 1.5
    s = re.sub(r"\b[Il|][\.,](\d+)\b", r"1.\1", s)
    # 18O degrees / 18O deg -> 180 degrees (O between digits/unit)
    s = re.sub(r"\b(\d+)[Oo](?=\s*(?:degrees?|deg|°)\b)", r"\g<1>0", s, flags=re.I)
    # Digits adjacent to common OCR glyph confusions.
    s = re.sub(r"(?<=\d)[Oo](?=\d)", "0", s)
    s = re.sub(r"(?<=\d)[Il|](?=\d)", "1", s)
    s = re.sub(r"(?<=\d)[Ss](?=\d)", "5", s)
    s = re.sub(r"(?<=\d)[Zz](?=\d)", "2", s)
    # Decimal comma in numeric contexts -> dot for consistency.
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    # Unit spacing cleanup: 1 . 5 meters -> 1.5 meters; 180degrees -> 180 degrees.
    s = re.sub(r"\b(\d+)\s*\.\s*(\d+)\b", r"\1.\2", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)(?=(?:m|cm|mm|km|degrees?|deg|°|percent|%)\b)", r"\1 ", s, flags=re.I)
    # Common digit/letter join near measurement prose.
    s = re.sub(r"(?i)\b(l|I|\|)(?=\d\s*(?:m|cm|mm|km|degrees?|deg|°)\b)", "1", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def extract_numbers(text: str) -> List[str]:
    s = normalize_numeric_ocr(text)
    out: List[str] = []
    # Include units when present so translations can restore full measurement.
    for m in re.finditer(r"(?i)\b\d+(?:\.\d+)?(?:\s*(?:m|meter|meters|cm|mm|km|degrees?|deg|°|percent|%|o'clock))?\b", s):
        token = re.sub(r"\s+", " ", m.group(0).strip())
        if token and token not in out:
            out.append(token)
    return out


def strip_numeric_ui_noise(text: str) -> str:
    """Remove obvious trailing numeric UI garbage while preserving measurements."""
    s = str(text or "")
    if not s:
        return s
    # Remove trailing UI fragments only when they look like codes and not measurements.
    toks = []
    for tok in s.split():
        clean = tok.strip("\"'()[]{}<>.,;:!?–—")
        if NOISE_NUM_TOKEN_RE.match(clean) and not MEANINGFUL_UNIT_RE.search(s):
            continue
        toks.append(tok)
    s = " ".join(toks)
    # Leading UI index artifacts, but do not remove meaningful line numbers followed by units.
    s = re.sub(r"^\s*(?:\d+\]|\d+\)|\d+\||\[\d+\])\s*", "", s).strip()
    return re.sub(r"\s{2,}", " ", s).strip()


def should_reject_numeric_noise(text: str) -> Tuple[bool, str]:
    s = str(text or "").strip()
    if not s:
        return True, "empty"
    words = re.findall(r"[A-Za-z]{2,}", s)
    nums = re.findall(r"\d", s)
    weird = re.findall(r"[+;:_=~`@#$%^*|川州讦让舒岛叭贸]", s)
    if len(s) <= 32 and nums and not _DIGIT_WORD_CONTEXT.search(s) and len(nums) + len(weird) > max(2, len(''.join(words))):
        return True, "numeric_ui_noise"
    if len(s) <= 18 and NOISE_NUM_TOKEN_RE.match(s.strip(" .,;:!?")):
        return True, "numeric_code_fragment"
    return False, "ok"


def protect_numbers(text: str) -> NumberProtection:
    src = normalize_numeric_ocr(text)
    numbers = extract_numbers(src)
    protected = src
    placeholders: List[str] = []
    for idx, num in enumerate(numbers):
        ph = f"__ORTNUM{idx}__"
        placeholders.append(ph)
        protected = re.sub(rf"(?<!\w){re.escape(num)}(?!\w)", ph, protected, count=1)
    return NumberProtection(source=src, protected=protected, numbers=numbers, placeholders=placeholders)


def restore_numbers(protection: NumberProtection | str, output: str) -> str:
    if isinstance(protection, str):
        protection = protect_numbers(protection)
    out = str(output or "")
    if not out or not protection.numbers:
        return out
    for ph, num in zip(protection.placeholders, protection.numbers):
        # Restore several likely translations/corruptions of the placeholder.
        variants = [ph, ph.lower(), ph.replace("__", ""), ph.replace("_", " ")]
        restored = False
        for v in variants:
            if v in out:
                out = out.replace(v, num)
                restored = True
        if not restored:
            # If translation dropped the number entirely, append it conservatively.
            normalized_out = normalize_numeric_ocr(out)
            if num not in normalized_out and not re.search(rf"(?<!\d){re.escape(num.split()[0])}(?!\d)", normalized_out):
                out = f"{out} ({num})".strip()
    return re.sub(r"\s{2,}", " ", out).strip()


def number_quality_hint(text: str) -> str:
    reject, reason = should_reject_numeric_noise(text)
    if reject:
        return reason
    nums = extract_numbers(text)
    if nums:
        return "number_safe"
    if re.search(r"[Il|OoSsZz][\.,]?\d|\d[OoIl|SsZz]\d", str(text or "")):
        return "possible_digit_confusion"
    return "none"


# =============================================================================
# v8.5 Numeric Dual-Pass helpers
# =============================================================================
NUMERIC_TRIGGER_RE = re.compile(
    r"(?i)\b(?:bearing|elevation|vertical|angle|degrees?|deg|distance|meters?|metres?|platform|front|left|right|below|above|ascend|descend|enemy|enemies|elids?|unit|units|coordinate|coordinates|targeting|range)\b"
)
_DEGREE_GAP_RE = re.compile(r"(?i)(?<!\d\s)(?:bearing\s+)?(?:elevation|vertical\s+angle|angle)\s+degrees?\b")
_DISTANCE_GAP_RE = re.compile(r"(?i)(?<!\d\s)distance\s+(?:meters?|metres?)\b")
_ANOTHER_METERS_GAP_RE = re.compile(r"(?i)\banother\s+(?:meters?|metres?)\b")
_NUMBER_TOKEN_RE = re.compile(r"(?<!\w)(?:\d{1,4}(?:[\.,]\d{1,2})?|[Il|][\.,]\d{1,2}|\d+[Oo](?=\s*(?:degrees?|deg|°)))(?!\w)")


def has_numeric_context(text: str) -> bool:
    return bool(NUMERIC_TRIGGER_RE.search(str(text or "")))


def has_meaningful_number(text: str) -> bool:
    s = normalize_numeric_ocr(text)
    return bool(_NUMBER_TOKEN_RE.search(s))


def needs_numeric_dual_pass(text: str) -> Tuple[bool, str]:
    """Return True when OCR text looks like it should contain numbers but does not.

    This deliberately does not invent numbers. It only asks the OCR worker to run
    a digit-focused second pass on the same frame.
    """
    s = normalize_numeric_ocr(text)
    if not s or not has_numeric_context(s):
        return False, "no_numeric_context"
    if should_reject_numeric_noise(s)[0]:
        return False, "numeric_noise"
    if has_meaningful_number(s):
        return False, "number_present"
    if _DEGREE_GAP_RE.search(s):
        return True, "missing_degree_value"
    if _DISTANCE_GAP_RE.search(s):
        return True, "missing_distance_value"
    if _ANOTHER_METERS_GAP_RE.search(s):
        return True, "missing_meter_value"
    # Broad tactical line: has multiple numeric cues but no digit at all.
    cues = len(NUMERIC_TRIGGER_RE.findall(s))
    if cues >= 2 and re.search(r"(?i)\b(?:degrees?|meters?|distance|bearing|angle)\b", s):
        return True, "missing_numeric_tactical_value"
    return False, "no_gap"



def _token_has_ui_noise(token: str) -> bool:
    t = str(token or "").strip()
    if not t:
        return True
    # Progress counters / subtitle timer fragments frequently appear in GFL2 wide dialog captures.
    if re.search(r"[:/;]", t):
        return True
    if re.search(r"\d+[+\-]\d+", t):
        return True
    if len(re.sub(r"\D", "", t)) >= 4 and not re.search(r"\.\d", t):
        return True
    return False


def clean_numeric_candidate(token: str, reason: str = "") -> str:
    """Return a conservative numeric candidate or empty string.

    v8.5.1 intentionally rejects ambiguous long UI-like candidates.  If a real
    digit cannot be read with confidence, the system leaves the line marked as a
    known OCR limitation instead of injecting wrong values.
    """
    raw = str(token or "")
    if _token_has_ui_noise(raw):
        return ""
    t = normalize_numeric_ocr(raw)
    t = t.strip().strip("[]{}()<>|:;,+*#@~`'")
    t = t.replace("O", "0").replace("o", "0")
    t = re.sub(r"(?<=\d)[Il|](?=\d)", "1", t)
    t = re.sub(r"(?<=\d)[Ss](?=\d)", "5", t)
    t = re.sub(r"(?<=\d)[Zz](?=\d)", "2", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"[^0-9.\-+]", "", t)
    if not re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{1,2})?", t):
        return ""
    try:
        value = float(t)
    except Exception:
        return ""
    reason_l = (reason or "").lower()
    # Tactical sanity ranges.  These ranges are deliberately broad enough for
    # game callouts but narrow enough to reject UI/progress fragments.
    if "degree" in reason_l or "bearing" in reason_l or "angle" in reason_l or "tactical" in reason_l:
        if not (-90.0 <= value <= 360.0):
            return ""
        # Single noisy 8/1 candidates are too ambiguous for missing degree values.
        if abs(value) in {1.0, 2.0, 8.0} and ("degree" in reason_l or "angle" in reason_l):
            return ""
    if "meter" in reason_l or "distance" in reason_l:
        if not (0.5 <= value <= 999.0):
            return ""
        if abs(value) in {1.0, 2.0, 8.0} and "another" not in reason_l:
            return ""
    # Reject values that still look like OCR/UI fragments from known logs.
    if re.fullmatch(r"8(?:2|21|261|461|861|881)", t):
        return ""
    return t


def clean_numeric_candidates(tokens: List[str], reason: str = "") -> List[str]:
    out: List[str] = []
    for tok in tokens or []:
        c = clean_numeric_candidate(tok, reason=reason)
        if c and c not in out:
            out.append(c)
    # v8.5.1: do not over-merge multiple candidates into a single text line.
    # Degree+distance may accept two values, otherwise one is enough.
    limit = 2 if re.search(r"(?i)degree|distance|meter|tactical", reason or "") else 1
    return out[:limit]


def merge_numeric_candidates_into_text(text: str, candidates: List[str]) -> Tuple[str, str]:
    """Inject digit candidates only when they pass semantic validation.

    v8.5.1 policy: wrong numbers are worse than missing numbers.  If candidates
    look like UI/progress noise, keep the original OCR and report a limitation.
    """
    s = normalize_numeric_ocr(text)
    need, reason = needs_numeric_dual_pass(s)
    cands = clean_numeric_candidates(candidates, reason=reason)
    if not need:
        return s, "no_gap"
    if not cands:
        return s, f"known_limitation:{reason}:no_valid_numeric_candidate"

    idx = 0
    changed = False

    def next_num() -> str:
        nonlocal idx
        if idx >= len(cands):
            return ""
        val = cands[idx]
        idx += 1
        return val

    def repl_degree(m: re.Match) -> str:
        nonlocal changed
        val = next_num()
        if not val:
            return m.group(0)
        changed = True
        return re.sub(r"(?i)degrees?", f"{val} degrees", m.group(0), count=1)

    def repl_distance(m: re.Match) -> str:
        nonlocal changed
        val = next_num()
        if not val:
            return m.group(0)
        changed = True
        return re.sub(r"(?i)(meters?|metres?)", f"{val} meters", m.group(0), count=1)

    s2 = _DEGREE_GAP_RE.sub(repl_degree, s, count=1)
    s2 = _DISTANCE_GAP_RE.sub(repl_distance, s2, count=1)
    if not changed and _ANOTHER_METERS_GAP_RE.search(s2):
        val = next_num()
        if val:
            s2 = _ANOTHER_METERS_GAP_RE.sub(f"another {val} meters", s2, count=1)
            changed = True

    if not changed:
        return s, f"known_limitation:{reason}:no_safe_merge"
    return re.sub(r"\s{2,}", " ", s2).strip(), f"merged:{reason}:{','.join(cands)}"


def numeric_limitation_hint(text: str) -> str:
    need, reason = needs_numeric_dual_pass(text)
    if need:
        return f"known_ocr_numeric_limitation:{reason}"
    return "none"

def number_gap_hint(text: str) -> str:
    need, reason = needs_numeric_dual_pass(text)
    return reason if need else "none"
