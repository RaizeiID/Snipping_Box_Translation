"""ORT v8.8.3 dialogue stability helpers.

This module is intentionally lightweight and deterministic.  It lives on the
runtime path so Auto Story can smooth noisy/progressive OCR without adding a
heavy semantic/model gate in the preview lane.

Main goals:
- keep the best source text for the current dialogue turn;
- prevent downgrading to a shorter/noisier OCR frame;
- coalesce tiny progressive updates so the overlay does not flicker;
- let Freeze and stable Interval behave more accurately than Auto.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import os
import re
import time

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+")
_TERMINAL_RE = re.compile(r"[.!?…][\"')\]]?\s*$")
_NOISE_RE = re.compile(r"[^A-Za-zÀ-ÿ0-9\s.,!?;:'\-()\[\]…]")


def _norm(text: str) -> str:
    s = str(text or "").strip().casefold()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(str(text or ""))


def _similar(a: str, b: str) -> float:
    a = _norm(a); b = _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return min(len(a), len(b)) / max(1, max(len(a), len(b)))
    return SequenceMatcher(None, a, b).ratio()


def _looks_same_turn(prev: str, cur: str) -> bool:
    p = _norm(prev); c = _norm(cur)
    if not p or not c:
        return False
    if p.startswith(c) or c.startswith(p):
        return True
    return _similar(prev, cur) >= 0.72


def _quality_score(text: str) -> float:
    s = str(text or "").strip()
    if not s:
        return -999.0
    words = _words(s)
    word_score = len(words) * 9.0
    length_score = min(len(s), 220) * 0.35
    terminal_bonus = 20.0 if _TERMINAL_RE.search(s) else 0.0
    punctuation_bonus = 4.0 if any(ch in s for ch in ",;:") else 0.0
    noise_penalty = len(_NOISE_RE.findall(s)) * 8.0
    orphan_penalty = sum(1 for w in words if len(w) == 1) * 1.5
    return word_score + length_score + terminal_bonus + punctuation_bonus - noise_penalty - orphan_penalty


@dataclass(frozen=True)
class DialogueStabilityDecision:
    process: bool
    text: str
    reason: str
    state: str
    best_changed: bool = False
    source_stable: bool = False
    turn_id: str = ""


class DialogueTurnAccumulator:
    """Small per-runtime accumulator for OCR text of the current dialog turn."""

    def __init__(
        self,
        *,
        auto_min_ms: int = 220,
        auto_min_token_gain: int = 3,
        interval_stable_ms: int = 420,
        interval_min_token_gain: int = 5,
        duplicate_hold_ms: int = 900,
    ) -> None:
        self.auto_min_ms = max(80, int(auto_min_ms))
        self.auto_min_token_gain = max(1, int(auto_min_token_gain))
        self.interval_stable_ms = max(120, int(interval_stable_ms))
        self.interval_min_token_gain = max(1, int(interval_min_token_gain))
        self.duplicate_hold_ms = max(120, int(duplicate_hold_ms))
        self._speaker = ""
        self._turn_id = ""
        self._best = ""
        self._best_score = -999.0
        self._first_ts = 0.0
        self._last_update_ts = 0.0
        self._last_emit_text = ""
        self._last_emit_ts = 0.0
        self._last_seen_norm = ""
        self._repeat_count = 0

    @classmethod
    def from_env(cls) -> "DialogueTurnAccumulator":
        return cls(
            auto_min_ms=int(os.environ.get("ORT_AUTO_SMOOTH_MIN_MS", "220")),
            auto_min_token_gain=int(os.environ.get("ORT_AUTO_SMOOTH_MIN_TOKEN_GAIN", "3")),
            interval_stable_ms=int(os.environ.get("ORT_INTERVAL_STABLE_MS", "420")),
            interval_min_token_gain=int(os.environ.get("ORT_INTERVAL_MIN_TOKEN_GAIN", "5")),
            duplicate_hold_ms=int(os.environ.get("ORT_OVERLAY_DUPLICATE_HOLD_MS", "900")),
        )

    def reset(self) -> None:
        self.__init__(
            auto_min_ms=self.auto_min_ms,
            auto_min_token_gain=self.auto_min_token_gain,
            interval_stable_ms=self.interval_stable_ms,
            interval_min_token_gain=self.interval_min_token_gain,
            duplicate_hold_ms=self.duplicate_hold_ms,
        )

    def update(self, speaker: str, body: str, *, mode: str = "", turn_id: str = "") -> DialogueStabilityDecision:
        now = time.time()
        speaker = str(speaker or "").strip()
        body = str(body or "").strip()
        mode_u = str(mode or "").upper()
        if not body:
            return DialogueStabilityDecision(False, body, "empty_body", "EMPTY", turn_id=turn_id)

        explicit_turn = str(turn_id or "").strip()
        new_turn = False
        if explicit_turn and explicit_turn != self._turn_id:
            new_turn = True
        elif speaker and self._speaker and speaker.casefold() != self._speaker.casefold() and not _looks_same_turn(self._best, body):
            new_turn = True
        elif self._best and not _looks_same_turn(self._best, body) and _similar(self._best, body) < 0.48:
            new_turn = True

        if new_turn or not self._best:
            self._speaker = speaker
            self._turn_id = explicit_turn
            self._best = body
            self._best_score = _quality_score(body)
            self._first_ts = now
            self._last_update_ts = now
            self._last_seen_norm = _norm(body)
            self._repeat_count = 1
            self._last_emit_text = ""
            self._last_emit_ts = 0.0
            state = "FREEZE_FINAL" if mode_u == "FREEZE" else ("INTERVAL_NEW" if mode_u == "INTERVAL" else "AUTO_NEW")
            if mode_u == "FREEZE":
                self._mark_emit(body, now)
                return DialogueStabilityDecision(True, body, "freeze_new_turn_final", state, True, True, self._turn_id)
            # New Auto/Interval turn: show only if meaningful enough; otherwise keep last visual overlay.
            min_words = 2 if mode_u == "STABLE" else 3
            if len(_words(body)) >= min_words or len(body) >= 14:
                self._mark_emit(body, now)
                return DialogueStabilityDecision(True, body, "new_turn_meaningful", state, True, False, self._turn_id)
            return DialogueStabilityDecision(False, body, "new_turn_too_short_keep_last", "TYPING", True, False, self._turn_id)

        cmp = _norm(body)
        if cmp and cmp == self._last_seen_norm:
            self._repeat_count += 1
        else:
            self._repeat_count = 1
            self._last_seen_norm = cmp
            self._last_update_ts = now

        score = _quality_score(body)
        best_changed = False
        # No-downgrade: keep a longer/cleaner best source when OCR briefly regresses.
        if score > self._best_score + 3.0 or (len(body) > len(self._best) + 6 and _looks_same_turn(self._best, body)):
            self._best = body
            self._best_score = score
            best_changed = True
        elif len(body) + 8 < len(self._best) and _looks_same_turn(self._best, body):
            body = self._best

        best = self._best or body
        age_ms = int((now - (self._first_ts or now)) * 1000)
        since_emit_ms = int((now - self._last_emit_ts) * 1000) if self._last_emit_ts else 999999
        stable_ms = int((now - self._last_update_ts) * 1000)
        token_gain = max(0, len(_words(best)) - len(_words(self._last_emit_text))) if self._last_emit_text else len(_words(best))
        has_tail = bool(_TERMINAL_RE.search(best))
        same_as_emitted = _norm(best) and _norm(best) == _norm(self._last_emit_text)
        source_stable = self._repeat_count >= 2 or stable_ms >= (self.interval_stable_ms if mode_u == "INTERVAL" else self.auto_min_ms) or has_tail

        if same_as_emitted and since_emit_ms < self.duplicate_hold_ms:
            return DialogueStabilityDecision(False, best, "duplicate_best_keep_overlay", "DUPLICATE", best_changed, source_stable, self._turn_id)

        if mode_u == "FREEZE":
            self._mark_emit(best, now)
            return DialogueStabilityDecision(True, best, "freeze_final_best_source", "FREEZE_FINAL", best_changed, True, self._turn_id)

        if mode_u == "INTERVAL":
            if source_stable or has_tail or age_ms >= max(self.interval_stable_ms, 520) or token_gain >= self.interval_min_token_gain:
                self._mark_emit(best, now)
                return DialogueStabilityDecision(True, best, "interval_stable_best_source", "INTERVAL_STABLE", best_changed, source_stable, self._turn_id)
            return DialogueStabilityDecision(False, best, "interval_wait_stable_keep_overlay", "INTERVAL_WAIT", best_changed, False, self._turn_id)

        # Auto/STABLE: allow progressive updates, but coalesce tiny OCR changes.
        if has_tail or token_gain >= self.auto_min_token_gain or since_emit_ms >= self.auto_min_ms or source_stable:
            self._mark_emit(best, now)
            return DialogueStabilityDecision(True, best, "auto_smooth_best_source", "AUTO_SMOOTH", best_changed, source_stable, self._turn_id)
        return DialogueStabilityDecision(False, best, "auto_micro_wait_keep_overlay", "AUTO_SMOOTH_WAIT", best_changed, source_stable, self._turn_id)

    def _mark_emit(self, text: str, now: float) -> None:
        self._last_emit_text = str(text or "").strip()
        self._last_emit_ts = now
