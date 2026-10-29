from __future__ import annotations
import os
import re
from difflib import SequenceMatcher

try:
    from app.ocr.number_guard import normalize_numeric_ocr, strip_numeric_ui_noise, should_reject_numeric_noise
except Exception:  # keep module standalone-safe
    def normalize_numeric_ocr(text: str) -> str: return str(text or "")
    def strip_numeric_ui_noise(text: str) -> str: return str(text or "")
    def should_reject_numeric_noise(text: str): return (False, "unavailable")

# v8.4.5: conservative OCR cleanup for wide dialog boxes + number-safe guard.
# Keep semantic text, remove high-confidence UI/noise fragments, and normalize common
# game/story OCR artifacts. This lets users snip the full GFL2 dialog box without
# forcing a risky tight crop that may miss long lines.
REPLACEMENTS = {
    "thelr": "their",
    "sllence": "silence",
    "volce": "voice",
    "contalner": "container",
    "balthllde": "Balthilde",
    "mtry": "try",
    "worrled": "worried",
    "equlpment": "equipment",
    "mlight": "might",
    "revlval": "revival",
    "cautlon": "caution",
    "qulet": "quiet",
    "paradeus'": "Paradeus",
    "helen's": "Helen",
    "helens": "Helen",
    "lentlne": "Lentine",
    "ralzei": "Raizei",
    "ralizei": "Raizei",
    "raizel": "Raizei",
    "vaymastina": "Voymastina",
    "voymastlna": "Voymastina",
    "voymastiha": "Voymastina",
    "ralzel": "Raizei",
    "ralzei": "Raizei",
    "orphelwnes": "Orphelune's",
    "qrphelune": "Orphelune",
    "colphne": "Colphne",
    "alvaand": "Alva and",
    "allare": "All are",
    "allthe": "All the",
    "wellfind": "We'll find",
    "whoare": "Who are",
    "girlin": "girl in",
    "onour": "On our",
    "ofcour": "Of cour",
    "ifide": "If I de",
    "canac": "can ac",
    "autopia": "A utopia",
    "feelas": "feel as",
    "thearmor": "The armor",
    "leftarm": "left arm",
    "pistoland": "pistol and",
    "don'tintend": "don't intend",
    "dontintend": "don't intend",
    "tryto": "try to",
    "lshoula": "I should",
    "fshoul": "I should",
    "experiemce": "experience",
    "fefuse": "refuse",
    "wantto": "want to",
    "jetjou": "yet you",
    "kouantfo": "you want to",
    "yov": "you",
    "seem": "seen",
    "mothawe": "not have",
    "wayh": "way",
    "sweettime": "sweet time",
    "youii": "you'll",
    "willeventually": "will eventually",
    "ifthe": "If the",
    "ifwe": "If we",
    "ifit": "If it",
    "if计": "If it",
    "if讦": "If it",
    "讦f": "if",
    "讦": "if",
    "计": "it",
    "川": "I",
    "permissionS": "permissions",
    "isnt": "isn't",
    "cant": "can't",
    "wont": "won't",
    "wouldnt": "wouldn't",
    "shouldnt": "shouldn't",
    "doesnt": "doesn't",
    "didnt": "didn't",
    # v8.7.1 observed GFL2 IDN log joins; conservative exact-token repairs.
    "dontworry": "don't worry",
    "hereyes": "her eyes",
    "tillthe": "till the",
    "beingable": "being able",
    "asimple": "a simple",
    "betterto": "better to",
    "foreven": "for even",
    "ksvkand": "KSVK and",
    "dandellon": "Dandelion",
    # v8.7.2 high-confidence GFL2 story word-boundary/letter repairs.
    "ifshe": "If she",
    "isan": "is an",
    "ofthe": "of the",
    "ofit": "of it",
    "iike": "like",
    "apologles": "apologies",
    "recelved": "received",
    "ksvkis": "KSVK is",
}

