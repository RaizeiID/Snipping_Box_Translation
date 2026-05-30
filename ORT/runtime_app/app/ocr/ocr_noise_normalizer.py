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

LEADING_NOISE = re.compile(r"^(?:[川州比讦让舒岛从小几叭贸]|I{1,4}|l{1,4}|\|{1,4}|1{1,4}|J{1,3}|M{1,2}|U{1,2}|W{1,2}|m{1,2}|n{1,2}|\?\?)+\s*")
MULTI_PUNCT = re.compile(r"([!?.,;:])\1{2,}")
BROKEN_WORD_JOIN = re.compile(r"\b([A-Za-z])\s+([,.;:!?])")
TRAILING_UI_NOISE = re.compile(
    r"(?:\s+|^)(?:"
    r"LT(?:S|F)[A-Z0-9]{2,}|LTS[IL1]{2,}\d?|SILJLI|JLI|LLI|MJL|OSLU\w*|"
    r"\d{2,}[,\.][A-Z]+|\d{1,3}[+xX×]\d{3,}|[0-9Il|]{2,}[+;:_\-][0-9A-ZIl|]{2,}|\d{5,}|[A-Z]{0,3}\d{2,}[A-Z0-9]{0,4}|"
    r"T[I1l|]{2,}\d*|[+;:\-]*I?ZJ?L|[~`@#$%^*_+=]{2,}|[川州比让舒岛叭贸]{1,}\w*"
    r")(?=\s|$)",
    re.I,
)
SHORT_NOISE_TOKEN = re.compile(r"^(?:[A-Z]*\d+[A-Z0-9,.;:!\-]*|[A-Z]{2,6}|[Il1|]{2,}|[~`@#$%^*_+=;:,.-]+)$")


def _strip_noise_tokens(s: str) -> str:
    if not s:
        return s
    s = TRAILING_UI_NOISE.sub(" ", s)
    toks = []
    for tok in s.split():
        raw = tok.strip()
        clean = raw.strip("\"'()[]{}<>.,;:!?-–—")
        # Keep short real words like no/ok/go; drop UI-like fragments.
        if clean and SHORT_NOISE_TOKEN.match(clean) and not re.search(r"[aeiouAEIOU]", clean):
            continue
        if len(clean) <= 2 and re.search(r"\d|[川州比让舒岛叭贸]", clean):
            continue
        toks.append(raw)
    return " ".join(toks)


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
