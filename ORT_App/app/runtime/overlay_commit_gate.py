"""ORT v8.9.2 transactional overlay commit gate.

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

def _normalise_for_growth(value: str) -> str:
    """Lowercase alphanumerics only, so OCR punctuation churn is ignored."""
    return " ".join("".join(ch if ch.isalnum() else " " for ch in str(value or "").lower()).split())


def _is_progressive_growth(previous: str, current: str, *, min_gain: int = 6, anchor: int = 16) -> bool:
    """True when `current` continues `previous` rather than replacing it.

    Deliberately anchored on the TAIL of the previous text rather than a plain
    startswith. Progressive game dialogue is captured with unstable leading
    noise -- the field log shows the same line arriving as "u Lentine War. War",
    then "Lentine War. War never changes", then "ar. War never changes. Only by
    maintaining..." -- so the beginning cannot be relied on. What is stable is
    that whatever was already on screen still appears, followed by more text.

    Conservative on purpose: a genuinely new sentence shares no tail with the
    old one and stays locked, which is what keeps the single-final protection
    meaningful for real turn changes.
    """
    old = _normalise_for_growth(previous)
    new = _normalise_for_growth(current)
    if not old or not new:
        return False
    tail = (old[-anchor:] if len(old) > anchor else old).strip()
    if not tail:
        return False
    position = new.find(tail)
    if position < 0:
        return False
    # Measure what was APPENDED after the anchor, not the change in total
    # length. The leading noise varies in size between frames ("Lentine War."
    # becoming "ar."), so a whole-string comparison can show a net gain of one
    # character while nine characters of real dialogue actually arrived.
    appended = new[position + len(tail):].strip()
    return len(appended) >= min_gain


# How long the finished line must have been on screen before a different line is
# allowed to replace it inside the same turn. Field gaps between real successive
# lines were 1-4 s; frames inside one typewriter burst are a few hundred ms.
_REPLACEMENT_SETTLE_MS = int(os.environ.get("ORT_OVERLAY_REPLACEMENT_SETTLE_MS", "800"))


def _is_distinct_source_line(previous: str, current: str, *, max_similarity: float = 0.55, min_words: int = 2) -> bool:
    """True when `current` is a different on-screen line, not a re-render of `previous`.

    ORT_V9_0_7_R12. The single-final lock is aimed at one case: the translator
    returning a new phrasing of the SAME source. It must not swallow a genuinely
    new line, but it did, because the turn state machine sometimes keeps one
    turn_id across a dialogue change. Field log 10:25:24 -> 10:25:30: the turn
    finalised on "Today's workload has definitely exceeded all my limits", then
    "Amid the chaos, I quickly locate the central control terminal inside the
    base" arrived with no new turn_id, and all four of its frames were dropped as
    `single_final_per_turn_locked`. That whole sentence never reached the player.

    Growth is handled by _is_progressive_growth; this covers replacement. Kept
    conservative: a re-phrased translation of the same source scores far above
    the threshold and stays locked, so the anti-flicker guarantee is unchanged.
    """
    prev = _normalise_for_growth(previous)
    cur = _normalise_for_growth(current)
    if not prev or not cur:
        return False
    if len(cur.split()) < min_words:
        return False
    if _is_progressive_growth(previous, current):
        return False
    return similarity(prev, cur) < max_similarity


@dataclass(frozen=True)
class OverlayCommitDecision:
    commit: bool
    reason: str
    state: str
    signature: str = ""
    force_visible: bool = False
    final: bool = False


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
        self.last_generation_id = 0
        self.last_signature = ""
        self.last_commit_ts = 0.0
        self.last_commit_state = ""
        self.final_turns: dict[str, str] = {}
        self.commit_counts: dict[str, int] = {}
        self.final_commit_counts: dict[str, int] = {}

    @classmethod
    def from_env(cls) -> "OverlayCommitGate":
        mode = os.environ.get("ORT_UI_REQUESTED_MODE", os.environ.get("ORT_BOOT_MODE", "auto")).lower()
        group = os.environ.get("ORT_MODEL_GROUP", "").lower()
        recording = os.environ.get("ORT_GFL2_RECORDING_PROFILE", "1") == "1"
        default_min = 420 if recording else 360
        if group == "fast":
            default_min = 460 if recording else 380
        elif group == "lite":
            default_min = 520 if recording else 440
        if mode == "interval":
            default_min = 620
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
        self.last_generation_id = 0
        self.last_source = ""
        self.last_commit_state = ""
        if clear_visible:
            self.last_speaker_html = ""
            self.last_dialog_html = ""
            self.last_plain = ""
            self.last_signature = ""
            self.last_commit_ts = 0.0
            self.final_turns.clear()
            self.commit_counts.clear()
            self.final_commit_counts.clear()

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
        generation_id: int = 0,
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
        elapsed_ms = int((now - self.last_commit_ts) * 1000) if self.last_commit_ts else 999999
        plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        source = str(source_text or "").strip()
        turn_id = str(turn_id or "").strip()
        generation_id = max(0, int(generation_id or 0))
        sig = visual_signature(plain)
        mode_u = str(mode or "").upper()
        cache_u = str(cache or "").upper()
        state_u = str(dialogue_state or "").upper()

        if turn_id and turn_id == self.last_turn_id and generation_id and generation_id < self.last_generation_id:
            return OverlayCommitDecision(False, "stale_generation_rejected", "STALE", sig, force_visible=self.never_empty)
        if not plain:
            return OverlayCommitDecision(False, "empty_plain_keep_last", "EMPTY", sig, force_visible=self.never_empty)
        if held:
            return OverlayCommitDecision(False, "held_keep_last", "HELD", sig, force_visible=self.never_empty)
        if turn_id and turn_id in self.final_turns:
            if sig and sig == self.final_turns[turn_id]:
                return OverlayCommitDecision(False, "final_duplicate_locked", "FINAL_LOCKED", sig, force_visible=self.never_empty)
            # ORT_V9_0_7_R11: PROGRESSIVE_TYPEWRITER
            # The single-final lock exists to stop a turn re-rendering when the
            # translator returns a different phrasing of the SAME sentence. In
            # GFL2 auto-story the dialogue is typed out progressively, so a turn
            # keeps growing after the first final was committed -- and this lock
            # was discarding every later step. Field log: 63 suppressed against
            # 34 committed, all `single_final_per_turn_locked`, so roughly two
            # thirds of the typewriter never reached the overlay.
            #
            # Growth is not a re-render: if the new source strictly extends what
            # was already shown, it is new dialogue the player can see on screen
            # and must be translated too. Only non-growing variants stay locked.
            if _is_progressive_growth(self.last_source, source):
                return OverlayCommitDecision(
                    True, "progressive_growth_after_final", "PROGRESSIVE", sig,
                    final=False,
                )
            # The replacement must also have let the finished line be readable
            # first. R11 deliberately refuses unrelated text inside a turn, and
            # that protection is what stops a stray OCR read of another UI
            # element from replacing live dialogue mid-burst. A real successor
            # line does not arrive in the same breath as the final it replaces:
            # in the field log the gap was ~4 s, while spurious reads land inside
            # the same typewriter burst. Gating on visible time keeps R11's
            # refusal intact and still lets genuine dialogue through.
            settle_ms = max(self.min_visible_ms, _REPLACEMENT_SETTLE_MS)
            if not _is_distinct_source_line(self.last_source, source) or elapsed_ms < settle_ms:
                return OverlayCommitDecision(False, "single_final_per_turn_locked", "FINAL_LOCKED", sig, force_visible=self.never_empty)
            # ORT_V9_0_7_R12: the lock belonged to the sentence that just ended.
            # A different line is on screen now, so retire the lock and let this
            # frame take the new-turn path below -- that path is what applies the
            # short-source wait and lets the line finalise on its own terms.
            # Without the new_turn override it would fall into the same-turn
            # branch and be rejected by `shorter_preview_no_downgrade`, because a
            # freshly typed line is shorter than the finished one before it.
            self.final_turns.pop(turn_id, None)
            stale_final_lock_retired = True
        else:
            stale_final_lock_retired = False

        new_turn = bool(turn_id and turn_id != self.last_turn_id) or stale_final_lock_retired
        elapsed_ms = int((now - self.last_commit_ts) * 1000) if self.last_commit_ts else 999999
        same_html = dialog_html == self.last_dialog_html and speaker_html == self.last_speaker_html
        source_gain = self._source_substantial(source)
        output_gain = is_substantial_update(self.last_plain, plain, min_token_gain=max(1, self.min_token_gain - 1), min_char_gain=14)
        complete_like = bool(final or force_complete or source_stable or state_u in {"FINAL_COMPLETE", "FINAL_READY", "INTERVAL_STABLE", "FREEZE_FINAL", "MANDATORY_FINAL"} or terminal_punctuation(source))
        final_candidate = bool(final and not trusted_preview and (force_complete or source_stable or state_u in {"FINAL_COMPLETE", "FINAL_READY", "INTERVAL_STABLE", "FREEZE_FINAL", "MANDATORY_FINAL"} or terminal_punctuation(source)))
        source_longer_valid = bool(source_gain and len(words(source)) >= 3 and ocr_corruption_score(source) <= 0.72)
        completeness_override = bool(self.complete_source_override and (source_gain or output_gain) and (complete_like or source_longer_valid))

        if mode_u == "FREEZE":
            return OverlayCommitDecision(True, "freeze_final_commit", "FREEZE", sig, final=True)
        if force_complete and final and not trusted_preview:
            return OverlayCommitDecision(True, "mandatory_final_override", "FINAL_COMPLETE", sig, final=True)
        if same_html and not completeness_override:
            return OverlayCommitDecision(False, "same_html_no_render", "DUPLICATE", sig)
        if sig and sig == self.last_signature and not completeness_override:
            return OverlayCommitDecision(False, "same_render_signature_no_render", "DUPLICATE", sig)
        if cache_u in {"HIT_STABLE_FINAL", "DUPLICATE_OCR_SUPPRESSED"} and similarity(plain, self.last_plain) >= self.similar_threshold and not completeness_override:
            return OverlayCommitDecision(False, "cache_duplicate_no_render", "DUPLICATE", sig)

        if new_turn:
            if len(words(plain)) < 2 and len(strip_html(plain)) < 12:
                return OverlayCommitDecision(False, "new_turn_too_short_wait_source", "NEW_TURN_WAIT", sig, force_visible=self.never_empty)
            if final_candidate:
                return OverlayCommitDecision(True, "new_turn_final_atomic_swap", "FINAL", sig, final=True)
            if completeness_override or len(words(plain)) >= 4 or len(words(source)) >= 4:
                return OverlayCommitDecision(True, "new_turn_preview_atomic_swap", "PREVIEW", sig)
            if elapsed_ms < max(120, int(self.min_visible_ms * 0.35)):
                return OverlayCommitDecision(False, "new_turn_short_wait_source", "NEW_TURN_WAIT", sig, force_visible=self.never_empty)
            return OverlayCommitDecision(True, "new_turn_progress_preview", "PREVIEW", sig)

        if self.last_plain:
            sim = similarity(plain, self.last_plain)
            shorter = len(strip_html(plain)) + 12 < len(strip_html(self.last_plain))
            if shorter and not complete_like:
                return OverlayCommitDecision(False, "shorter_preview_no_downgrade", "NO_DOWNGRADE", sig, force_visible=self.never_empty)
            # v8.8.8-r2: complete/longer source wins over min-visible.
            if completeness_override:
                reason = "source_longer_must_win" if source_longer_valid and not complete_like else "final_complete_override"
                state = "FINAL_COMPLETE"
                return OverlayCommitDecision(True, reason, state, sig, final=final_candidate)
            if elapsed_ms < self.min_visible_ms:
                if sim >= 0.72 or not output_gain:
                    return OverlayCommitDecision(False, "min_visible_keep_last", "MIN_VISIBLE", sig, force_visible=self.never_empty)
            if sim >= self.similar_threshold and not output_gain and not (final and self.final_override):
                return OverlayCommitDecision(False, "similar_small_change_no_render", "SIMILAR", sig, force_visible=self.never_empty)

        if final_candidate and self.final_override:
            if output_gain or source_gain or len(strip_html(plain)) >= len(strip_html(self.last_plain)):
                return OverlayCommitDecision(True, "final_completeness_commit", "FINAL", sig, final=True)
        if trusted_preview:
            return OverlayCommitDecision(True, "trusted_preview_commit", "PREVIEW", sig)
        return OverlayCommitDecision(True, "meaningful_preview_commit", "PREVIEW", sig)

    def mark_committed(self, *, speaker_html: str, dialog_html: str, plain_translation: str, source_text: str, turn_id: str = "", generation_id: int = 0, signature: str = "", state: str = "", final: bool = False) -> None:
        self.last_speaker_html = speaker_html
        self.last_dialog_html = dialog_html
        self.last_plain = str(plain_translation or strip_html(dialog_html) or "").strip()
        self.last_source = str(source_text or "").strip()
        self.last_turn_id = str(turn_id or "").strip()
        self.last_generation_id = max(0, int(generation_id or 0))
        self.last_signature = signature or visual_signature(self.last_plain)
        self.last_commit_state = str(state or "")
        self.last_commit_ts = time.time()
        if self.last_turn_id:
            self.commit_counts[self.last_turn_id] = self.commit_counts.get(self.last_turn_id, 0) + 1
            if final:
                self.final_turns[self.last_turn_id] = self.last_signature
                self.final_commit_counts[self.last_turn_id] = self.final_commit_counts.get(self.last_turn_id, 0) + 1
            if len(self.commit_counts) > 256:
                oldest = next(iter(self.commit_counts))
                self.commit_counts.pop(oldest, None)
                self.final_commit_counts.pop(oldest, None)
                self.final_turns.pop(oldest, None)