# ORT v9.0.7 R25 -----------------------------------------------------------
# The three filters below were removing dialogue, not noise.
#
# LEADING_NOISE had no boundary after the glyph run, so it ate the first letter
# of ordinary words: "Move to grid" -> "ove to grid", "We lost 42" -> "e lost
# 42", "I saw 416" -> "saw 416". Requiring the run to be followed by whitespace
# or end-of-string keeps every real word intact, because in "Move" the M is
# followed by a letter. Single "I" and "A" are then excluded by name -- they are
# the two English words that are also single letters.
LEADING_NOISE = re.compile(
    r"^(?!(?:I|A)(?:\s|$))(?:[川州比讦让舒岛从小几叭贸]|I{1,4}|l{1,4}|\|{1,4}|1{1,4}"
    r"|J{1,3}|M{1,2}|U{1,2}|W{1,2}|m{1,2}|n{1,2}|\?\?)+(?=\s|$)\s*"
)

# Weapon codenames are the GFL cast: 416, HK416, UMP45, AK-12, M4A1, G11,
# WA2000, DSR-50, PPK, KSVK. Structurally they look exactly like the HUD junk
# the filters hunt -- capitals and digits, often no vowel -- so they were being
# deleted as noise. They are protected by shape here, and glyph repair skips
# them too: "M4A1" must never become "M4Al".
# Mixed letters+digits is unambiguous enough to protect by shape alone.
CODE_TOKEN = re.compile(r"^[A-Z]{1,4}[-\s]?\d{1,4}[A-Z]{0,2}\d{0,2}$")

# All-digit and all-letter codenames are NOT separable from HUD by shape: "416"
# is a T-Doll, "153" is a level readout, and nothing about the token says which.
# Those need to be named. Anything not on this list keeps the old treatment, so
# adding a name can only ever recover text, never delete it.
CODE_NAMES = {
    "416", "9A91", "40", "45", "12", "11",
    "PPK", "KSVK", "SOP", "SOPMOD", "MDR", "MG", "SMG", "AR", "RF", "HG", "SG",
    "M4", "M16", "G11", "G36", "P7", "P90", "PP", "AK", "UMP", "HK", "DSR",
    "WA", "OTs", "ST", "DP", "TS", "IDW", "NTW", "FAL", "SAT", "CMS", "RO",
}


def _is_code_name(clean: str) -> bool:
    if not clean:
        return False
    if CODE_TOKEN.match(clean):
        return True
    return clean.upper() in CODE_NAMES
MULTI_PUNCT = re.compile(r"([!?.,;:])\1{2,}")
BROKEN_WORD_JOIN = re.compile(r"\b([A-Za-z])\s+([,.;:!?])")
# Glyph soup that cannot be anything but an artifact -- safe to remove wherever
# it appears, because no dialogue contains it.
TRAILING_UI_NOISE = re.compile(
    r"(?:\s+|^)(?:"
    r"LT(?:S|F)[A-Z0-9]{2,}|LTS[IL1]{2,}\d?|SILJLI|JLI|LLI|MJL|OSLU\w*|"
    r"T[I1l|]{2,}\d*|[+;:\-]*I?ZJ?L|[~`@#$%^*_+=]{2,}|[川州比让舒岛叭贸]{1,}\w*"
    r")(?=\s|$)",
    re.I,
)

# R25: the numeric shapes below used to live in the pattern above and ran
# anywhere in the line, so `[A-Z]{0,3}\d{2,}[A-Z0-9]{0,4}` deleted every
# standalone two-digit number it met -- "in 15 minutes" became "in minutes",
# "Coordinates are 3387 by 9021" became "Coordinates are by". They are real HUD
# shapes, but only at a line edge; in the middle of a sentence a number is what
# the character just said. Note the lookahead still requires whitespace or end,
# so a sentence-final "grid 4512." keeps its number -- the full stop breaks the
# match, which is exactly the wanted behaviour.
EDGE_NUMERIC_SHAPE = re.compile(
    r"^(?:\d{2,}[,\.][A-Z]+|\d{1,3}[+xX×]\d{3,}"
    r"|[0-9Il|]{2,}[+;:_\-][0-9A-ZIl|]{2,}|\d{5,}|[A-Z]{0,3}\d{2,}[A-Z0-9]{0,4})$",
    re.I,
)
SHORT_NOISE_TOKEN = re.compile(r"^(?:[A-Z]*\d+[A-Z0-9,.;:!\-]*|[A-Z]{2,6}|[Il1|]{2,}|[~`@#$%^*_+=;:,.-]+)$")


