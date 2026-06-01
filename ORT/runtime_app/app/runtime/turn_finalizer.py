"""ORT v8.8.6 Turn Finalizer v2.

Mandatory final commit before a dialogue turn is allowed to expire. This is the
core fix for translations that only show 20–90% of the visible dialogue.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time

from app.runtime.render_signature import words, terminal_punctuation, similarity, ocr_corruption_score


@dataclass(frozen=True)
class TurnFinalizerDecision:
    force_final: bool
    reason: str
    best_source: str
    final_due: bool
    corruption: float
    mandatory: bool = False


class TurnFinalizer:
    def __init__(self, *, final_wait_ms: int = 360, min_gain_words: int = 2, max_corruption: float = 0.62, hard_deadline_ms: int = 900) -> None:
        self.final_wait_ms = int(final_wait_ms)
        self.min_gain_words = int(min_gain_words)
        self.max_corruption = float(max_corruption)
        self.hard_deadline_ms = int(hard_deadline_ms)
        self._turn_id = ""
        self._best_source = ""
        self._best_translation = ""
        self._best_words = 0
        self._best_ts = 0.0
        self._turn_start_ts = 0.0
        self._final_committed = False

    @classmethod
    def from_env(cls) -> "TurnFinalizer":
        return cls(
            final_wait_ms=int(os.environ.get("ORT_TURN_FINALIZER_WAIT_MS", "360")),
            min_gain_words=int(os.environ.get("ORT_TURN_FINALIZER_MIN_GAIN", "2")),
            max_corruption=float(os.environ.get("ORT_TURN_FINALIZER_MAX_CORRUPTION", "0.62")),
            hard_deadline_ms=int(os.environ.get("ORT_TURN_FINALIZER_HARD_DEADLINE_MS", "900")),
        )

    def reset(self) -> None:
        self._turn_id = ""
        self._best_source = ""
        self._best_translation = ""
        self._best_words = 0
        self._best_ts = 0.0
        self._turn_start_ts = 0.0
        self._final_committed = False

    def update(self, *, turn_id: str, source: str, translation: str, source_stable: bool = False, final_payload: bool = False, mode: str = "", consensus_ready: bool = False, buffer_due: bool = True) -> TurnFinalizerDecision:
        now = time.time()
        tid = str(turn_id or "").strip() or "default"
        src = str(source or "").strip()
        out = str(translation or "").strip()
        if tid != self._turn_id:
            self._turn_id = tid
            self._best_source = ""
            self._best_translation = ""
            self._best_words = 0
            self._best_ts = now
            self._turn_start_ts = now
            self._final_committed = False
        w = len(words(src))
        corr = ocr_corruption_score(src)
        source_better = bool(src and (w > self._best_words + self.min_gain_words or len(src) > len(self._best_source) + 12))
        source_same_or_better = bool(src and (not self._best_source or source_better or (similarity(src, self._best_source) >= 0.92 and len(src) >= len(self._best_source))))
        if source_same_or_better and corr <= self.max_corruption:
            self._best_source = src
            self._best_translation = out or self._best_translation
            self._best_words = max(self._best_words, w)
            self._best_ts = now
        best_corr = ocr_corruption_score(self._best_source or src)
        stable_age_ms = int((now - (self._best_ts or now)) * 1000)
        turn_age_ms = int((now - (self._turn_start_ts or now)) * 1000)
        mode_u = str(mode or "").upper()
        due = bool(source_stable or consensus_ready or terminal_punctuation(self._best_source) or stable_age_ms >= self.final_wait_ms or mode_u in {"FREEZE", "INTERVAL"})
        hard_due = bool(turn_age_ms >= self.hard_deadline_ms and self._best_source and not self._final_committed)
        if final_payload and self._best_source and best_corr <= self.max_corruption:
            if source_better:
                return TurnFinalizerDecision(True, "source_longer_must_win_v2", self._best_source, True, best_corr, True)
            if (due and buffer_due and not self._final_committed) or hard_due:
                self._final_committed = True
                reason = "mandatory_final_deadline" if hard_due else "mandatory_final_commit_v2"
                return TurnFinalizerDecision(True, reason, self._best_source, True, best_corr, True)
        return TurnFinalizerDecision(False, "not_due", self._best_source or src, due or hard_due, best_corr, False)
