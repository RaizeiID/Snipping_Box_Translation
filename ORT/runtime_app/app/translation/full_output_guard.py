"""ORT v8.8.9 Full Output Guard.

A lightweight post-translation safety layer for story mode.  Its job is not to
invent a better translation; it prevents a low-coverage final from hiding a new
dialogue behind the previous last-good overlay.  When the translation appears
truncated, it prefers a safe current-source preview and blocks cache/training.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Optional

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+")


@dataclass(frozen=True)
class FullOutputDecision:
    allow_final: bool
    output: str
    reason: str = "ok"
    coverage: float = 1.0
    cache_blocked: str = ""
    trusted_preview: bool = False


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(str(text or ""))


def output_coverage(source: str, output: str) -> float:
    src = _words(source)
    if not src:
        return 1.0
    out = _words(output)
    return len(out) / max(1, len(src))


def source_safe_preview(source: str, partial_output: str = "") -> str:
    src = str(source or "").strip()
    partial = str(partial_output or "").strip()
    if partial and partial.casefold() != src.casefold() and len(_words(partial)) >= 3:
        return f"{partial}\n[{src}]"
    return f"{src}\n[Preview aman: final lengkap belum stabil]" if src else "[Preview aman: final lengkap belum stabil]"


class FullOutputGuard:
    def __init__(self, *, enabled: bool = True, min_words: int = 8, floor: float = 0.34) -> None:
        self.enabled = bool(enabled)
        self.min_words = int(min_words)
        self.floor = float(floor)

    @classmethod
    def from_env(cls) -> "FullOutputGuard":
        return cls(
            enabled=os.environ.get("ORT_FULL_OUTPUT_GUARD", "1") != "0",
            min_words=int(os.environ.get("ORT_FULL_OUTPUT_MIN_SOURCE_WORDS", "8")),
            floor=float(os.environ.get("ORT_FULL_OUTPUT_COVERAGE_FLOOR", "0.34")),
        )

    def assess(self, source: str, output: str, *, anchor_output: Optional[str] = None, relation: str = "") -> FullOutputDecision:
        if not self.enabled:
            return FullOutputDecision(True, str(output or ""), "disabled", 1.0)
        src_words = _words(source)
        if len(src_words) < self.min_words:
            return FullOutputDecision(True, str(output or ""), "short_source", 1.0)
        cov = output_coverage(source, output)
        if cov >= self.floor and len(str(output or "").strip()) >= 12:
            return FullOutputDecision(True, str(output or ""), "coverage_ok", round(cov, 3))
        # If the CT2/literal anchor is more complete than the polished result,
        # use it as a no-cache preview before falling back to raw source.
        anchor = str(anchor_output or "").strip()
        anchor_cov = output_coverage(source, anchor) if anchor else 0.0
        if anchor and anchor_cov > cov + 0.16 and len(_words(anchor)) >= max(4, int(len(src_words) * self.floor)):
            return FullOutputDecision(
                False,
                anchor,
                "anchor_output_more_complete",
                round(anchor_cov, 3),
                "full_output_guard_anchor_no_cache",
                True,
            )
        return FullOutputDecision(
            False,
            source_safe_preview(source, output),
            "output_coverage_too_low_source_safe_preview",
            round(cov, 3),
            "full_output_guard_source_safe_no_cache",
            True,
        )