def _is_noise_token(raw: str, clean: str) -> bool:
    if not clean:
        return False
    if _is_code_name(clean):
        return False
    # A token carrying sentence punctuation is part of the sentence: "sector 7."
    # ends a line of dialogue, a HUD counter never does.
    if raw.rstrip("\"')]}").endswith((".", "!", "?", ",", ";", ":")):
        return False
    if SHORT_NOISE_TOKEN.match(clean) and not re.search(r"[aeiouAEIOU]", clean):
        return True
    if len(clean) <= 2 and re.search(r"\d|[川州比让舒岛叭贸]", clean):
        return True
    if EDGE_NUMERIC_SHAPE.match(clean):
        return True
    return False


def _strip_noise_tokens(s: str) -> str:
    """Remove HUD fragments without removing dialogue.

    ORT v9.0.7 R25. This used to test every token in the line, which deleted
    content wherever content happened to look like a HUD fragment: "in 15
    minutes" -> "in minutes", "sector 7" -> "sector", "Only 5 of the 20
    returned" -> "Only of the returned". Measured across the user's own logs,
    6% of real dialogue lines came out damaged, and of fourteen hand-built
    codename and coordinate lines, thirteen lost content.

    The distinction the old code was missing is positional. Level counters,
    timers and footer artifacts sit at the EDGES of a captured line -- that is
    why the regex above is called TRAILING_UI_NOISE. Numbers and codenames that
    belong to the dialogue sit BETWEEN words. So the edges are eaten greedily
    and the interior is left alone, which keeps the original purpose while
    ending the content loss.
    """
    if not s:
        return s
    s = TRAILING_UI_NOISE.sub(" ", s)
    toks = s.split()
    if not toks:
        return ""

    def noisy(tok):
        return _is_noise_token(tok, tok.strip("\"'()[]{}<>.,;:!?-–—"))

    start = 0
    while start < len(toks) and noisy(toks[start]):
        start += 1
    end = len(toks)
    while end > start and noisy(toks[end - 1]):
        end -= 1
    return " ".join(toks[start:end])


_ORDINAL_SUFFIX = re.compile(r"^1(?:st|nd|rd|th)\b", re.I)


def repair_confusable_glyphs(text: str) -> str:
    """Undo the glyph substitutions the detector makes on thin characters.

    ORT v9.0.7 R25. 1, I and l share a vertical stroke; 5/s and 0/o share an
    outline. Counted over the user's own logs, in lines that reached the
    translator:

        1 + lowercase   ("1can flank")        48
        lowercase + 5   ("It5 possible")      35
        1 + Capital     ("1Ve started")       12
        0 between letters ("l0a0 qulckly")     6
        1 + apostrophe  ("1've never")          4
        l + Capital     ("lWas my fault")       1

    Each rule below is anchored so it can only fire where a digit sits in a
    position a digit cannot legitimately occupy -- fused to lowercase letters.
    A number standing on its own is never touched, ordinals like "1st" are
    excluded by name, and any token shaped like a weapon codename is skipped
    outright, so UMP45, M4A1 and HK416 come through unchanged.
    """
    if not text or not re.search(r"[015l]", text):
        return text

    out = []
    for tok in re.split(r"(\s+)", str(text)):
        if not tok.strip():
            out.append(tok)
            continue
        core = tok.strip("\"'()[]{}<>.,;:!?-–—")
        # Codenames and plain numbers are content; never rewrite their glyphs.
        if _is_code_name(core) or re.fullmatch(r"[\d.,]+", core) or _ORDINAL_SUFFIX.match(core):
            out.append(tok)
            continue
        t = tok
        # "1've" -> "I've"
        t = re.sub(r"(?<![\w])1(?=')", "I", t)
        # "1can" -> "I can"  /  "1Ve" -> "I Ve"
        t = re.sub(r"(?<![\w])1(?=[a-z]{2,})", "I ", t)
        t = re.sub(r"(?<![\w])1(?=[A-Z][a-z])", "I ", t)
        # "lWas" -> "I Was"
        t = re.sub(r"(?<![\w])l(?=[A-Z][a-z])", "I ", t)
        # "It5" -> "Its"; only at the end of an otherwise alphabetic word.
        t = re.sub(r"(?<=[a-z])5\b", "s", t)
        # "d0es" -> "does"; only with a letter on both sides.
        t = re.sub(r"(?<=[a-z])0(?=[a-z])", "o", t)
        out.append(t)
    return "".join(out)


