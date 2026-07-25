from __future__ import annotations

from dataclasses import dataclass
import os
import time


@dataclass
class PreloadBarrier:
    """Tracks the two long-lived workers required before Lab capture may start."""

    translator_ready: bool = False
    asr_ready: bool = False
    activated: bool = False
    started_at: float = 0.0

    def begin(self, now: float | None = None) -> None:
        self.translator_ready = False
        self.asr_ready = False
        self.activated = False
        self.started_at = float(time.monotonic() if now is None else now)

    def mark_translator_ready(self) -> bool:
        self.translator_ready = True
        return self._activate_if_ready()

    def mark_asr_ready(self) -> bool:
        self.asr_ready = True
        return self._activate_if_ready()

    def _activate_if_ready(self) -> bool:
        if self.activated or not (self.translator_ready and self.asr_ready):
            return False
        self.activated = True
        return True

    def elapsed_ms(self, now: float | None = None) -> int:
        if self.started_at <= 0:
            return 0
        current = float(time.monotonic() if now is None else now)
        return max(0, int((current - self.started_at) * 1000.0))


@dataclass(frozen=True)
class TranslationWatchdogPolicy:
    timeout_s: float
    poll_s: float = 0.25

    @classmethod
    def for_profile(cls, profile: str) -> "TranslationWatchdogPolicy":
        override = str(os.environ.get("ORT_TRANSLATION_WATCHDOG_SECONDS", "") or "").strip()
        if override:
            try:
                return cls(timeout_s=max(6.0, min(60.0, float(override))))
            except ValueError:
                pass
        key = str(profile or "normal").strip().lower()
        # v9.0.3: seven seconds was too aggressive for a busy CPU/GPU system.
        # A single slow CT2 request must not immediately force the whole session
        # into the much slower Argos recovery path.
        if key in {"speed", "instant", "fast"}:
            return cls(timeout_s=12.0)
        if key in {"accurate", "quality"}:
            return cls(timeout_s=22.0)
        return cls(timeout_s=15.0)


class PartialTranslationGate:
    """Coalesces ASR revisions before they overload the translation sidecar."""

    def __init__(self, profile: str = "normal") -> None:
        key = str(profile or "normal").strip().lower()
        self.minimum_interval_s = 0.55 if key in {"speed", "instant", "fast"} else 1.15 if key in {"accurate", "quality"} else 0.80
        self.last_submit_at = 0.0
        self.last_text = ""
        self.last_confirmed = ""

    @staticmethod
    def _clean(value: str) -> str:
        return " ".join(str(value or "").split())

    def should_submit(self, text: str, *, confirmed: str = "", stable: bool = False, now: float | None = None) -> tuple[bool, str]:
        current = self._clean(text)
        confirmed_text = self._clean(confirmed)
        current_time = float(time.monotonic() if now is None else now)
        if not current:
            return False, "empty"
        if stable:
            self._commit(current, confirmed_text, current_time)
            return True, "final"
        if current == self.last_text:
            return False, "duplicate"
        confirmed_grew = bool(confirmed_text and confirmed_text != self.last_confirmed and len(confirmed_text) > len(self.last_confirmed))
        elapsed = current_time - self.last_submit_at if self.last_submit_at > 0 else 999.0
        first_preview = not self.last_text
        punctuation_commit = current.endswith((".", "!", "?", "…", "。", "！", "？"))
        if first_preview or confirmed_grew or punctuation_commit or elapsed >= self.minimum_interval_s:
            self._commit(current, confirmed_text, current_time)
            return True, "first" if first_preview else "confirmed_growth" if confirmed_grew else "punctuation" if punctuation_commit else "interval"
        return False, "coalesced"

    def _commit(self, text: str, confirmed: str, now: float) -> None:
        self.last_text = text
        if confirmed:
            self.last_confirmed = confirmed
        self.last_submit_at = now
