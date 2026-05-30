from __future__ import annotations

import re
from typing import Iterable

try:
    from app.translation.idn_terminology import apply_terminology_consistency, preserve_game_terms
except Exception:  # pragma: no cover - runtime fallback when app package is unavailable
    def preserve_game_terms(source: str, output: str) -> str:
        return output
    def apply_terminology_consistency(source: str, output: str, *, mode: str = "balanced", tags: Iterable[str] | None = None) -> str:
        return output

# v8.6: IDN Quality Layer is now a shared layer for Fast IDN, Lite IDN, and Normal IDN.
# It remains deterministic/offline so it is safe for live translation.  The layer avoids
# hallucinating missing text; it only normalizes wording, punctuation, pronouns, and game terms.

_MODE_ALIASES = {
    "0": "off", "none": "off", "raw": "off",
    "lite": "lite_light", "light": "lite_light", "lite_light": "lite_light", "idn_light": "lite_light",
    "fast_light": "fast_light", "fast_idn_light": "fast_light",
    "lite_balanced": "lite_balanced", "balanced": "balanced", "idn_balanced": "balanced",
    "natural": "natural", "idn_natural": "natural", "dialog": "natural", "story": "natural",
    "quality": "quality", "deep": "quality", "idn_quality": "quality", "lite_quality": "quality",
}

_PUNCT_RULES = [
    (r"\s+([,.;:!?])", r"\1"),
    (r"([,.;:!?])(?=\S)", r"\1 "),
    (r"\s{2,}", " "),
    (r"\.\.\.\s*\.++", "..."),
]

_COMMON_DIALOG_RULES = [
    (r"\baku tidak dapat\b", "aku tidak bisa"),
    (r"\bkau tidak dapat\b", "kau tidak bisa"),
    (r"\bkamu tidak dapat\b", "kau tidak bisa"),
    (r"\bmereka tidak dapat\b", "mereka tidak bisa"),
    (r"\bAku tidak dapat\b", "Aku tidak bisa"),
    (r"\bKamu tidak dapat\b", "Kau tidak bisa"),
    (r"\bSaya\b", "Aku"),
    (r"\bsaya\b", "aku"),
    (r"\banda\b", "kau"),
    (r"\bAnda\b", "Kau"),
    (r"\bkamu akan\b", "kau akan"),
    (r"\bkamu bisa\b", "kau bisa"),
    (r"\bkamu tahu\b", "kau tahu"),
    (r"\bapakah kamu\b", "apa kau"),
    (r"\bapakah kau\b", "apa kau"),
    (r"\bhal itu\b", "itu"),
    (r"\bini adalah\b", "ini"),
    (r"\bitu adalah\b", "itu"),
    (r"\bTidak apa apa\b", "Tidak apa-apa"),
    (r"\btidak apa apa\b", "tidak apa-apa"),
    (r"\bsekarang ini\b", "sekarang"),
]

_BALANCED_RULES = [
    (r"\baku akan melakukan\b", "aku akan lakukan"),
    (r"\baku akan pergi\b", "aku pergi"),
    (r"\bkita akan pergi\b", "kita pergi"),
    (r"\bmelakukan tembakan\b", "menembak"),
    (r"\bmembuat bidikan\b", "membidik"),
    (r"\bsecara manual\b", "manual"),
    (r"\bdengan Aku\b", "denganku"),
    (r"\bdengan aku\b", "denganku"),
    (r"\bdi dalam lab\b", "di lab"),
    (r"\bdi dalam laboratorium\b", "di laboratorium"),
]

_NATURAL_RULES = [
    (r"\bapa yang kamu butuhkan\b", "apa yang kau butuhkan"),
    (r"\bapa yang kau butuhkan\?", "apa yang kau butuhkan?"),
    (r"\baku mempercayaimu\b", "aku percaya padamu"),
    (r"\bpercaya kamu\b", "percaya padamu"),
    (r"\bhampir di sana\b", "hampir sampai"),
    (r"\btidak ada di penglihatan\b", "tidak terlihat"),
    (r"\btidak berada di mana pun terlihat\b", "tidak terlihat di mana pun"),
    (r"\bbersiap untuk mengekstrak\b", "bersiap mengevakuasi"),
]