def normalize_ocr_noise(text: str) -> str:
    s = str(text or "")
    # v8.7: remove fixed GFL footer/UI artifacts before any name/cache logic sees them.
    try:
        if os.environ.get("ORT_GFL_ARTIFACT_FILTER", "0") == "1":
            from app.games.gfl_profile import normalize_gfl_text
            s = normalize_gfl_text(s)
    except Exception:
        pass
    s = s.replace("。", ".").replace("，", ",").replace("：", ":")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = re.sub(r"[\u200b\ufeff]", "", s)
    s = LEADING_NOISE.sub("", s).strip()
    # Before the token filters, so a repaired "1can" is judged as "I can".
    if os.environ.get("ORT_GLYPH_REPAIR", "1") == "1":
        s = repair_confusable_glyphs(s)
    s = normalize_numeric_ocr(s)
    s = strip_numeric_ui_noise(s)
    s = _strip_noise_tokens(s)
    for k, v in REPLACEMENTS.items():
        s = re.sub(rf"\b{re.escape(k)}\b", v, s, flags=re.I)
    # Text-only fallback for observed joined first-person forms.  Visual confirmation
    # for standalone missing I is handled by the GFL2 thin-glyph ROI pass.
    s = re.sub(r"(?i)(^|[.!?]\s+|\b(?:DP-12|KSVK)\s+)iam\b", r"\1I am", s)
    s = re.sub(r"(?i)(^|[.!?]\s+|\b(?:DP-12|KSVK)\s+)irefuse\b", r"\1I refuse", s)
    s = re.sub(r"\b([A-Za-z])\s+(?=[A-Za-z]\b)", r"\1", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = BROKEN_WORD_JOIN.sub(r"\1\2", s)
    s = MULTI_PUNCT.sub(r"\1\1", s)
    try:
        from app.translation.name_alias_normalizer import apply_name_aliases
        s = apply_name_aliases(s, os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "")))
    except Exception:
        pass
    try:
        if os.environ.get("ORT_GFL_ARTIFACT_FILTER", "0") == "1":
            from app.games.gfl_profile import normalize_gfl_text
            s = normalize_gfl_text(s)
    except Exception:
        pass
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def fuzzy_cache_key(text: str) -> str:
    s = normalize_ocr_noise(text).lower()
    s = re.sub(r"^[^a-z0-9]+", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def looks_ocr_noisy(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return False
    if LEADING_NOISE.search(s) or TRAILING_UI_NOISE.search(s):
        return True
    if re.search(r"\b(?:thelr|sllence|volce|contalner|equlpment|cautlon|qulet|experiemce|fefuse)\b", s, flags=re.I):
        return True
    letters = re.findall(r"[A-Za-z]", s)
    weird = len(re.findall(r"[|川州讦让舒岛叭贸~`@#$%^*_+=]", s))
    digits = len(re.findall(r"\d", s))
    if letters and (weird + digits * 0.6) / max(1, len(letters)) > 0.18:
        return True
    return False


def should_reject_ocr_text(text: str) -> tuple[bool, str]:
    """Reject only obvious UI/noise fragments before translation/cache/learning."""
    s = str(text or "").strip()
    if not s:
        return True, "empty"
    letters = re.findall(r"[A-Za-z]", s)
    if len(letters) < 2:
        return True, "too_few_letters"
    num_reject, num_reason = should_reject_numeric_noise(s)
    if num_reject:
        return True, num_reason
    if len(s) <= 8 and looks_ocr_noisy(s):
        return True, "short_noise"
    # Mostly numeric/UI code lines should not be translated.
    digits = len(re.findall(r"\d", s))
    weird = len(re.findall(r"[川州讦让舒岛叭贸~`@#$%^*_+=|]", s))
    if len(s) <= 24 and (digits + weird) > len(letters):
        return True, "ui_code_noise"
    if len(letters) >= 3 and weird / max(1, len(letters)) > 0.35:
        return True, "symbol_noise_ratio"
    return False, "ok"


def similarity_key(a: str, b: str) -> float:
    return SequenceMatcher(None, fuzzy_cache_key(a), fuzzy_cache_key(b)).ratio()
