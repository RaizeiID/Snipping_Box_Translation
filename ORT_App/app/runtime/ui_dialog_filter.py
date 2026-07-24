"""ORT v8.9.1 UI/Loading/Battle Text Filter v4.

Rejects non-dialog text before translation/cache so the story pipeline does not
spend time translating loading screens, battle instructions, reward counters,
or progress/menu text.  v8.8.9 adds fuzzy OCR variants observed in low-OCR
recording runs, while staying lightweight and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import List


@dataclass
class UIFilterDecision:
    process: bool
    text: str
    reason: str = "ok"
    category: str = "dialog"


class UIDialogFilter:
    DEFAULT_PATTERNS: List[str] = [
        r"\b(?:Loading|Loadlng|Loadlilng|LoBdlng|Coadlng|Coading)\s+(?:Resources|Resouroes|ResourCos|Resour)\b",
        r"\bCombat\s+Effectiveness\b",
        r"\bCombat\s+Start\b",
        r"\bClick\s*tile\s*or\s*drag\s*to\s*deploy\b",
        r"\bClick\s*anywhere\s*to\s*skip\b",
        r"\bClickanywhere\s*to\s*skip\b",
        r"\bHeroic\s+Mode\b",
        r"\b(?:Part\s+)?Challenge\s+Mode\b",
        r"\b(?:Part\s+)?Supply\b",
        r"\bStory\s+Supply\b",
        r"\bSupply\s+\d{1,3}%\b",
        r"\bStory\s+\d{1,3}%\b",
        r"\bDamage\s+Stats\b",
        r"\bContinue\s+Confirm\s+Damage\s+Stats\b",
        r"\bNo\s+more\s+items\s+will\s+be\s+gained\s+for\s+repeated\s+Challenges\b",
        r"\bCollect\s+more\s+to\s+claim\s+rewards?\b",
        r"\bCollect\b",
        r"\bColect\b",
        r"^\s*\d+\s*/\s*\d+\b",
        r"^\s*\d{1,3}\s*%\b",
        r"\b(?:Toysmith|Max\s+Level|Commander\s+Level|mmander\s+Level)\b",
        r"\b(?:Dammage|Damage)\s+Stats\s+Confirm\b",
        r"\bClick\s*anywhere\s*to\s*exit\b",
        r"\bClickanywhere\s*to\s*exit\b",
        r"\b(?:Formation|Commissions?|Platoon|End\s+Action|Marionette\s+Melee|Marionette\s+Repair|Marionette\s+Repalr|Marlonette\s+Repalr|Marlonette\s+Repair)\b",
        r"\b\d{2,5}\s*/\s*\d{2,5}\b",
    ]

    NARRATION_NOT_NAME = [
        "After finalizing",
        "The office",
        "According to",
        "Only those",
        "Turns out",
        "Chances are",
        "Hehe",
        "Challenge Mode",
        "Part Challenge Mode",
        "Part Supply",
        "Story Supply",
        "Damage Stats",
    ]

    MENU_WORD_RE = re.compile(r"\b(?:challenge|supply|story|heroic|damage|dammage|stats|confirm|continue|resources|loading|loadlilng|collect|reward|level|formation|commission|platoon|action|melee|toy smith|toysmith|marionette|marlonette|repair|repalr|coading)\b", re.I)
    PROGRESS_RE = re.compile(r"(?:\b\d+\s*/\s*\d+\b|\b\d{1,3}\s*%\b)")
    DIALOG_LIKE_RE = re.compile(r"[.!?…]|\b(?:I|you|we|they|she|he|Commander|Kenny|Raizei|Helen|Heli|Helena)\b", re.I)

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._compiled = [re.compile(p, re.I) for p in self.DEFAULT_PATTERNS]

    @classmethod
    def from_env(cls) -> "UIDialogFilter":
        return cls(enabled=os.environ.get("ORT_UI_DIALOG_FILTER", "1") != "0")

    def check(self, text: str, *, mode: str = "AUTO") -> UIFilterDecision:
        s = (text or "").strip()
        if not self.enabled or not s:
            return UIFilterDecision(True, s)
        for rx in self._compiled:
            if rx.search(s):
                return UIFilterDecision(False, s, "ui_loading_battle_text", "ui")
        # Loading/progress often appears with story lore behind it. Treat as UI if
        # progress/loading/menu prefix is present because it corrupts the OCR source.
        if re.match(r"^\s*(\d{1,3}%|\d+/\d+)\s+", s):
            return UIFilterDecision(False, s, "progress_prefix", "ui")
        low = s.lower()
        # OCR can drop the first characters: e.g. "enge Mode Part Challenge Mode...".
        if ("challenge mode" in low or "part supply" in low or "damage stats" in low) and self.PROGRESS_RE.search(s):
            return UIFilterDecision(False, s, "fuzzy_menu_progress_text", "ui")
        # Dense menu/reward text with multiple UI words and no real sentence marker.
        menu_hits = len(self.MENU_WORD_RE.findall(s))
        if menu_hits >= 3 and self.PROGRESS_RE.search(s) and not self.DIALOG_LIKE_RE.search(s):
            return UIFilterDecision(False, s, "dense_ui_menu_text", "ui")
        # v8.9.1: UI-score filter. Many battle/menu screens contain short
        # mixed title tokens plus numbers; they may have punctuation but are not
        # story dialogue. Keep this conservative by requiring several UI clues.
        numeric_hits = len(self.PROGRESS_RE.findall(s))
        slash_stat = bool(re.search(r"\b\d{2,5}\s*/\s*\d{2,5}\b", s))
        ui_score = menu_hits + (2 if slash_stat else 0) + (1 if numeric_hits else 0)
        if ui_score >= 3 and not re.search(r"\b(?:I|you|we|she|he|they|Commander|Raizei|Sweeper|Littara|Ullrid|Groza|Helen|Klukai)\b", s, re.I):
            return UIFilterDecision(False, s, "ui_score_non_dialog", "ui")
        # v8.9.1: reject mixed-script/OCR garbage from battle/loading screens, e.g.
        # "NzUtO Ra Rancaman @a 酋 UhDh" or stray Chinese glyph + menu fragments.
        cjk = len(re.findall(r"[\u4e00-\u9fff]", s))
        symbols = len(re.findall(r"[@#酋入本]", s))
        latin_words = re.findall(r"[A-Za-z]{2,}", s)
        if (cjk or symbols >= 2) and len(latin_words) <= 6 and not self.DIALOG_LIKE_RE.search(s):
            return UIFilterDecision(False, s, "mixed_script_ocr_garbage", "ui")
        return UIFilterDecision(True, s)

    def is_negative_name_prefix(self, text: str) -> bool:
        low = (text or "").strip().lower()
        return any(low.startswith(x.lower()) for x in self.NARRATION_NOT_NAME)
