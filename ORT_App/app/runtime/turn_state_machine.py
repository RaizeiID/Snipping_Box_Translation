from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import os
import re
import threading
import time
from typing import Optional


_SPACE_RE = re.compile(r"\s+")
_COMPARE_RE = re.compile(r"[^a-z0-9']+")
_TAIL_RE = re.compile(r"[.!?…][\"')\]]?\s*$")


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", str(text or "").strip())


def _norm(text: str) -> str:
    return _COMPARE_RE.sub("", _clean(text).casefold())


def _similar(a: str, b: str) -> float:
    left = _norm(a)
    right = _norm(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _progressive(a: str, b: str) -> bool:
    left = _norm(a)
    right = _norm(b)
    if not left or not right:
        return False
    shorter = min(len(left), len(right))
    if shorter >= 4 and (left.startswith(right) or right.startswith(left)):
        return True
    if shorter < 10:
        return False
    prefix = SequenceMatcher(None, left[:shorter], right[:shorter]).ratio()
    return prefix >= 0.82 and abs(len(left) - len(right)) <= max(80, int(max(len(left), len(right)) * 0.70))


@dataclass(frozen=True)
class TurnToken:
    turn_id: str
    generation_id: int
    is_new_turn: bool
    source_changed: bool
    reason: str
    observed_at: float

    def as_meta(self) -> dict:
        return {
            "dialog_turn_id": self.turn_id,
            "generation_id": self.generation_id,
            "dialog_new_turn": self.is_new_turn,
            "turn_state_reason": self.reason,
            "turn_observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class ClearToken:
    should_clear: bool
    previous_turn_id: str
    generation_id: int
    reason: str
    observed_at: float

    def as_meta(self) -> dict:
        return {
            "control": "explicit_clear",
            "previous_turn_id": self.previous_turn_id,
            "generation_id": self.generation_id,
            "clear_reason": self.reason,
            "turn_observed_at": self.observed_at,
        }


class TurnStateMachine:
    def __init__(self, *, new_turn_similarity: float = 0.52, absence_misses: int = 2, absence_min_ms: int = 550) -> None:
        self.new_turn_similarity = max(0.20, min(0.90, float(new_turn_similarity)))
        self.absence_misses = max(1, int(absence_misses))
        self.absence_min_ms = max(0, int(absence_min_ms))
        self._lock = threading.RLock()
        self._turn_sequence = 0
        self._generation = 0
        self._turn_id = ""
        self._speaker = ""
        self._source = ""
        self._first_source = ""
        self._turn_started_at = 0.0
        self._last_observed_at = 0.0
        self._absence_started_at = 0.0
        self._absence_count = 0

    @classmethod
    def from_env(cls) -> "TurnStateMachine":
        return cls(
            new_turn_similarity=float(os.environ.get("ORT_TURN_NEW_SIMILARITY", "0.52")),
            absence_misses=int(os.environ.get("ORT_DIALOG_CLEAR_MISSES", "2")),
            absence_min_ms=int(os.environ.get("ORT_DIALOG_CLEAR_MIN_MS", "550")),
        )

    def _make_turn_id(self, speaker: str, source: str) -> str:
        self._turn_sequence += 1
        digest = hashlib.sha1(f"{speaker.casefold()}\n{_norm(source)[:160]}".encode("utf-8", "ignore")).hexdigest()[:8]
        return f"t{self._turn_sequence:06d}-{digest}"

    def _begin_turn(self, speaker: str, source: str, now: float, reason: str) -> TurnToken:
        self._generation += 1
        self._turn_id = self._make_turn_id(speaker, source)
        self._speaker = speaker
        self._source = source
        self._first_source = source
        self._turn_started_at = now
        self._last_observed_at = now
        self._absence_started_at = 0.0
        self._absence_count = 0
        return TurnToken(self._turn_id, self._generation, True, True, reason, now)

    def observe(self, source: str, *, speaker: str = "") -> TurnToken:
        now = time.time()
        source = _clean(source)
        speaker = _clean(speaker)
        with self._lock:
            self._absence_started_at = 0.0
            self._absence_count = 0
            if not source:
                return TurnToken(self._turn_id, self._generation, False, False, "empty_observation", now)
            if not self._turn_id or not self._source:
                return self._begin_turn(speaker, source, now, "initial_turn")

            current_speaker = self._speaker.casefold()
            incoming_speaker = speaker.casefold()
            speaker_changed = bool(current_speaker and incoming_speaker and current_speaker != incoming_speaker)
            progressive = _progressive(self._source, source)
            sim = _similar(self._source, source)
            previous_complete = bool(_TAIL_RE.search(self._source))
            likely_new = speaker_changed or (
                not progressive
                and sim < self.new_turn_similarity
                and (previous_complete or len(_norm(source)) >= 8)
            )
            if likely_new:
                reason = "speaker_changed" if speaker_changed else "source_discontinuity"
                return self._begin_turn(speaker, source, now, reason)

            if incoming_speaker and not current_speaker:
                self._speaker = speaker
            source_changed = _norm(source) != _norm(self._source)
            if source_changed:
                self._generation += 1
                self._source = source
            self._last_observed_at = now
            reason = "progressive_update" if progressive and source_changed else ("ocr_revision" if source_changed else "duplicate_observation")
            return TurnToken(self._turn_id, self._generation, False, source_changed, reason, now)

    def observe_absence(self, *, reason: str = "dialogue_absent") -> ClearToken:
        now = time.time()
        with self._lock:
            if not self._turn_id:
                return ClearToken(False, "", self._generation, "no_active_turn", now)
            if self._absence_count == 0:
                self._absence_started_at = now
            self._absence_count += 1
            age_ms = int((now - self._absence_started_at) * 1000)
            if self._absence_count < self.absence_misses or age_ms < self.absence_min_ms:
                return ClearToken(False, self._turn_id, self._generation, "absence_debounce", now)
            return self.clear(reason=reason)

    def clear(self, *, reason: str = "explicit_clear") -> ClearToken:
        now = time.time()
        with self._lock:
            previous = self._turn_id
            if not previous:
                return ClearToken(False, "", self._generation, "no_active_turn", now)
            self._generation += 1
            token = ClearToken(True, previous, self._generation, reason, now)
            self._turn_id = ""
            self._speaker = ""
            self._source = ""
            self._first_source = ""
            self._turn_started_at = 0.0
            self._last_observed_at = now
            self._absence_started_at = 0.0
            self._absence_count = 0
            return token

    def is_current(self, turn_id: str, generation_id: int) -> bool:
        with self._lock:
            return bool(turn_id) and turn_id == self._turn_id and int(generation_id) == self._generation

    def is_generation_current(self, generation_id: int) -> bool:
        with self._lock:
            return int(generation_id) == self._generation

    def current(self) -> Optional[TurnToken]:
        with self._lock:
            if not self._turn_id:
                return None
            return TurnToken(self._turn_id, self._generation, False, False, "current", self._last_observed_at)

    def reset(self) -> None:
        with self._lock:
            self._turn_sequence = 0
            self._generation = 0
            self._turn_id = ""
            self._speaker = ""
            self._source = ""
            self._first_source = ""
            self._turn_started_at = 0.0
            self._last_observed_at = 0.0
            self._absence_started_at = 0.0
            self._absence_count = 0


_STATE_MACHINE: Optional[TurnStateMachine] = None
_STATE_MACHINE_LOCK = threading.Lock()


def get_turn_state_machine() -> TurnStateMachine:
    global _STATE_MACHINE
    with _STATE_MACHINE_LOCK:
        if _STATE_MACHINE is None:
            _STATE_MACHINE = TurnStateMachine.from_env()
        return _STATE_MACHINE
