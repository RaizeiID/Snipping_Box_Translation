"""v8.7.2 stable-final cache policy for progressive visual-novel dialogue.

The live overlay may translate progressive prefixes, but the persistent cache must
only keep the latest stable/final line.  This module is intentionally translation-
backend agnostic and keeps a tiny in-session memo for identical OCR frames.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Optional

from app.translation.fuzzy_cache_normalizer import normalize_cache_key
from app.translation.critical_token_guard import can_commit_final


@dataclass
class FinalCandidate:
    source: str
    key: str
    output: str = ""
    engine: str = ""
    first_seen: float = 0.0
    last_seen: float = 0.0
    repeats: int = 1


@dataclass
class CachePlan:
    key: str
    relation: str
    reuse_output: str = ""
    previous_to_commit: Optional[FinalCandidate] = None
    store_current_immediately: bool = False
    reason: str = ""


class StableFinalCachePolicy:
    """Track one growing dialogue and expose safe final-store decisions."""

    def __init__(self) -> None:
        self.enabled = os.environ.get("ORT_STABLE_FINAL_CACHE_V2", "1") != "0"
        self.memo_enabled = os.environ.get("ORT_CURRENT_DIALOG_MEMO", "1") != "0"
        self.requested_mode = os.environ.get("ORT_UI_REQUESTED_MODE", os.environ.get("ORT_BOOT_MODE", "auto")).lower()
        self.min_final_len = int(os.environ.get("ORT_STABLE_FINAL_MIN_LEN", "14"))
        self.candidate: Optional[FinalCandidate] = None

    @staticmethod
    def _related_progressive(old_key: str, new_key: str) -> bool:
        if not old_key or not new_key:
            return False
        if old_key == new_key:
            return True
        shorter, longer = sorted((old_key, new_key), key=len)
        # OCR punctuation/casing is normalized before this point.  Require a
        # meaningful shared prefix so unrelated short lines are not grouped.
        return len(shorter) >= 6 and longer.startswith(shorter)

    def _eligible(self, item: Optional[FinalCandidate]) -> bool:
        if not item or not item.output:
            return False
        if len(item.key) < self.min_final_len:
            return False
        if item.source.rstrip().endswith(("...", "…")):
            return False
        stable, _reason = can_commit_final(item.source)
        if not stable:
            return False
        return True

    def prepare(self, source: str) -> CachePlan:
        key = normalize_cache_key(source)
        now = time.time()
        if not self.enabled:
            return CachePlan(key=key, relation="disabled", store_current_immediately=True, reason="stable_final_disabled")
        # Freeze/Interval is explicit snapshot behavior.  It is safe to store
        # the committed translation immediately; Auto gets final-only storage.
        is_auto = self.requested_mode == "auto"
        if self.candidate is None:
            self.candidate = FinalCandidate(source=source, key=key, first_seen=now, last_seen=now)
            return CachePlan(key=key, relation="new", store_current_immediately=not is_auto, reason="new_candidate")
        current = self.candidate
        if key == current.key:
            current.repeats += 1
            current.last_seen = now
            reuse = current.output if self.memo_enabled else ""
            return CachePlan(key=key, relation="duplicate", reuse_output=reuse, store_current_immediately=(not is_auto or current.repeats >= 2), reason="same_normalized_text")
        if self._related_progressive(current.key, key):
            # Keep the longest observed text as the final candidate; short OCR
            # regressions should not replace a fuller sentence.
            if len(key) >= len(current.key):
                self.candidate = FinalCandidate(source=source, key=key, first_seen=current.first_seen, last_seen=now)
            return CachePlan(key=key, relation="progressive", store_current_immediately=not is_auto, reason="text_growing")
        previous = current if self._eligible(current) else None
        self.candidate = FinalCandidate(source=source, key=key, first_seen=now, last_seen=now)
        return CachePlan(key=key, relation="new_dialog", previous_to_commit=previous, store_current_immediately=not is_auto, reason="dialog_changed")

    def observe_translation(self, source: str, output: str, engine: str) -> None:
        if not self.candidate:
            return
        key = normalize_cache_key(source)
        if key == self.candidate.key:
            self.candidate.output = str(output or "")
            self.candidate.engine = str(engine or "")
            self.candidate.last_seen = time.time()

    def candidate_for_flush(self) -> Optional[FinalCandidate]:
        return self.candidate if self._eligible(self.candidate) else None