_QUALITY_RULES = [
    (r"\bdengan seluruh kekuatannya\b", "dengan sekuat tenaga"),
    (r"\baku merasa tanpa berat\b", "aku merasa melayang"),
    (r"\bdi luar laboratorium yang penuh ELID\b", "keluar dari laboratorium yang dipenuhi ELID"),
    (r"\bmenstabilkan sarafku\b", "menenangkan gugupku"),
    (r"\bmenenangkan sarafku\b", "menenangkan gugupku"),
]

_ARTIFACT_RULES = [
    # Conservative cleanup for OCR/translation artifacts often seen in live dialog output.
    (r"\btherel\b", "there!"),
    (r"\bToolatel\b", "Too late!"),
    (r"\blatel\b", "late!"),
    (r"\bCommanderl\b", "Commander!"),
]


def _canonical_mode(mode: str | None) -> str:
    return _MODE_ALIASES.get(str(mode or "lite_balanced").lower(), str(mode or "lite_balanced").lower())


def _apply_rules(text: str, rules: Iterable[tuple[str, str]]) -> str:
    out = text
    for pat, repl in rules:
        out = re.sub(pat, repl, out, flags=re.I)
    return out


def _fix_spacing(text: str) -> str:
    out = str(text or "")
    out = out.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    for pat, repl in _PUNCT_RULES:
        out = re.sub(pat, repl, out)
    out = out.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    return re.sub(r"\s+", " ", out).strip()


def _sentence_case(text: str) -> str:
    out = str(text or "").strip()
    if not out:
        return out
    # Keep all-caps acronyms and labels intact; only capitalize the first alphabetic char.
    for i, ch in enumerate(out):
        if ch.isalpha():
            return out[:i] + ch.upper() + out[i + 1:]
    return out


def _mode_depth(mode: str) -> int:
    if mode in {"off"}: return 0
    if mode in {"fast_light", "lite_light"}: return 1
    if mode in {"lite_balanced", "balanced"}: return 2
    if mode == "natural": return 3
    if mode == "quality": return 4
    return 2


def apply_idn_quality(source: str, translation: str, mode: str = "lite_balanced", tags: Iterable[str] | None = None) -> str:
    """Apply deterministic Indonesian quality cleanup for live game translation.

    Modes:
    - off/raw: no changes
    - fast_light: minimal Fast IDN cleanup, very low latency
    - lite_light: punctuation + safe pronouns/terms
    - lite_balanced/balanced: stronger dialog smoothing
    - natural: story/dialog style polish
    - quality/deep: highest deterministic polish, still offline and conservative
    """
    mode_c = _canonical_mode(mode)
    if mode_c == "off":
        return str(translation or "")
    out = str(translation or "").strip()
    if not out:
        return out
    src = str(source or "")
    tags_l = {str(t).lower() for t in (tags or [])}

    out = _fix_spacing(out)
    out = preserve_game_terms(src, out)
    depth = _mode_depth(mode_c)

    # Keep Fast IDN light.  It should not run deep phrasing rules in live loop.
    if depth >= 1:
        out = _apply_rules(out, _COMMON_DIALOG_RULES)
    if depth >= 2:
        out = _apply_rules(out, _BALANCED_RULES)
    if depth >= 3:
        out = _apply_rules(out, _NATURAL_RULES)
    if depth >= 4:
        out = _apply_rules(out, _QUALITY_RULES)

    # Only apply artifact cleanup in IDN contexts or quality modes, so Normal non-IDN output is not over-edited.
    if depth >= 2 or any("idn" in t for t in tags_l):
        out = _apply_rules(out, _ARTIFACT_RULES)

    out = apply_terminology_consistency(src, out, mode=mode_c, tags=tags_l)
    out = _fix_spacing(out)
    return _sentence_case(out)


def idn_quality_mode_for_model(model_key: str = "", group: str = "", level: int = 2, fast_path: bool = False, lite_enabled: bool = False) -> str:
    """Shared v8.6 mapping used by strategy/tests/documentation."""
    key = str(model_key or "").lower()
    grp = str(group or "").lower()
    try:
        lvl = int(level)
    except Exception:
        lvl = 2
    if fast_path or key == "fast_idn":
        return "fast_light" if key == "fast_idn" else "off"
    if "idn" not in grp and "idn" not in key:
        return "off"
    if lite_enabled or "lite" in grp:
        return {1: "lite_light", 2: "lite_balanced", 3: "balanced", 4: "natural", 5: "quality"}.get(lvl, "lite_balanced")
    return {1: "lite_light", 2: "balanced", 3: "natural", 4: "natural", 5: "quality"}.get(lvl, "balanced")
