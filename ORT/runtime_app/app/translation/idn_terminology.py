from __future__ import annotations

import re
from typing import Iterable

# v8.6: deterministic terminology consistency for live IDN output.
# The module is intentionally offline-only and conservative.  It preserves game names,
# technical terms, and recurring GFL2 terminology without doing broad fuzzy rewriting.

GAME_TERMS = {
    "Commander", "Doll", "Dolls", "ELID", "ELIDs", "Paradeus", "Mangi Security",
    "Conglomerate", "URNC", "Omen", "DP-12", "KCCO", "G&K", "Monsoon", "Varjagers",
    "Groza", "Raizei", "Voymastina", "Alva", "Mayling", "Colphne", "Nemesis",
}

# Indonesian consistency terms.  These are only applied when the corresponding English
# source term appears, so they do not invent context.
SOURCE_TERM_TO_IDN = {
    "visual system": "sistem visual",
    "targeting assistance": "bantuan penargetan",
    "extraction point": "titik ekstraksi",
    "bearing": "arah tembak",
    "elevation": "elevasi",
    "vertical angle": "sudut vertikal",
    "distance": "jarak",
    "meters": "meter",
    "meter": "meter",
    "accuracy": "akurasi",
    "manual": "manual",
    "lab": "lab",
    "laboratory": "laboratorium",
}

_BAD_TERM_TRANSLATIONS = [
    (r"\bkomandan\b", "Commander"),
    (r"\bboneka\b", "Doll"),
    (r"\bboneka-boneka\b", "Dolls"),
    (r"\belid\b", "ELID"),
    (r"\belids\b", "ELIDs"),
]


def _source_has(source: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", source, flags=re.I) is not None


def preserve_game_terms(source: str, output: str) -> str:
    src = str(source or "")
    out = str(output or "")
    if not out:
        return out
    for term in sorted(GAME_TERMS, key=len, reverse=True):
        if _source_has(src, term):
            # restore common lowercase/case-damaged variants in the output
            out = re.sub(rf"\b{re.escape(term.lower())}\b", term, out, flags=re.I)
    for pat, repl in _BAD_TERM_TRANSLATIONS:
        # Only force English game term if that term exists in source.
        if repl.lower() in src.lower():
            out = re.sub(pat, repl, out, flags=re.I)
    return out


def apply_terminology_consistency(source: str, output: str, *, mode: str = "balanced", tags: Iterable[str] | None = None) -> str:
    src = str(source or "")
    out = str(output or "")
    if not out:
        return out
    out = preserve_game_terms(src, out)
    mode_l = str(mode or "balanced").lower()
    # For quality/natural modes, gently normalize Indonesian technical phrasing.
    if mode_l in {"balanced", "lite_balanced", "natural", "quality", "deep", "idn_quality", "idn_natural"}:
        if _source_has(src, "extraction point"):
            out = re.sub(r"\btitik pengambilan\b|\btitik evakuasi\b", "titik ekstraksi", out, flags=re.I)
        if _source_has(src, "targeting assistance"):
            out = re.sub(r"\bbantuan target\b|\bbantuan membidik\b", "bantuan penargetan", out, flags=re.I)
        if _source_has(src, "visual system"):
            out = re.sub(r"\bsistem penglihatan\b", "sistem visual", out, flags=re.I)
        if _source_has(src, "meters") or _source_has(src, "meter"):
            out = re.sub(r"\bmetres\b|\bmeters\b|\bmeter-meter\b", "meter", out, flags=re.I)
    return out


def terminology_report(source: str, output: str) -> dict[str, object]:
    fixed = apply_terminology_consistency(source, output)
    return {"changed": fixed != str(output or ""), "output": fixed}
