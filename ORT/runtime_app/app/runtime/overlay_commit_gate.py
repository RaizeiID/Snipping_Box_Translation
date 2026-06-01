"""ORT v8.8.6 Overlay Commit Gate.

v8.8.3 reduced flicker by suppressing render churn. v8.8.5 keeps that
visual stability but gives priority to completeness and never-empty behaviour:
- a longer/better final source may override minimum visible time;
- duplicate/cache hits do not render unless they complete the current turn;
- held/short/new-turn candidates keep the last visible subtitle instead of
  clearing the overlay;
- Freeze/Interval can behave as stable/final-first modes.

This is still a lightweight visual gate. It does not call any model and should
not add noticeable latency to Auto Story.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import time
from typing import Optional

from app.runtime.render_signature import (
    visual_signature,
    similarity,
    is_substantial_update,
    words,
    strip_html,
    terminal_punctuation,
    ocr_corruption_score,
)

@dataclass(frozen=True)
class OverlayCommitDecision:
    commit: bool
    reason: str
    state: str
    signature: str = ""
    force_visible: bool = False


class OverlayCommitGate:
    def __init__(
        self,
        *,
        min_visible_ms: int = 480,
        min_token_gain: int = 3,
        similar_threshold: float = 0.92,
        final_override: bool = True,
        never_empty: bool = True,
        complete_source_override: bool = True,
    ) -> None:
        self.min_visible_ms = max(0, int(min_visible_ms))
        self.min_token_gain = max(1, int(min_token_gain))
        self.similar_threshold = float(similar_threshold)
        self.final_override = bool(final_override)
        self.never_empty = bool(never_empty)
        self.complete_source_override = bool(complete_source_override)
        self.last_speaker_html = ""
        self.last_dialog_html = ""
        self.last_plain = ""
        self.last_source = ""
        self.last_turn_id = ""
        self.last_signature = ""
        self.last_commit_ts = 0.0
        self.last_commit_state = ""

    @classmethod
    def from_env(cls) -> "OverlayCommitGate":
        mode = os.environ.get("ORT_UI_REQUESTED_MODE", os.environ.get("ORT_BOOT_MODE", "auto")).lower()
        group = os.environ.get("ORT_MODEL_GROUP", "").lower()
        recording = os.environ.get("ORT_GFL2_RECORDING_PROFILE", "1") == "1"
        default_min = 500 if recording else 420
        if group == "fast":
            default_min = 560 if recording else 460
        elif group == "lite":
            default_min = 620 if recording else 520
        if mode == "interval":
            default_min = 850
        elif mode == "freeze":
            default_min = 0
        return cls(
            min_visible_ms=int(os.environ.get("ORT_OVERLAY_MIN_VISIBLE_MS", str(default_min))),
            min_token_gain=int(os.environ.get("ORT_OVERLAY_MIN_TOKEN_GAIN", "3")),
            similar_threshold=float(os.environ.get("ORT_OVERLAY_SIMILARITY_THRESHOLD", "0.92")),
            final_override=os.environ.get("ORT_OVERLAY_FINAL_OVERRIDE", "1") != "0",
            never_empty=os.environ.get("ORT_OVERLAY_NEVER_EMPTY", "1") != "0",
            complete_source_override=os.environ.get("ORT_OVERLAY_COMPLETE_SOURCE_OVERRIDE", "1") != "0",
        )

    def reset(self, *, clear_visible: bool = False) -> None:
        self.last_turn_id = ""
        self.last_source = ""
        self.last_commit_state = ""
        if clear_visible:
            self.last_speaker_html = ""
            self.last_dialog_html = ""
            self.last_plain = ""
            self.last_signature = ""
            self.last_commit_ts = 0.0

    def has_visible(self) -> bool:
        return bool(self.last_dialog_html or self.last_plain)

    def last_visible_payload(self) -> tuple[str, str]:
        return self.last_speaker_html, self.last_dialog_html

    def _source_substantial(self, source: str) -> bool:
        if not source:
            return False
        if not self.last_source:
            return True
        if terminal_punctuation(source) and len(source) >= max(12, len(self.last_source) - 4):
            return True
        if is_substantial_update(self.last_source, source, min_token_gain=self.min_token_gain, min_char_gain=16):
            return True
        return False

    def decide(
        self,
        *,
        speaker_html: str,
        dialog_html: str,
        plain_translation: str,
        source_text: str,
        speaker: str = "",
        turn_id: str = "",
        mode: str = "",
        engine: str = "",
        cache: str = "",
        trusted_preview: bool = False,
        final: bool = False,
        held: bool = False,
        source_stable: bool = False,
        force_complete: bool = False,
        dialogue_state: str = "",
    ) -> OverlayCommitDecision:
        now = time.time()
        plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        source = str(source_text or "").strip()
        turn_id = str(turn_id or "").strip()
        sig = visual_signature(plain)
        mode_u = str(mode or "").upper()
        cache_u = str(cache or "").upper()
        state_u = str(dialogue_state or "").upper()

        if mode_u == "FREEZE":
            return OverlayCommitDecision(True, "freeze_final_commit", "FREEZE", sig)
        if not plain:
            return OverlayCommitDecision(False, "empty_plain_keep_last", "EMPTY", sig, force_visible=self.never_empty)
        if held:
            return OverlayCommitDecision(False, "held_keep_last", "HELD", sig, force_visible=self.never_empty)

        new_turn = bool(turn_id and turn_id != self.last_turn_id)
        elapsed_ms = int((now - self.last_commit_ts) * 1000) if self.last_commit_ts else 999999
        same_html = dialog_html == self.last_dialog_html and speaker_html == self.last_speaker_html
        source_gain = self._source_substantial(source)
        output_gain = is_substantial_update(self.last_plain, plain, min_token_gain=max(1, self.min_token_gain - 1), min_char_gain=14)
        complete_like = bool(final or force_complete or source_stable or state_u in {"FINAL_COMPLETE", "FINAL_READY", "INTERVAL_STABLE", "FREEZE_FINAL", "MANDATORY_FINAL"} or terminal_punctuation(source))
        source_longer_valid = bool(source_gain and len(words(source)) >= 3 and ocr_corruption_score(source) <= 0.72)
        completeness_override = bool(self.complete_source_override and (source_gain or output_gain) and (complete_like or source_longer_valid))

        if force_complete:
            return OverlayCommitDecision(True, "mandatory_final_override", "FINAL_COMPLETE", sig)
        if same_html and not completeness_override:
            return OverlayCommitDecision(False, "same_html_no_render", "DUPLICATE", sig)
        if sig and sig == self.last_signature and not completeness_override:
            return OverlayCommitDecision(False, "same_render_signature_no_render", "DUPLICATE", sig)
        if cache_u in {"HIT_STABLE_FINAL", "DUPLICATE_OCR_SUPPRESSED"} and similarity(plain, self.last_plain) >= self.similar_threshold and not completeness_override:
            return OverlayCommitDecision(False, "cache_duplicate_no_render", "DUPLICATE", sig)

        if new_turn:
            # v8.8.6: do not let noisy turn-id churn dominate the overlay.
            # A new-turn preview may commit only when meaningful or final-ready;
            # otherwise repaint/keep last good until this turn has enough content.
            if len(words(plain)) < 2 and len(strip_html(plain)) < 14:
                return OverlayCommitDecision(False, "new_turn_too_short_keep_last", "NEW_TURN_WAIT", sig, force_visible=self.never_empty)
            if completeness_override or source_stable or terminal_punctuation(source) or len(words(plain)) >= 6:
                return OverlayCommitDecision(True, "new_turn_meaningful_commit", "NEW_TURN", sig)
            if elapsed_ms < max(220, int(self.min_visible_ms * 0.55)):
                return OverlayCommitDecision(False, "new_turn_wait_for_complete", "NEW_TURN_WAIT", sig, force_visible=self.never_empty)
            return OverlayCommitDecision(True, "new_turn_progress_commit", "NEW_TURN", sig)

        if self.last_plain:
            sim = similarity(plain, self.last_plain)
            shorter = len(strip_html(plain)) + 12 < len(strip_html(self.last_plain))
            if shorter and not complete_like:
                return OverlayCommitDecision(False, "shorter_preview_no_downgrade", "NO_DOWNGRADE", sig, force_visible=self.never_empty)
            # v8.8.6: complete/longer source wins over min-visible.
            if completeness_override:
                reason = "source_longer_must_win" if source_longer_valid and not complete_like else "final_complete_override"
                return OverlayCommitDecision(True, reason, "FINAL_COMPLETE", sig)
            if elapsed_ms < self.min_visible_ms:
                if sim >= 0.72 or not output_gain:
                    return OverlayCommitDecision(False, "min_visible_keep_last", "MIN_VISIBLE", sig, force_visible=self.never_empty)
            if sim >= self.similar_threshold and not output_gain and not (final and self.final_override):
                return OverlayCommitDecision(False, "similar_small_change_no_render", "SIMILAR", sig, force_visible=self.never_empty)

        if final and self.final_override:
            if output_gain or source_gain or len(strip_html(plain)) >= len(strip_html(self.last_plain)):
                return OverlayCommitDecision(True, "final_completeness_commit", "FINAL", sig)
        if trusted_preview:
            return OverlayCommitDecision(True, "trusted_preview_commit", "PREVIEW", sig)
        return OverlayCommitDecision(True, "meaningful_commit", "COMMIT", sig)

    def mark_committed(self, *, speaker_html: str, dialog_html: str, plain_translation: str, source_text: str, turn_id: str = "", signature: str = "", state: str = "") -> None:
        self.last_speaker_html = speaker_html
        self.last_dialog_html = dialog_html
        self.last_plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        self.last_source = str(source_text or "").strip()
        self.last_turn_id = str(turn_id or "").strip()
        self.last_signature = signature or visual_signature(self.last_plain)
        self.last_commit_state = str(state or "")
        self.last_commit_ts = time.time()
