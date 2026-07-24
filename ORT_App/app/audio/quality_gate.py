from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?")
_HALLUCINATION_PATTERNS = (
    re.compile(r"\bplease (?:like|subscribe|share|follow)(?:\s+to)?\b", re.I),
    re.compile(r"\bthank you for watching\b", re.I),
    re.compile(r"\bsubtitles? by\b", re.I),
    re.compile(r"\bcopyright all rights reserved\b", re.I),
)


@dataclass(frozen=True)
class ASRQualityMetrics:
    avg_logprob: float
    no_speech_prob: float
    compression_ratio: float
    language_probability: float
    repetition_ratio: float
    token_density: float
    word_count: int
    audio_seconds: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ASRQualityDecision:
    accepted: bool
    retry_recommended: bool
    reasons: tuple[str, ...]
    metrics: ASRQualityMetrics

    def as_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "retry_recommended": self.retry_recommended,
            "reasons": list(self.reasons),
            "metrics": self.metrics.as_dict(),
        }


def _words(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD_RE.finditer(str(text or ""))]


def repetition_ratio(text: str) -> float:
    words = _words(text)
    if len(words) < 4:
        return 0.0
    ngram_size = 3 if len(words) >= 6 else 2
    ngrams = [tuple(words[index:index + ngram_size]) for index in range(len(words) - ngram_size + 1)]
    if not ngrams:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (len(set(ngrams)) / float(len(ngrams)))))


def aggregate_segment_metrics(segments: Iterable[object]) -> tuple[float, float, float]:
    rows = list(segments)
    if not rows:
        return -2.0, 1.0, 0.0
    weights = [max(0.05, float(getattr(row, "end", 0.0) or 0.0) - float(getattr(row, "start", 0.0) or 0.0)) for row in rows]
    total = sum(weights) or 1.0

    def weighted(name: str, default: float) -> float:
        values = []
        for row, weight in zip(rows, weights):
            value = getattr(row, name, default)
            values.append(float(default if value is None else value) * weight)
        return sum(values) / total

    return weighted("avg_logprob", -2.0), weighted("no_speech_prob", 1.0), weighted("compression_ratio", 0.0)


def assess_asr_quality(
    text: str,
    *,
    audio_seconds: float,
    avg_logprob: float,
    no_speech_prob: float,
    compression_ratio: float,
    language_probability: float,
    detected_language: str = "",
    expected_language: str = "",
) -> ASRQualityDecision:
    clean = " ".join(str(text or "").split())
    words = _words(clean)
    duration = max(0.1, float(audio_seconds or 0.0))
    repeat = repetition_ratio(clean)
    density = len(words) / duration
    metrics = ASRQualityMetrics(
        avg_logprob=float(avg_logprob),
        no_speech_prob=float(no_speech_prob),
        compression_ratio=float(compression_ratio),
        language_probability=float(language_probability),
        repetition_ratio=repeat,
        token_density=density,
        word_count=len(words),
        audio_seconds=duration,
    )
    reasons: list[str] = []
    hard_reject = False
    if not clean or not words:
        reasons.append("EMPTY")
        hard_reject = True
    if float(no_speech_prob) >= 0.78:
        reasons.append("NO_SPEECH")
        hard_reject = True
    if any(pattern.search(clean) for pattern in _HALLUCINATION_PATTERNS):
        reasons.append("HALLUCINATION_PHRASE")
        hard_reject = True
    if float(avg_logprob) < -1.25:
        reasons.append("LOW_LOGPROB")
    if float(compression_ratio) > 2.45:
        reasons.append("HIGH_COMPRESSION")
    if repeat >= 0.48 or (len(words) >= 12 and len(set(words)) / max(1, len(words)) < 0.34):
        reasons.append("REPETITION")
    if density > 7.2 and len(words) >= 8:
        reasons.append("TOKEN_DENSITY")
    expected = str(expected_language or "").strip().lower()
    detected = str(detected_language or "").strip().lower()
    if expected and detected and detected != expected and float(language_probability) >= 0.55:
        reasons.append("LANGUAGE_MISMATCH")
    if expected and float(language_probability) < 0.35:
        reasons.append("LOW_LANGUAGE_PROBABILITY")
    accepted = not reasons
    retryable = {"LOW_LOGPROB", "HIGH_COMPRESSION", "REPETITION", "TOKEN_DENSITY", "LANGUAGE_MISMATCH", "LOW_LANGUAGE_PROBABILITY"}
    retry_recommended = (not accepted) and (not hard_reject) and bool(set(reasons) & retryable)
    return ASRQualityDecision(
        accepted=accepted,
        retry_recommended=retry_recommended,
        reasons=tuple(reasons),
        metrics=metrics,
    )
