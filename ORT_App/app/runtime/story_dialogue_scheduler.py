from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Optional


@dataclass
class SchedulerDecision:
    process: bool
    text: str
    reason: str
    state: str
    sleep_ms: int = 0


_TAIL_PUNCT_RE = re.compile(r"[.!?…。！？]['\")\]]*$")


def _norm_for_compare(text: str) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[|川州讦]+", "", s)
    return s


def _similar(a: str, b: str) -> float:
    a = _norm_for_compare(a)
    b = _norm_for_compare(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return min(len(a), len(b)) / max(1, max(len(a), len(b)))
    return SequenceMatcher(None, a, b).ratio()


def _is_growth(prev: str, cur: str) -> bool:
    """True when OCR text is probably the same dialog line still typing/growing."""
    p = _norm_for_compare(prev)
    c = _norm_for_compare(cur)
    if not p or not c:
        return False
    if c.startswith(p) or p.startswith(c):
        return True
    # OCR typos can slightly change the prefix while the line grows.
    short = min(len(p), len(c))
    if short < 10:
        return False
    prefix_score = SequenceMatcher(None, p[:short], c[:short]).ratio()
    return prefix_score >= 0.82 and abs(len(c) - len(p)) <= max(60, int(max(len(c), len(p)) * 0.65))


class StoryDialogueScheduler:
    """Translate scheduler for story/dialog OCR.

    v8.3.2 design notes:
    - Freeze = manual story click; commit immediately.
    - Interval = automated Freeze; wait briefly, but never hold forever while text is typing.
    - Auto = automatic story playback; use lighter stabilization and hash-gate cooperation.

    v8.2/v8.3 had a failure mode where Auto/Interval became too conservative after Fast CT2 work.
    v8.3.2 restores classic story flow: Auto commits progressively like a VN text feed, and
    Interval behaves as automated Freeze with quick commits instead of long typing holds.
    """

    def __init__(
        self,
        profile: str = "interval_auto",
        enabled: bool = True,
        min_age_ms: int = 180,
        min_repeats: int = 1,
        duplicate_hold_ms: int = 1800,
        max_wait_ms: int = 850,
        voice_hold_ms: int = 1800,
        quick_punct_commit: bool = True,
        progressive_commit: bool = False,
        classic_interval: bool = False,
        progressive_min_ms: int = 140,
        progressive_min_delta: int = 4,
    ):
        self.profile = str(profile or "interval_auto").lower()
        self.enabled = bool(enabled)
        self.min_age_ms = int(min_age_ms)
        self.min_repeats = int(min_repeats)
        self.duplicate_hold_ms = int(duplicate_hold_ms)
        self.max_wait_ms = int(max_wait_ms)
        self.voice_hold_ms = int(voice_hold_ms or duplicate_hold_ms)
        self.quick_punct_commit = bool(quick_punct_commit)
        self.progressive_commit = bool(progressive_commit)
        self.classic_interval = bool(classic_interval)
        self.progressive_min_ms = int(progressive_min_ms)
        self.progressive_min_delta = int(progressive_min_delta)
        self._last_seen = ""
        self._last_seen_ts = 0.0
        self._candidate_start_ts = 0.0
        self._last_change_ts = 0.0
        self._repeat_count = 0
        self._last_committed = ""
        self._last_commit_ts = 0.0

    @classmethod
    def from_env(cls) -> "StoryDialogueScheduler":
        profile = os.environ.get("ORT_DIALOG_SCHEDULER_PROFILE", "interval_auto").lower()
        enabled = os.environ.get("ORT_STORY_DIALOGUE_SCHEDULER", "1") != "0"
        if profile == "freeze_manual":
            min_age = int(os.environ.get("ORT_DIALOG_STABLE_MS", "0"))
            repeats = int(os.environ.get("ORT_DIALOG_STABLE_REPEATS", "1"))
            max_wait = int(os.environ.get("ORT_DIALOG_MAX_WAIT_MS", "0"))
        elif profile == "auto_story":
            min_age = int(os.environ.get("ORT_DIALOG_STABLE_MS", "100"))
            repeats = int(os.environ.get("ORT_DIALOG_STABLE_REPEATS", "1"))
            max_wait = int(os.environ.get("ORT_DIALOG_MAX_WAIT_MS", "650"))
        else:
            min_age = int(os.environ.get("ORT_DIALOG_STABLE_MS", "160"))
            repeats = int(os.environ.get("ORT_DIALOG_STABLE_REPEATS", "1"))
            max_wait = int(os.environ.get("ORT_DIALOG_MAX_WAIT_MS", "850"))
        dup_hold = int(os.environ.get("ORT_DIALOG_DUPLICATE_HOLD_MS", "1800"))
        voice_hold = int(os.environ.get("ORT_DIALOG_VOICE_HOLD_MS", str(dup_hold)))
        quick_punct = os.environ.get("ORT_DIALOG_QUICK_PUNCT_COMMIT", "1") != "0"
        progressive = os.environ.get("ORT_DIALOG_PROGRESSIVE_COMMIT", "1" if profile == "auto_story" else "0") != "0"
        classic_interval = os.environ.get("ORT_DIALOG_CLASSIC_INTERVAL", "0") != "0"
        progressive_min_ms = int(os.environ.get("ORT_DIALOG_PROGRESSIVE_MIN_MS", "140"))
        progressive_min_delta = int(os.environ.get("ORT_DIALOG_PROGRESSIVE_MIN_DELTA", "4"))
        return cls(profile=profile, enabled=enabled, min_age_ms=min_age, min_repeats=repeats, duplicate_hold_ms=dup_hold, max_wait_ms=max_wait, voice_hold_ms=voice_hold, quick_punct_commit=quick_punct, progressive_commit=progressive, classic_interval=classic_interval, progressive_min_ms=progressive_min_ms, progressive_min_delta=progressive_min_delta)

    def decide(self, text: str, *, mode: str = "", meta: Optional[Dict[str, Any]] = None) -> SchedulerDecision:
        meta = meta or {}
        text = str(text or "").strip()
        if not self.enabled or not text:
            return SchedulerDecision(bool(text), text, "disabled_or_empty", "BYPASS")
        mode_u = str(mode or "").upper()
        manual_freeze = bool(meta.get("manual_freeze")) or (mode_u == "FREEZE" and not bool(meta.get("auto_snapshot", False)))
        now = time.time()

        # Manual Freeze is expected to react to the user's click immediately.
        if self.profile == "freeze_manual" or manual_freeze:
            if self._last_committed and _similar(text, self._last_committed) >= 0.995 and (now - self._last_commit_ts) * 1000 < self.duplicate_hold_ms:
                return SchedulerDecision(False, text, "manual_duplicate_hold", "VOICE_HOLD", 0)
            self._commit(text, now)
            return SchedulerDecision(True, text, "manual_freeze_commit", "MANUAL_COMMIT")

        cmp = _norm_for_compare(text)
        last = _norm_for_compare(self._last_seen)
        if not cmp:
            return SchedulerDecision(False, text, "empty_after_norm", "EMPTY")

        if self._last_committed:
            similar_to_committed = _similar(text, self._last_committed)
            if similar_to_committed >= 0.990 and (now - self._last_commit_ts) * 1000 < max(self.duplicate_hold_ms, self.voice_hold_ms):
                return SchedulerDecision(False, text, "voice_hold_duplicate", "VOICE_HOLD", 90)
        else:
            similar_to_committed = 0.0

        # v8.8.2: Auto/Interval still follow story text, but tiny OCR deltas are coalesced
        # so the overlay does not flicker on every typewriter frame.
        if self.progressive_commit:
            since_commit_ms = int((now - self._last_commit_ts) * 1000) if self._last_commit_ts else 999999
            delta = abs(len(_norm_for_compare(text)) - len(_norm_for_compare(self._last_committed))) if self._last_committed else len(cmp)
            sim_commit = _similar(text, self._last_committed) if self._last_committed else 0.0
            min_delta = self.progressive_min_delta
            min_ms = self.progressive_min_ms
            if self.profile == "auto_story" and os.environ.get("ORT_AUTO_SMOOTH_MODE", "1") == "1":
                min_delta = max(min_delta, int(os.environ.get("ORT_AUTO_SMOOTH_MIN_CHAR_DELTA", "10")))
                min_ms = max(min_ms, int(os.environ.get("ORT_AUTO_SMOOTH_MIN_MS", "220")))
            if self.profile != "auto_story" and os.environ.get("ORT_INTERVAL_STABLE_MODE", "1") == "1":
                min_delta = max(min_delta, int(os.environ.get("ORT_INTERVAL_MIN_CHAR_DELTA", "14")))
                min_ms = max(min_ms, int(os.environ.get("ORT_INTERVAL_PROGRESSIVE_MIN_MS", "360")))
            if len(cmp) >= 8 and (not self._last_committed or sim_commit < 0.982) and delta >= min_delta and since_commit_ms >= min_ms:
                self._commit(text, now)
                state = "AUTO_SMOOTH_PROGRESS" if self.profile == "auto_story" else "INTERVAL_STORY_AWARE_COMMIT"
                return SchedulerDecision(True, text, "smooth_progressive_commit", state)

        if cmp == last:
            self._repeat_count += 1
        else:
            # Do not reset the whole timer if the OCR line is simply growing while the game types it.
            growth = _is_growth(self._last_seen, text)
            if not growth or self._candidate_start_ts <= 0:
                self._candidate_start_ts = now
            self._last_seen = text
            self._last_seen_ts = now
            self._last_change_ts = now
            self._repeat_count = 1

            if len(cmp) < 6:
                return SchedulerDecision(False, text, "too_short_wait", "TYPING", 30)

            candidate_age_ms = int((now - self._candidate_start_ts) * 1000)
            has_tail = bool(_TAIL_PUNCT_RE.search(text))
            long_enough = len(cmp) >= 12

            # Story-only/auto can commit at punctuation quickly.  Interval can also do this
            # after a short age so the overlay never stays blank while text is complete.
            if long_enough and has_tail and self.quick_punct_commit and candidate_age_ms >= max(60, min(self.min_age_ms, 140)):
                self._commit(text, now)
                return SchedulerDecision(True, text, "punct_commit_after_growth", "STABLE_TEXT")

            # Bounded fallback: commit latest meaningful text even if OCR keeps changing.
            # This is the v8.2.1 fix for the blank translation box in Interval mode.
            if long_enough and self.max_wait_ms > 0 and candidate_age_ms >= self.max_wait_ms:
                self._commit(text, now)
                return SchedulerDecision(True, text, f"max_wait_commit age={candidate_age_ms}", "STABLE_TEXT")

            return SchedulerDecision(False, text, f"text_changed_wait_stable age={candidate_age_ms}", "TYPING", min(70, max(20, self.min_age_ms)))

        candidate_age_ms = int((now - (self._candidate_start_ts or self._last_change_ts or now)) * 1000)
        age_ms = int((now - self._last_change_ts) * 1000)
        enough_repeats = self._repeat_count >= max(1, self.min_repeats)
        enough_age = age_ms >= max(0, self.min_age_ms)
        has_tail = bool(_TAIL_PUNCT_RE.search(text))
        long_enough = len(cmp) >= 12

        if long_enough and enough_repeats and (enough_age or has_tail or candidate_age_ms >= self.max_wait_ms):
            self._commit(text, now)
            return SchedulerDecision(True, text, "stable_commit", "STABLE_TEXT")

        if long_enough and self.max_wait_ms > 0 and candidate_age_ms >= self.max_wait_ms:
            self._commit(text, now)
            return SchedulerDecision(True, text, f"max_wait_commit age={candidate_age_ms}", "STABLE_TEXT")

        return SchedulerDecision(False, text, f"waiting_stable age={age_ms} candidate={candidate_age_ms} repeat={self._repeat_count}", "TYPING", min(70, max(10, self.min_age_ms - age_ms)))

    def _commit(self, text: str, now: float) -> None:
        self._last_committed = str(text or "").strip()
        self._last_commit_ts = now
        self._last_seen = self._last_committed
        self._last_seen_ts = now
        self._last_change_ts = now
        self._candidate_start_ts = now
        self._repeat_count = 0
