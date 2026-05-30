"""v8.7.8 dialogue completeness/stable-commit decisions.

Accuracy-first profiles use final-only safe commit: a new progressive subtitle is
held for one stabilising frame rather than displayed as an unreliable final.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

_CONNECTIVE = re.compile(r"^\s*(?:and|but|then|or|so|because|while|when|thank you)\b", re.I)
_TERMINAL = re.compile(r"[.!?…][\"')\]]?\s*$")
_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+")

@dataclass(frozen=True)
class CompletenessDecision:
    allow_overlay: bool
    reason: str = ""
    source_words: int = 0
    output_coverage: float = 1.0
    final_only_safe_commit: bool = False
    @property
    def hold(self) -> bool: return not self.allow_overlay
    @property
    def allowed(self) -> bool: return self.allow_overlay

def hold_incomplete_source(source: str, relation: str, *, auto_mode: bool = True, final_only_accuracy: bool = False) -> CompletenessDecision:
    text = str(source or "").strip(); words = _WORD.findall(text)
    progressive = relation in {"new", "progressive"}
    if not auto_mode or not progressive or _TERMINAL.search(text):
        return CompletenessDecision(True, source_words=len(words), final_only_safe_commit=final_only_accuracy)
    if _CONNECTIVE.search(text) and len(words) <= 12:
        return CompletenessDecision(False, "short_connective_prefix", len(words), 0.0, final_only_accuracy)
    if len(words) <= 2 or len(text) < 10:
        return CompletenessDecision(False, "source_too_short_progressive", len(words), 0.0, final_only_accuracy)
    # IDN/Normal quality modes must wait for repetition or punctuation before a
    # progressive source replaces a safe final overlay.
    if final_only_accuracy:
        return CompletenessDecision(False, "accuracy_final_only_wait_stable", len(words), 0.0, True)
    return CompletenessDecision(True, source_words=len(words))

def assess_output_coverage(source: str, output: str, relation: str, *, accuracy_first: bool = False) -> CompletenessDecision:
    src_words = _WORD.findall(str(source or "")); out_words = _WORD.findall(str(output or ""))
    if len(src_words) < 8:
        return CompletenessDecision(True, source_words=len(src_words), final_only_safe_commit=accuracy_first)
    coverage = len(out_words) / max(1, len(src_words))
    floor = 0.34 if accuracy_first else 0.22
    if coverage < floor or len(str(output or "").strip()) < 12:
        return CompletenessDecision(False, "output_coverage_too_low", len(src_words), round(coverage, 3), accuracy_first)
    return CompletenessDecision(True, source_words=len(src_words), output_coverage=round(coverage, 3), final_only_safe_commit=accuracy_first)
