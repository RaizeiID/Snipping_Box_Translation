"""ORT v8.9.1 Contextual OCR Text Repair.

This module repairs common OCR corruption before translation while staying
conservative enough for live story use. It is not a free-form autocorrector:
repairs are deterministic, token-bounded, and either dictionary-backed common
OCR fixes or registry/entity aliases handled by PredictionGuard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class RepairEvent:
    source: str
    target: str
    label: str
    reason: str


@dataclass(frozen=True)
class RepairResult:
    text: str
    events: List[RepairEvent] = field(default_factory=list)
    changed: bool = False


_BOUNDARY = r"(?<![A-Za-z0-9]){src}(?![A-Za-z0-9])"

# Deterministic whole-token fixes observed in v8.8.9 logs and earlier sessions.
# Green fixes are low-risk spelling/spacing/casing repairs; Yellow fixes are
# only applied when surrounded by ordinary English context.
COMMON_FIXES: Dict[str, Tuple[str, str]] = {
    "Qur": ("our", "green"),
    "qur": ("our", "green"),
    "Ifnot": ("If not", "green"),
    "ifnot": ("if not", "green"),
    "callyoU": ("call you", "green"),
    "callyOU": ("call you", "green"),
    "callyou": ("call you", "green"),
    "Oroshould": ("Or should", "yellow"),
    "Orshould": ("Or should", "green"),
    "orshould": ("or should", "green"),
    "must'ye": ("must've", "green"),
    "Must'ye": ("Must've", "green"),
    "weve": ("we've", "green"),
    "Weve": ("We've", "green"),
    "yoU": ("you", "green"),
    "yOU": ("you", "green"),
    "oU": ("ou", "yellow"),
    "Becaus": ("Because", "green"),
    "becaus": ("because", "green"),
    "aybe": ("maybe", "yellow"),
    "Aybe": ("Maybe", "yellow"),
    "telljust": ("tell just", "green"),
    "notall": ("not all", "green"),
    "notallt": ("not all t", "yellow"),
    "Iits": ("It's", "yellow"),
    "Its": ("It's", "yellow"),
    "Ofcourse": ("Of course", "green"),
    "offcourse": ("of course", "green"),
    "dont": ("don't", "yellow"),
    "Dont": ("Don't", "yellow"),
    "wont": ("won't", "yellow"),
    "Wont": ("Won't", "yellow"),
    "can'tt": ("can't", "green"),
}

# Character confusions seen in OCR. This table is only used by specific word
# families below, not globally.
WORD_FAMILIES: Dict[str, Iterable[str]] = {
    "healing": ("healin9", "healng", "healln9", "heallng", "heaIing", "heaiing"),
    "look": ("Iook", "l00k", "iook"),
    "look at": ("ook at", "0ok at", "Iook at"),
    "our": ("Qur", "0ur", "Owr"),
    "your": ("yoUr", "yOUr"),
    "you": ("yoU", "yOU"),
}

# Prefix repairs are applied at sentence/dialogue starts because OCR often loses
# the first glyph: "ook at" -> "look at", "aybe" -> "maybe".
PREFIX_FIXES: Dict[str, Tuple[str, str]] = {
    "ook at": ("look at", "green"),
    "ookat": ("look at", "green"),
    "aybe": ("maybe", "yellow"),
    "f we": ("if we", "green"),
    "f you're": ("if you're", "green"),
    "fyou're": ("if you're", "green"),
    "'m not": ("I'm not", "green"),
    "m not": ("I'm not", "yellow"),
    "t's": ("It's", "yellow"),
    "here's": ("There's", "yellow"),
}

# Words that are too short or ambiguous should never be repaired by common-word
# logic without a stronger subsystem such as entity registry/ROI.
AMBIGUOUS_SHORT = {"rid", "hel", "bal", "ny", "or", "he", "she"}


def _replace_boundary(text: str, src: str, dst: str) -> tuple[str, bool]:
    rx = re.compile(_BOUNDARY.format(src=re.escape(src)), re.IGNORECASE)
    new = rx.sub(dst, text)
    return new, new != text


def _apply_prefix(text: str, events: List[RepairEvent]) -> str:
    stripped = text.lstrip()
    lead = text[: len(text) - len(stripped)]
    low = stripped.lower()
    for src, (dst, label) in sorted(PREFIX_FIXES.items(), key=lambda x: len(x[0]), reverse=True):
        if low == src.lower() or low.startswith(src.lower() + " "):
            # Preserve sentence-start capitalization from the replacement.
            repaired = lead + dst + stripped[len(src):]
            if repaired != text:
                events.append(RepairEvent(src, dst, label.capitalize(), "contextual_prefix_ocr_repair"))
                return repaired
    return text


def _apply_word_families(text: str, events: List[RepairEvent]) -> str:
    for canonical, variants in WORD_FAMILIES.items():
        for src in variants:
            if src.lower() in AMBIGUOUS_SHORT:
                continue
            new, changed = _replace_boundary(text, src, canonical)
            if changed:
                text = new
                events.append(RepairEvent(src, canonical, "Green", "ocr_confusion_family_repair"))
    return text


def repair_text(text: str, *, enabled: bool | None = None) -> RepairResult:
    if enabled is None:
        enabled = os.environ.get("ORT_CONTEXTUAL_OCR_REPAIR", "1") != "0"
    original = str(text or "")
    if not enabled or not original.strip():
        return RepairResult(original, [], False)

    events: List[RepairEvent] = []
    repaired = original
    repaired = _apply_prefix(repaired, events)
    repaired = _apply_word_families(repaired, events)

    for src, (dst, label) in sorted(COMMON_FIXES.items(), key=lambda x: len(x[0]), reverse=True):
        if src.lower() in AMBIGUOUS_SHORT:
            continue
        new, changed = _replace_boundary(repaired, src, dst)
        if changed:
            repaired = new
            events.append(RepairEvent(src, dst, label.capitalize(), "common_ocr_token_repair"))

    # Light punctuation/spacing repair. These do not alter semantics.
    before = repaired
    repaired = re.sub(r"\s+([,.;:!?])", r"\1", repaired)
    repaired = re.sub(r"([,.;:!?])(\S)", r"\1 \2", repaired)
    repaired = re.sub(r"\s{2,}", " ", repaired).strip()
    if repaired != before:
        events.append(RepairEvent("spacing/punctuation", "normalized", "Green", "spacing_punctuation_repair"))

    return RepairResult(repaired, events, repaired != original)
