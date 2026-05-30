"""ORT Translation v8.7.9 General Semantic Fidelity Guard.

Compares a polished candidate against the source while retaining a CT2 literal
anchor as the safe fallback.  This supplements the hallucination blacklist with
checks for omission/drift that were observed in v8.7.8 live video and logs.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9-]+")
_NUM = re.compile(r"\b\d+(?:[.,-]\d+)?\b")
_NEG_SRC = re.compile(r"\b(?:not|no|never|cannot|can't|won't|wouldn't|didn't|without|refuse|refuses|refused)\b", re.I)
_NEG_OUT = re.compile(r"\b(?:not|no|never|cannot|can't|won't|without|refuse|tidak|tak|bukan|jangan|menolak|tanpa)\b", re.I)
_PROPER = re.compile(r"\b(?:[A-Z][A-Za-z0-9-]{2,}|[A-Z]{2,}(?:-[A-Z0-9]+)?)\b")
_STOP_PROPER = {"The", "This", "That", "Thank", "Will", "Okay", "News", "Normal", "Hard"}
_ACTIONS = {
    "bows": ("bow", "membungkuk"), "bow": ("bow", "membungkuk"),
    "death": ("death", "kematian", "mati", "tewas"), "die": ("die", "mati", "tewas"),
    "believe": ("believe", "percaya"), "abandon": ("abandon", "meninggalkan", "tinggalkan"),
    "leave": ("leave", "meninggalkan", "tinggalkan", "pergi"), "promise": ("promise", "janji"),
}
@dataclass(frozen=True)
class FidelityDecision:
    allowed: bool
    reason: str = "safe"
    flags: tuple[str, ...] = ()
    coverage: float = 1.0

def _norm(text: str) -> str:
    return str(text or "").casefold()

def assess_semantic_fidelity(source: str, candidate: str, literal_anchor: str = "") -> FidelityDecision:
    source, candidate, literal_anchor = str(source or ""), str(candidate or ""), str(literal_anchor or "")
    src_l, out_l = _norm(source), _norm(candidate)
    src_words, out_words = _WORD.findall(source), _WORD.findall(candidate)
    flags: list[str] = []
    coverage = len(out_words) / max(1, len(src_words))
    if len(src_words) >= 8 and (coverage < 0.34 or len(candidate.strip()) < 12):
        flags.append("coverage_low")
    if _NEG_SRC.search(source) and not _NEG_OUT.search(candidate):
        flags.append("negation_lost")
    numbers = set(_NUM.findall(source))
    if numbers and not numbers.issubset(set(_NUM.findall(candidate))):
        flags.append("number_lost")
    protected = {p for p in _PROPER.findall(source) if p not in _STOP_PROPER and len(p) >= 4}
    missing = sorted(p for p in protected if p.casefold() not in out_l)
    if missing:
        flags.append("entity_lost:" + ",".join(missing[:4]))
    for action, equivalents in _ACTIONS.items():
        if re.search(rf"\b{re.escape(action)}\b", src_l) and not any(eq in out_l for eq in equivalents):
            flags.append("action_lost:" + action)
    if flags:
        return FidelityDecision(False, "semantic_drift:" + ";".join(flags), tuple(flags), round(coverage, 3))
    return FidelityDecision(True, "safe", (), round(coverage, 3))
