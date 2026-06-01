"""ORT v8.8.6 Temporal OCR Consensus.

Final-lane only consensus for story subtitles. It does not block fast preview.
It keeps a small window of recent OCR strings for each turn and builds a
best_source_consensus so the final commit is based on stable text instead of a
single noisy frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import os
import time

from app.runtime.render_signature import repair_ocr_text, ocr_corruption_score, words, similarity, terminal_punctuation


@dataclass(frozen=True)
class ConsensusDecision:
    text: str
    changed: bool
    ready: bool
    confidence: float
    reason: str
    frame_count: int
    corruption: float


class TemporalOCRConsensus:
    def __init__(self, *, window: int = 5, min_frames: int = 2, stable_ms: int = 260, max_corruption: float = 0.62) -> None:
        self.window = max(2, int(window))
        self.min_frames = max(1, int(min_frames))
        self.stable_ms = max(0, int(stable_ms))
        self.max_corruption = float(max_corruption)
        self._turn_id = ""
        self._frames = deque(maxlen=self.window)
        self._last_best = ""
        self._last_change_ts = 0.0

    @classmethod
    def from_env(cls) -> "TemporalOCRConsensus":
        return cls(
            window=int(os.environ.get("ORT_TEMPORAL_OCR_CONSENSUS_WINDOW", "5")),
            min_frames=int(os.environ.get("ORT_TEMPORAL_OCR_CONSENSUS_MIN_FRAMES", "2")),
            stable_ms=int(os.environ.get("ORT_TEMPORAL_OCR_CONSENSUS_STABLE_MS", "260")),
            max_corruption=float(os.environ.get("ORT_TEMPORAL_OCR_CONSENSUS_MAX_CORRUPTION", "0.62")),
        )

    def reset(self) -> None:
        self._turn_id = ""
        self._frames.clear()
        self._last_best = ""
        self._last_change_ts = 0.0

    def _score(self, text: str) -> float:
        w = len(words(text))
        corr = ocr_corruption_score(text)
        punct = 0.25 if terminal_punctuation(text) else 0.0
        return (w * 1.0) + min(len(text) / 80.0, 2.5) + punct - (corr * 4.0)

    def update(self, *, turn_id: str, text: str, mode: str = "", allow_final_lane: bool = True) -> ConsensusDecision:
        raw = repair_ocr_text(str(text or "").strip())
        if not raw:
            return ConsensusDecision("", False, False, 0.0, "empty", 0, 1.0)
        tid = str(turn_id or "").strip()
        now = time.time()
        if tid and tid != self._turn_id:
            self._turn_id = tid
            self._frames.clear()
            self._last_best = ""
            self._last_change_ts = now
        corr = ocr_corruption_score(raw)
        self._frames.append((raw, now, corr))
        # choose the longest/least corrupted candidate that agrees with neighbours
        candidates = [x[0] for x in self._frames]
        best = max(candidates, key=self._score)
        # If latest is substantially longer and not corrupted, prefer it quickly.
        if len(raw) > len(best) + 10 and corr <= self.max_corruption:
            best = raw
        changed = bool(best and best != self._last_best)
        if changed:
            self._last_best = best
            self._last_change_ts = now
        age_ms = int((now - (self._last_change_ts or now)) * 1000)
        similar_count = sum(1 for c in candidates if similarity(c, best) >= 0.86)
        ready = bool(
            allow_final_lane
            and len(self._frames) >= self.min_frames
            and ocr_corruption_score(best) <= self.max_corruption
            and (similar_count >= self.min_frames or terminal_punctuation(best) or age_ms >= self.stable_ms)
        )
        confidence = min(1.0, (similar_count / max(1, len(self._frames))) * (1.0 - min(0.8, ocr_corruption_score(best))))
        reason = "consensus_ready" if ready else ("collecting_frames" if len(self._frames) < self.min_frames else "waiting_stable")
        return ConsensusDecision(best, changed, ready, round(confidence, 4), reason, len(self._frames), ocr_corruption_score(best))
