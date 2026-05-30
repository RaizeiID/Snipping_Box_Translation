from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass
class StableCommitResult:
    commit: bool
    text: str
    reason: str = ""
    repeats: int = 0

class StableTextCommitter:
    """Small OCR debounce gate.

    v8.1 behavior:
    - commit repeated text quickly;
    - commit a stable single text after min_age_ms;
    - ignore very short/empty text;
    - reset manually when capture area/mode changes if needed.
    """
    def __init__(self, min_age_ms: int = 180, min_repeats: int = 2):
        self.min_age_ms = max(0, int(min_age_ms))
        self.min_repeats = max(1, int(min_repeats))
        self._last = ""
        self._first_seen = 0.0
        self._repeats = 0
        self._last_commit = ""

    def reset(self) -> None:
        self._last = ""
        self._first_seen = 0.0
        self._repeats = 0
        self._last_commit = ""

    def update(self, text: str) -> StableCommitResult:
        now = time.time() * 1000
        t = (text or "").strip()
        if not t or len(t) < 2:
            return StableCommitResult(False, t, "empty/too_short", self._repeats)
        if t == self._last:
            self._repeats += 1
        else:
            self._last = t
            self._first_seen = now
            self._repeats = 1
            return StableCommitResult(False, t, "new_text_waiting", self._repeats)
        if t == self._last_commit:
            return StableCommitResult(False, t, "already_committed", self._repeats)
        if self._repeats >= self.min_repeats or (now - self._first_seen) >= self.min_age_ms:
            self._last_commit = t
            return StableCommitResult(True, t, "stable", self._repeats)
        return StableCommitResult(False, t, "debounce", self._repeats)
