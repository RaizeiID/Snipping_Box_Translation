"""ORT v8.8.3 Overlay Commit Gate.

This is a visual/render gate, not a heavy translation/safety gate.  OCR and
translation can continue quickly, but the overlay is only replaced when the new
payload is visually meaningful or final/complete enough.  This reduces flicker
without returning to v8.7.8-style long holds.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Optional

from app.runtime.render_signature import visual_signature, similarity, is_substantial_update, words, strip_html

@dataclass(frozen=True)
class OverlayCommitDecision:
    commit: bool
    reason: str
    state: str
    signature: str = ""


class OverlayCommitGate:
    def __init__(
        self,
        *,
        min_visible_ms: int = 500,
        min_token_gain: int = 3,
        similar_threshold: float = 0.92,
        final_override: bool = True,
    ) -> None:
        self.min_visible_ms = max(80, int(min_visible_ms))
        self.min_token_gain = max(1, int(min_token_gain))
        self.similar_threshold = float(similar_threshold)
        self.final_override = bool(final_override)
        self.last_speaker_html = ""
        self.last_dialog_html = ""
        self.last_plain = ""
        self.last_source = ""
        self.last_turn_id = ""
        self.last_signature = ""
        self.last_commit_ts = 0.0

    @classmethod
    def from_env(cls) -> "OverlayCommitGate":
        mode = os.environ.get("ORT_UI_REQUESTED_MODE", os.environ.get("ORT_BOOT_MODE", "auto")).lower()
        group = os.environ.get("ORT_MODEL_GROUP", "").lower()
        default_min = 500
        if group == "fast":
            default_min = 620
        elif group == "lite":
            default_min = 650
        if mode == "interval":
            default_min = 900
        elif mode == "freeze":
            default_min = 0
        return cls(
            min_visible_ms=int(os.environ.get("ORT_OVERLAY_MIN_VISIBLE_MS", str(default_min))),
            min_token_gain=int(os.environ.get("ORT_OVERLAY_MIN_TOKEN_GAIN", "3")),
            similar_threshold=float(os.environ.get("ORT_OVERLAY_SIMILARITY_THRESHOLD", "0.92")),
            final_override=os.environ.get("ORT_OVERLAY_FINAL_OVERRIDE", "1") != "0",
        )

    def reset(self, *, clear_visible: bool = False) -> None:
        self.last_turn_id = ""
        self.last_source = ""
        if clear_visible:
            self.last_speaker_html = ""
            self.last_dialog_html = ""
            self.last_plain = ""
            self.last_signature = ""
            self.last_commit_ts = 0.0

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
    ) -> OverlayCommitDecision:
        now = time.time()
        plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        source = str(source_text or "").strip()
        turn_id = str(turn_id or "").strip()
        sig = visual_signature(plain)
        mode_u = str(mode or "").upper()
        cache_u = str(cache or "").upper()
        if mode_u == "FREEZE":
            return OverlayCommitDecision(True, "freeze_final_commit", "FREEZE", sig)
        if not plain:
            return OverlayCommitDecision(False, "empty_plain_keep_last", "EMPTY", sig)
        if held:
            return OverlayCommitDecision(False, "held_keep_last", "HELD", sig)
        new_turn = bool(turn_id and turn_id != self.last_turn_id)
        elapsed_ms = int((now - self.last_commit_ts) * 1000) if self.last_commit_ts else 999999
        same_html = dialog_html == self.last_dialog_html and speaker_html == self.last_speaker_html
        if same_html:
            return OverlayCommitDecision(False, "same_html_no_render", "DUPLICATE", sig)
        if sig and sig == self.last_signature:
            return OverlayCommitDecision(False, "same_render_signature_no_render", "DUPLICATE", sig)
        if cache_u in {"HIT_STABLE_FINAL", "DUPLICATE_OCR_SUPPRESSED"} and similarity(plain, self.last_plain) >= self.similar_threshold:
            return OverlayCommitDecision(False, "cache_duplicate_no_render", "DUPLICATE", sig)
        if new_turn:
            # For a new turn, allow meaningful payloads immediately. Very short/source-noisy
            # candidates are already handled by the accumulator; keep old visible otherwise.
            if len(words(plain)) < 2 and len(strip_html(plain)) < 14:
                return OverlayCommitDecision(False, "new_turn_too_short_keep_last", "NEW_TURN_WAIT", sig)
            return OverlayCommitDecision(True, "new_turn_meaningful_commit", "NEW_TURN", sig)
        if self.last_plain:
            sim = similarity(plain, self.last_plain)
            substantial = is_substantial_update(self.last_plain, plain, min_token_gain=self.min_token_gain)
            shorter = len(strip_html(plain)) + 12 < len(strip_html(self.last_plain))
            if shorter and not final:
                return OverlayCommitDecision(False, "shorter_preview_no_downgrade", "NO_DOWNGRADE", sig)
            if elapsed_ms < self.min_visible_ms and not (final and self.final_override and substantial):
                if sim >= 0.78 or not substantial:
                    return OverlayCommitDecision(False, "min_visible_keep_last", "MIN_VISIBLE", sig)
            if sim >= self.similar_threshold and not substantial and not (final and self.final_override):
                return OverlayCommitDecision(False, "similar_small_change_no_render", "SIMILAR", sig)
        if final and self.final_override:
            if is_substantial_update(self.last_plain, plain, min_token_gain=1) or len(strip_html(plain)) >= len(strip_html(self.last_plain)):
                return OverlayCommitDecision(True, "final_completeness_commit", "FINAL", sig)
        if trusted_preview:
            return OverlayCommitDecision(True, "trusted_preview_commit", "PREVIEW", sig)
        return OverlayCommitDecision(True, "meaningful_commit", "COMMIT", sig)

    def mark_committed(self, *, speaker_html: str, dialog_html: str, plain_translation: str, source_text: str, turn_id: str = "", signature: str = "") -> None:
        self.last_speaker_html = speaker_html
        self.last_dialog_html = dialog_html
        self.last_plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        self.last_source = str(source_text or "").strip()
        self.last_turn_id = str(turn_id or "").strip()
        self.last_signature = signature or visual_signature(self.last_plain)
        self.last_commit_ts = time.time()
