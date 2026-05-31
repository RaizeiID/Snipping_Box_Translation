"""ORT v8.8.5 Turn Finalizer.

Overlay commit gates reduce flicker, but each game-dialogue turn must still get
one complete final render before it is allowed to disappear. This module tracks
best source/translation per turn and tells the renderer when a final complete
commit should override min-visible/similar suppression.
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


class TurnFinalizer:
    def __init__(self, *, final_wait_ms: int = 420, min_gain_words: int = 2, max_corruption: float = 0.58) -> None:
        self.final_wait_ms = int(final_wait_ms)
        self.min_gain_words = int(min_gain_words)
        self.max_corruption = float(max_corruption)
        self._turn_id = ""
        self._best_source = ""
        self._best_translation = ""
        self._best_words = 0
        self._best_ts = 0.0
        self._final_committed = False

    @classmethod
    def from_env(cls) -> "TurnFinalizer":
        return cls(
            final_wait_ms=int(os.environ.get("ORT_TURN_FINALIZER_WAIT_MS", "420")),
            min_gain_words=int(os.environ.get("ORT_TURN_FINALIZER_MIN_GAIN", "2")),
            max_corruption=float(os.environ.get("ORT_TURN_FINALIZER_MAX_CORRUPTION", "0.58")),
        )

    def reset(self) -> None:
        self._turn_id = ""
        self._best_source = ""
        self._best_translation = ""
        self._best_words = 0
        self._best_ts = 0.0
        self._final_committed = False

    def update(self, *, turn_id: str, source: str, translation: str, source_stable: bool = False, final_payload: bool = False, mode: str = "") -> TurnFinalizerDecision:
        now = time.time()
        tid = str(turn_id or "").strip()
        src = str(source or "").strip()
        out = str(translation or "").strip()
        if tid and tid != self._turn_id:
            self._turn_id = tid
            self._best_source = ""
            self._best_translation = ""
            self._best_words = 0
            self._best_ts = now
            self._final_committed = False
        w = len(words(src))
        corr = ocr_corruption_score(src)
        source_better = bool(src and (w > self._best_words + self.min_gain_words or len(src) > len(self._best_source) + 14))
        if src and (not self._best_source or (source_better and corr <= self.max_corruption) or similarity(src, self._best_source) >= 0.94 and len(src) >= len(self._best_source)):
            self._best_source = src
            self._best_translation = out or self._best_translation
            self._best_words = max(self._best_words, w)
            self._best_ts = now
        age_ms = int((now - (self._best_ts or now)) * 1000)
        due = bool(source_stable or terminal_punctuation(self._best_source) or age_ms >= self.final_wait_ms or str(mode or "").upper() in {"FREEZE", "INTERVAL"})
        if final_payload and due and not self._final_committed and self._best_source and corr <= self.max_corruption:
            self._final_committed = True
            return TurnFinalizerDecision(True, "turn_finalizer_complete_due", self._best_source, True, corr)
        if source_better and final_payload and corr <= self.max_corruption:
            return TurnFinalizerDecision(True, "source_longer_must_win", self._best_source, due, corr)
        return TurnFinalizerDecision(False, "not_due", self._best_source or src, due, corr)
