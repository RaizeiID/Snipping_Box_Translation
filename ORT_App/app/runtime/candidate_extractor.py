"""ORT v8.8.8-r2 Candidate Name Extractor with negative rules."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class CandidateDecision:
    candidate: str
    kind: str
    confidence: str
    reason: str


NEGATIVE_STARTS = {
    "loading resources", "combat effectiveness", "combat start", "click anywhere",
    "clickanywhere", "collect", "colect", "heroic mode", "story supply",
    "after finalizing", "the office", "according to", "only those",
    "turns out", "chances are", "hehe",
}

KNOWN_PREFIXES = {
    "raizei": ("Raizei", "main_commander", "green"),
    "darture": ("Darture", "character_name", "green"),
    "poludnitsa": ("Poludnitsa", "character_or_story_entity", "green"),
    "anfiya sharapova": ("Anfiya Sharapova", "character_relation_name", "yellow"),
    "shadow figure": ("Shadow Figure", "masked_speaker_label", "green"),
    "shadowy figure": ("Shadowy Figure", "masked_speaker_label", "green"),
    "mangi security team leader": ("Mangi Security Team Leader", "speaker_label", "green"),
}


def classify_initial_candidate(text: str) -> CandidateDecision:
    s = (text or "").strip()
    low = s.lower()
    if not s:
        return CandidateDecision("", "empty", "red", "empty")
    if re.match(r"^(\d+/\d+|\d{1,3}%)\b", s):
        return CandidateDecision("", "ui_progress", "red", "progress_prefix")
    for neg in NEGATIVE_STARTS:
        if low.startswith(neg):
            return CandidateDecision("", "negative_ui_or_narration", "red", "negative_prefix")
    for prefix, (candidate, kind, conf) in sorted(KNOWN_PREFIXES.items(), key=lambda x: len(x[0]), reverse=True):
        if low == prefix or low.startswith(prefix + " "):
            return CandidateDecision(candidate, kind, conf, "known_prefix")
    tokens = s.split()
    if tokens and tokens[0][0].isupper() and len(tokens[0]) >= 3:
        return CandidateDecision(tokens[0], "review_candidate", "yellow", "capitalized_initial_token")
    return CandidateDecision("", "unknown", "red", "not_a_candidate")
