from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# v8.6: conservative game/name alias correction for OCR typos.
# This is intentionally small and game-profile aware so it improves recurring GFL2
# speaker/name mistakes without turning arbitrary words into character names.

@dataclass(frozen=True)
class AliasHit:
    raw: str
    fixed: str

_GFL2_ALIASES: dict[str, str] = {
    "Ralzel": "Raizei",
    "Ralzei": "Raizei",
    "Raizel": "Raizei",
    "RaizeI": "Raizei",
    "Rai2ei": "Raizei",
    "RalzeI": "Raizei",
    "Voymastlna": "Voymastina",
    "VoymastIna": "Voymastina",
    "Voymastiha": "Voymastina",
    "Vaymastina": "Voymastina",
    "Vaymastlna": "Voymastina",
    "Vaymastin": "Voymastina",
    "Voymastin": "Voymastina",
    "AIVa": "Alva",
    "AIva": "Alva",
    "AlVa": "Alva",
    "Aiva": "Alva",
    "Gro2a": "Groza",
    # v8.7.1 GFL2: keep hyphen/digits and restore observed canonical names.
    "Dp-12": "DP-12",
    "dp-12": "DP-12",
    "DP-I2": "DP-12",
    "Dandellon": "Dandelion",
    # v8.7.3 speaker-slot/known entity corrections. These never merge Helen and Helena.
    "elanie": "Melanie",
    "Melanle": "Melanie",
    "Phaedusa": "Phaetusa",
    "Balthalde": "Balthilde",
}

# Lowercase/no-space token fixes are used for cache keys and OCR text where the OCR
# removed spacing around a speaker name.
_GFL_ALIASES: dict[str, str] = {
    "AK-I2": "AK-12", "AK-I5": "AK-15", "AN-9A": "AN-94", "M4AI": "M4A1",
    "ST AR-I5": "ST AR-15", "AR-I5": "AR-15", "UMP4S": "UMP45", "UMPg": "UMP9",
    "TokareV": "Tokarev", "Kalinais": "Kalina is", "Kalinaand": "Kalina and",
    "Dandelionthis": "Dandelion this", "Dandelionfortunately": "Dandelion fortunately",
}

_GFL2_TOKEN_FIXES: dict[str, str] = {
    "ralzel": "Raizei",
    "ralzei": "Raizei",
    "raizel": "Raizei",
    "raizei": "Raizei",
    "voymastlna": "Voymastina",
    "voymastiha": "Voymastina",
    "vaymastina": "Voymastina",
    "vaymastin": "Voymastina",
    "voymastin": "Voymastina",
    "aiva": "Alva",
    "alva": "Alva",
    "dp12": "DP-12",
    "dandellon": "Dandelion",
    "elanie": "Melanie",
    "melanle": "Melanie",
    "phaedusa": "Phaetusa",
    "balthalde": "Balthilde",
}


def _game_allows_alias(game: str | None = None) -> bool:
    g = str(game or "").upper()
    return (not g) or g in {"GFL", "GIRLS_FRONTLINE", "GFL1", "GFL2", "GFL2_EXILIUM", "CUSTOM"}


def apply_name_aliases(text: str, game: str | None = None) -> str:
    """Correct high-confidence OCR name aliases.

    The function avoids broad fuzzy replacement.  It only touches exact word tokens
    and a few common no-space speaker forms observed in GFL2 logs.
    """
    s = str(text or "")
    if not s or not _game_allows_alias(game):
        return s
    g = str(game or "").upper()
    if g in {"GFL", "GIRLS_FRONTLINE", "GFL1"}:
        for raw, fixed in _GFL_ALIASES.items():
            s = re.sub(rf"\b{re.escape(raw)}\b", fixed, s, flags=re.I)
    for raw, fixed in _GFL2_ALIASES.items():
        s = re.sub(rf"\b{re.escape(raw)}\b", fixed, s)
    # Fix OCR variants at line starts/speaker slots and after punctuation.
    parts: list[str] = []
    for tok in re.split(r"(\W+)", s):
        key = re.sub(r"[^A-Za-z]", "", tok).lower()
        fixed = _GFL2_TOKEN_FIXES.get(key)
        if fixed and (tok[:1].isupper() or key in {"ralzel", "ralzei", "raizel", "voymastlna", "vaymastina", "vaymastin", "voymastin"}):
            parts.append(fixed)
        else:
            parts.append(tok)
    s = "".join(parts)
    s = re.sub(r"\bVoymastina\s+s\b", "Voymastina's", s)
    s = re.sub(r"\bVoymastinas\b", "Voymastina's", s)
    if g in {"GFL2", "GFL2_EXILIUM"}:
        # Context-safe observed GFL2 repairs; do not blindly rewrite ambiguous DP-125.
        s = re.sub(r"\b[Dd][Pp]-[Iil1]2\b", "DP-12", s)
        s = re.sub(r"\bKSVKs\b", "KSVK's", s)
        # v8.7.2: canonical-name boundary restoration for joined body words.
        s = re.sub(r"\bKSVK(?:and)\b", "KSVK and", s, flags=re.I)
        s = re.sub(r"\bKSVK(?:is)\b", "KSVK is", s, flags=re.I)
        s = re.sub(r"\bKSVK(?:was)\b", "KSVK was", s, flags=re.I)
        s = re.sub(r"\bKSVK(?:has)\b", "KSVK has", s, flags=re.I)
        s = re.sub(r"\bDp-12\b|\bdp-12\b", "DP-12", s)
        # DP-125 was observed where possessive DP-12's precedes body nouns.
        # Restrict the repair to safe possessive contexts rather than global replacement.
        s = re.sub(r"\bDP-125(?=\s+(?:voice|answer|hand|hands|hair|eyes|expression|data|neural|memories)\b)", "DP-12's", s, flags=re.I)
    return s


def alias_report(text: str, game: str | None = None) -> list[AliasHit]:
    raw = str(text or "")
    fixed = apply_name_aliases(raw, game)
    if raw == fixed:
        return []
    hits: list[AliasHit] = []
    for a, b in _GFL2_ALIASES.items():
        if re.search(rf"\b{re.escape(a)}\b", raw) and b in fixed:
            hits.append(AliasHit(a, b))
    return hits
