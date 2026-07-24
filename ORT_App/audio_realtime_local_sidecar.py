from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import sys
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Optional

import numpy as np

from app.audio.cuda_bootstrap import activate_cuda_dll_search
from app.audio.turn_context import RollingTurnContext

CUDA_BOOTSTRAP = activate_cuda_dll_search()

EVENT_PREFIX = "ORT_AUDIO_EVENT "
TARGET_SAMPLE_RATE = 16000
STOP_REQUESTED = False
_PRINT_LOCK = threading.Lock()
_EVENT_SINK: Optional[list[dict]] = None


def emit_event(event_type: str, **payload: Any) -> None:
    event = {"type": str(event_type), "ts": time.time(), **payload}
    if _EVENT_SINK is not None:
        _EVENT_SINK.append(event)
        return
    with _PRINT_LOCK:
        print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def _signal_stop(*_args: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def _install_signal_handlers() -> None:
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _signal_stop)
            except Exception:
                pass


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())



def _has_semantic_text(value: Any) -> bool:
    """Return True for text containing at least one letter/number/CJK symbol."""
    text = _clean_text(value)
    return any(char.isalnum() or "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" for char in text)


def _partial_growth(previous: str, current: str) -> float:
    old = _clean_text(previous)
    new = _clean_text(current)
    if not old:
        return 1.0
    if new.lower().startswith(old.lower()):
        return max(0.0, (len(new) - len(old)) / float(max(1, len(old))))
    old_tokens = set(old.lower().split())
    new_tokens = set(new.lower().split())
    overlap = len(old_tokens & new_tokens) / float(max(1, len(old_tokens | new_tokens)))
    return 1.0 - overlap


def _language_code(value: str) -> Optional[str]:
    key = str(value or "auto").strip().lower().replace("_", "-")
    mapping = {
        "ja-jp": "ja",
        "ja": "ja",
        "ja-specialist": "ja",
        "japanese-specialist": "ja",
        "en-us": "en",
        "en": "en",
        "zh-cn": "zh",
        "zh": "zh",
        "ko-kr": "ko",
        "ko": "ko",
        "id-id": "id",
        "id": "id",
    }
    if key in {"", "auto", "auto-detect", "auto_detect", "smart-auto", "smart"}:
        return None
    return mapping.get(key, key.split("-", 1)[0])


def _is_japanese_specialist_mode(value: str) -> bool:
    key = str(value or "").strip().lower().replace("_", "-")
    return key in {"ja-specialist", "japanese-specialist"}


def _mono_float_from_pcm16(payload: bytes, channels: int) -> np.ndarray:
    samples = np.frombuffer(payload, dtype=np.int16)
    if samples.size == 0:
        return np.empty(0, dtype=np.float32)
    channels = max(1, int(channels))
    usable = samples.size - (samples.size % channels)
    if usable <= 0:
        return np.empty(0, dtype=np.float32)
    matrix = samples[:usable].reshape(-1, channels).astype(np.float32)
    return np.clip(matrix.mean(axis=1) / 32768.0, -1.0, 1.0)


def _resample_linear(samples: np.ndarray, source_rate: int, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    source = np.asarray(samples, dtype=np.float32).reshape(-1)
    source_rate = max(1, int(source_rate))
    target_rate = max(1, int(target_rate))
    if source.size == 0 or source_rate == target_rate:
        return source.copy()
    target_size = max(1, int(round(source.size * target_rate / float(source_rate))))
    old_positions = np.linspace(0.0, 1.0, num=source.size, endpoint=False, dtype=np.float64)
    new_positions = np.linspace(0.0, 1.0, num=target_size, endpoint=False, dtype=np.float64)
    return np.interp(new_positions, old_positions, source).astype(np.float32)


def _rms(samples: np.ndarray) -> float:
    source = np.asarray(samples, dtype=np.float32).reshape(-1)
    if source.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(source), dtype=np.float64)))


@dataclass(frozen=True)
class LocalRealtimePolicy:
    profile: str
    first_partial_s: float
    partial_interval_s: float
    endpoint_s: float
    max_phrase_s: float
    pre_roll_s: float
    carry_over_s: float
    minimum_rms: float
    noise_multiplier: float
    short_pause_s: float
    long_pause_s: float
    subtitle_window_s: float
    hard_turn_s: float
    semantic_no_speech_passes: int = 2
    chunk_ms: int = 20

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "first_partial_ms": int(self.first_partial_s * 1000),
            "partial_interval_ms": int(self.partial_interval_s * 1000),
            "endpoint_ms": int(self.endpoint_s * 1000),
            "max_phrase_ms": int(self.max_phrase_s * 1000),
            "pre_roll_ms": int(self.pre_roll_s * 1000),
            "carry_over_ms": int(self.carry_over_s * 1000),
            "minimum_rms": self.minimum_rms,
            "noise_multiplier": self.noise_multiplier,
            "short_pause_ms": int(self.short_pause_s * 1000),
            "long_pause_ms": int(self.long_pause_s * 1000),
            "subtitle_window_ms": int(self.subtitle_window_s * 1000),
            "hard_turn_ms": int(self.hard_turn_s * 1000),
            "semantic_no_speech_passes": self.semantic_no_speech_passes,
            "chunk_ms": self.chunk_ms,
        }


def resolve_policy(profile: str, device: str) -> LocalRealtimePolicy:
    profile_key = str(profile or "normal").strip().lower()
    gpu = str(device or "cpu").strip().lower() == "cuda"
    if profile_key in {"speed", "instant", "fast"}:
        return LocalRealtimePolicy(
            profile="speed",
            first_partial_s=0.34 if gpu else 0.46,
            partial_interval_s=0.30 if gpu else 0.46,
            endpoint_s=0.46,
            max_phrase_s=8.0,
            pre_roll_s=0.30,
            carry_over_s=0.18,
            minimum_rms=0.0032,
            noise_multiplier=2.25,
            short_pause_s=0.28,
            long_pause_s=0.92,
            subtitle_window_s=5.0,
            hard_turn_s=9.0,
        )
    if profile_key in {"accurate", "quality"}:
        return LocalRealtimePolicy(
            profile="accurate",
            first_partial_s=0.64 if gpu else 0.84,
            partial_interval_s=0.58 if gpu else 0.86,
            endpoint_s=0.76,
            max_phrase_s=16.0,
            pre_roll_s=0.42,
            carry_over_s=0.32,
            minimum_rms=0.0038,
            noise_multiplier=2.65,
            short_pause_s=0.42,
            long_pause_s=1.35,
            subtitle_window_s=7.5,
            hard_turn_s=14.0,
        )
    return LocalRealtimePolicy(
        profile="normal",
        first_partial_s=0.46 if gpu else 0.58,
        partial_interval_s=0.42 if gpu else 0.58,
        endpoint_s=0.62,
        max_phrase_s=12.0,
        pre_roll_s=0.36,
        carry_over_s=0.24,
        minimum_rms=0.0035,
        noise_multiplier=2.45,
        short_pause_s=0.34,
        long_pause_s=1.10,
        subtitle_window_s=6.0,
        hard_turn_s=11.0,
    )


@dataclass
class Snapshot:
    result_id: str
    revision: int
    samples: np.ndarray
    stable: bool
    created_at: float
    audio_seconds: float


class LatestSnapshotMailbox:
    """Keeps only the newest interim while never discarding a final snapshot."""

    def __init__(self, max_finals: int = 2) -> None:
        self._condition = threading.Condition()
        self._latest_partial: Optional[Snapshot] = None
        self._finals: Deque[Snapshot] = deque()
        self._max_finals = max(1, int(max_finals))
        self._closed = False

    def put(self, snapshot: Snapshot) -> None:
        with self._condition:
            if snapshot.stable:
                self._latest_partial = None
                while len(self._finals) >= self._max_finals:
                    dropped = self._finals.popleft()
                    emit_event(
                        "metric",
                        name="realtime_final_backpressure_drop",
                        dropped_segment=dropped.result_id,
                        kept_segment=snapshot.result_id,
                        local_realtime=True,
                    )
                self._finals.append(snapshot)
            else:
                self._latest_partial = snapshot
            self._condition.notify_all()

    def get(self, timeout: float = 0.2) -> Optional[Snapshot]:
        deadline = time.monotonic() + max(0.01, float(timeout))
        with self._condition:
            while not self._closed and not self._finals and self._latest_partial is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            if self._finals:
                return self._finals.popleft()
            snapshot = self._latest_partial
            self._latest_partial = None
            return snapshot

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


@dataclass(frozen=True)
class LanguageCorrectionPolicy:
    mode: str
    enabled: bool
    observation_interval_s: float
    confirmation_window_s: float
    minimum_confirmations: int
    confidence_threshold: float
    dominance_threshold: float
    code_switch_max_s: float
    cooldown_s: float


def resolve_language_correction_policy(mode: str) -> LanguageCorrectionPolicy:
    key = str(mode or "balanced").strip().lower()
    if key in {"off", "disabled", "none", "0", "false"}:
        return LanguageCorrectionPolicy("off", False, 99.0, 99.0, 99, 1.0, 1.0, 0.0, 0.0)
    if key in {"conservative", "safe"}:
        return LanguageCorrectionPolicy("conservative", True, 2.0, 12.0, 5, 0.90, 0.80, 4.0, 24.0)
    if key in {"aggressive", "fast"}:
        return LanguageCorrectionPolicy("aggressive", True, 1.5, 5.0, 3, 0.72, 0.67, 3.0, 15.0)
    return LanguageCorrectionPolicy("balanced", True, 2.0, 8.0, 4, 0.80, 0.70, 4.0, 20.0)


@dataclass(frozen=True)
class LanguageDecision:
    detected_language: str = ""
    probability: float = 0.0
    global_language: str = ""
    segment_language: str = ""
    state: str = ""


class LanguageWatchdog:
    """Independent, low-frequency language detector with hysteresis.

    It never treats one short foreign sentence as a global language change.
    A short mismatch is returned only as a segment-level code switch. Global
    correction needs repeated, dominant evidence across the configured window.
    """

    def __init__(
        self,
        model_root: Path,
        requested_language: Optional[str],
        mode: str,
        language_locked: bool,
        cpu_threads: int,
    ) -> None:
        self.model_root = Path(model_root)
        self.requested_language = requested_language
        self.policy = resolve_language_correction_policy(mode)
        self.language_locked = bool(language_locked)
        self.cpu_threads = max(1, int(cpu_threads))
        self.detector: Any = None
        self.detector_size = ""
        self.last_observation_at = -1e9
        self.last_global_switch_at = -1e9
        self.observations: Deque[tuple[float, str, float]] = deque(maxlen=24)
        self.unavailable = False
        self._lock = threading.RLock()
        self._probe_thread: Optional[threading.Thread] = None
        self._pending_decision: Optional[LanguageDecision] = None

    def _location(self) -> Optional[Path]:
        for size in ("tiny", "base"):
            for candidate in (self.model_root / f"faster-whisper-{size}", self.model_root / size):
                if candidate.is_dir():
                    self.detector_size = size
                    return candidate
        return None

    def _ensure_detector(self) -> bool:
        if not self.policy.enabled or self.unavailable:
            return False
        if self.detector is not None:
            return True
        location = self._location()
        if location is None:
            self.unavailable = True
            emit_event(
                "state",
                state="LANGUAGE_WATCHDOG_UNAVAILABLE",
                reason="DETECTOR_MODEL_MISSING",
                local_realtime=True,
            )
            return False
        try:
            from faster_whisper import WhisperModel

            emit_event(
                "state",
                state="LANGUAGE_WATCHDOG_LOADING",
                model=self.detector_size,
                device="cpu",
                mode=self.policy.mode,
                local_realtime=True,
            )
            self.detector = WhisperModel(
                str(location),
                device="cpu",
                compute_type="int8",
                cpu_threads=max(1, min(2, self.cpu_threads)),
                num_workers=1,
            )
            emit_event(
                "state",
                state="LANGUAGE_WATCHDOG_READY",
                model=self.detector_size,
                device="cpu",
                mode=self.policy.mode,
                local_realtime=True,
            )
            return True
        except Exception as exc:
            self.unavailable = True
            emit_event(
                "state",
                state="LANGUAGE_WATCHDOG_UNAVAILABLE",
                reason="DETECTOR_LOAD_FAILED",
                message=str(exc),
                local_realtime=True,
            )
            return False

    def record_detection(self, language: str, probability: float, now: float, current_language: Optional[str]) -> LanguageDecision:
        detected = _language_code(language) or ""
        probability = max(0.0, min(1.0, float(probability or 0.0)))
        if not detected:
            return LanguageDecision()
        self.observations.append((float(now), detected, probability))
        horizon = max(self.policy.confirmation_window_s + 6.0, 20.0)
        while self.observations and now - self.observations[0][0] > horizon:
            self.observations.popleft()

        current = _language_code(current_language or "") or ""
        mismatch = bool(current and detected != current)
        recent_same = [item for item in self.observations if item[1] == detected and now - item[0] <= self.policy.confirmation_window_s]
        recent_all = [item for item in self.observations if now - item[0] <= self.policy.confirmation_window_s]
        avg_probability = sum(item[2] for item in recent_same) / max(1, len(recent_same))
        dominance = len(recent_same) / max(1, len(recent_all))
        span = (recent_same[-1][0] - recent_same[0][0]) if len(recent_same) >= 2 else 0.0

        required_confidence = self.policy.confidence_threshold + (0.05 if mismatch else 0.0)
        required_window = self.policy.confirmation_window_s + (4.0 if mismatch and current and self.last_global_switch_at > -1e8 else 0.0)
        enough_span = span >= max(0.0, required_window - self.policy.observation_interval_s * 1.5)
        confirmed = bool(
            len(recent_same) >= self.policy.minimum_confirmations
            and avg_probability >= required_confidence
            and dominance >= self.policy.dominance_threshold
            and enough_span
        )
        cooldown_ok = now - self.last_global_switch_at >= self.policy.cooldown_s

        if confirmed and cooldown_ok and not self.language_locked and detected != current:
            self.last_global_switch_at = now
            emit_event(
                "state",
                state="LANGUAGE_SWITCH_CONFIRMED" if current else "LANGUAGE_LOCKED",
                previous_language=current or "auto",
                detected_language=detected,
                language_probability=round(avg_probability, 4),
                confirmations=len(recent_same),
                dominance=round(dominance, 4),
                mode=self.policy.mode,
                local_realtime=True,
            )
            return LanguageDecision(detected, avg_probability, detected, detected, "GLOBAL_SWITCH")

        if mismatch and probability >= self.policy.confidence_threshold:
            first = recent_same[0][0] if recent_same else now
            mismatch_duration = max(0.0, now - first)
            state = "TEMPORARY_CODE_SWITCH" if mismatch_duration <= self.policy.code_switch_max_s or self.language_locked else "LANGUAGE_MISMATCH_CONFIRMING"
            emit_event(
                "state",
                state=state,
                primary_language=current,
                detected_language=detected,
                language_probability=round(probability, 4),
                confirmations=len(recent_same),
                language_locked=self.language_locked,
                local_realtime=True,
            )
            return LanguageDecision(detected, probability, "", detected, state)

        return LanguageDecision(detected, probability, "", current or detected, "OBSERVED")

    def _probe_async(self, probe: np.ndarray, current_language: Optional[str], observation_time: float) -> None:
        decision = LanguageDecision(segment_language=_language_code(current_language or "") or "")
        try:
            if not self._ensure_detector():
                return
            segments, info = self.detector.transcribe(
                probe,
                language=None,
                task="transcribe",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                word_timestamps=False,
                without_timestamps=True,
            )
            for _ in segments:
                break
            detected = str(getattr(info, "language", "") or "")
            probability = float(getattr(info, "language_probability", 0.0) or 0.0)
            decision = self.record_detection(detected, probability, observation_time, current_language)
        except Exception as exc:
            emit_event(
                "state",
                state="LANGUAGE_WATCHDOG_PROBE_FAILED",
                message=str(exc),
                local_realtime=True,
            )
        finally:
            with self._lock:
                self._pending_decision = decision

    def observe(self, samples: np.ndarray, current_language: Optional[str], now: Optional[float] = None) -> LanguageDecision:
        current = _language_code(current_language or "") or ""
        if not self.policy.enabled:
            return LanguageDecision(segment_language=current)
        current_time = time.monotonic() if now is None else float(now)
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        with self._lock:
            decision = self._pending_decision
            self._pending_decision = None
            due = current_time - self.last_observation_at >= self.policy.observation_interval_s
            worker_busy = self._probe_thread is not None and self._probe_thread.is_alive()
            if due and not worker_busy and len(audio) >= int(TARGET_SAMPLE_RATE * 1.0):
                self.last_observation_at = current_time
                probe = audio[-int(TARGET_SAMPLE_RATE * 3.0):].copy()
                self._probe_thread = threading.Thread(
                    target=self._probe_async,
                    args=(probe, current_language, current_time),
                    name="ort-language-watchdog",
                    daemon=True,
                )
                self._probe_thread.start()
        return decision or LanguageDecision(segment_language=current)



def _contains_japanese(text: str) -> bool:
    return any("\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def _asr_quality_reasons(text: str, audio_seconds: float, task: str) -> list[str]:
    clean = _clean_text(text)
    if not clean:
        return ["EMPTY", "NO_SPEECH"]
    tokens = clean.lower().split()
    reasons: list[str] = []
    if len(tokens) >= 8:
        unique_ratio = len(set(tokens)) / float(len(tokens))
        max_count = max(tokens.count(item) for item in set(tokens))
        if max_count >= 5 and max_count / float(len(tokens)) >= 0.42:
            reasons.append("REPEAT_TOKEN_LOOP")
        if unique_ratio < 0.22:
            reasons.append("LOW_LEXICAL_DIVERSITY")
        joined_triples = [" ".join(tokens[i:i + 3]) for i in range(max(0, len(tokens) - 2))]
        if joined_triples and max(joined_triples.count(item) for item in set(joined_triples)) >= 4:
            reasons.append("REPEAT_NGRAM_LOOP")
    if audio_seconds > 0.0 and len(clean) > max(180, int(audio_seconds * 55.0)):
        reasons.append("OUTPUT_AUDIO_RATIO")
    if task == "translate" and _contains_japanese(clean):
        # A few Japanese names are acceptable, but a bridge dominated by Japanese
        # cannot be sent to the English->Indonesian translator.
        jp_chars = sum(1 for char in clean if "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff")
        if jp_chars / max(1, len(clean)) >= 0.45:
            reasons.append("BRIDGE_NOT_ENGLISH")
    return sorted(set(reasons))


class ModelAdapter:
    def __init__(
        self,
        model_root: Path,
        model_size: str,
        fallback_model_size: str,
        device: str,
        compute_type: str,
        cpu_threads: int,
        language: Optional[str],
        allow_cpu_fallback: bool,
        game: str,
        requested_language: str = "auto",
        japanese_specialist: bool = False,
        language_correction_mode: str = "balanced",
        language_locked: bool = False,
        profile: str = "normal",
    ) -> None:
        self.model_root = Path(model_root)
        self.generic_model_size = str(model_size or "base")
        self.model_size = self.generic_model_size
        self.fallback_model_size = str(fallback_model_size or "base")
        self.device = str(device or "cpu")
        self.compute_type = str(compute_type or ("int8_float16" if self.device == "cuda" else "int8"))
        self.cpu_threads = max(1, int(cpu_threads))
        self.language = language
        self.requested_language = str(requested_language or "auto")
        self.japanese_specialist = bool(japanese_specialist)
        self.session_language: Optional[str] = language
        self.allow_cpu_fallback = bool(allow_cpu_fallback)
        self.game = str(game or "")
        self.model: Any = None
        self._fallback_used = False
        self.specialist_active = False
        self._specialist_unavailable_reported = False
        self.language_watchdog = LanguageWatchdog(
            self.model_root,
            language,
            language_correction_mode,
            language_locked,
            self.cpu_threads,
        )
        self.language_locked = bool(language_locked)
        self.profile = str(profile or "normal").strip().lower()
        self._last_reject_reasons: list[str] = []
        self.fast_preview_model: Any = None
        self.fast_preview_model_size = self.fallback_model_size
        self.fast_preview_model_path = ""
        self.dual_stream_cpu_specialist = False
        self._specialist_lock = threading.RLock()

    def _model_location(self, size: str) -> str:
        candidates = [
            self.model_root / f"faster-whisper-{size}",
            self.model_root / size,
        ]
        if size == "kotoba-bilingual":
            candidates = [
                self.model_root / "kotoba-whisper-bilingual-v1.0-faster",
                self.model_root / "faster-whisper-kotoba-bilingual-v1.0",
                self.model_root / "kotoba-bilingual",
            ] + candidates
        for candidate in candidates:
            if candidate.is_dir():
                return str(candidate)
        raise FileNotFoundError(
            f"Model faster-whisper-{size} tidak ditemukan di {self.model_root}. Jalankan Siapkan Audio terlebih dahulu."
        )

    def _construct_model(self, size: str, device: str, compute_type: str) -> tuple[Any, str]:
        from faster_whisper import WhisperModel

        location = self._model_location(size)
        emit_event(
            "state",
            state="MODEL_LOADING",
            model=size,
            device=device,
            compute_type=compute_type,
            local_realtime=True,
        )
        model = WhisperModel(
            location,
            device=device,
            compute_type=compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=1,
        )
        return model, location

    def _ensure_fast_preview_model(self) -> None:
        if self.fast_preview_model is not None:
            return
        from faster_whisper import WhisperModel

        location = self._model_location(self.fast_preview_model_size)
        emit_event(
            "state",
            state="FAST_PREVIEW_MODEL_LOADING",
            model=self.fast_preview_model_size,
            device="cpu",
            compute_type="int8",
            local_realtime=True,
        )
        self.fast_preview_model = WhisperModel(
            location,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(4, self.cpu_threads)),
            num_workers=1,
        )
        self.fast_preview_model_path = location
        emit_event(
            "state",
            state="FAST_PREVIEW_MODEL_READY",
            model=self.fast_preview_model_size,
            model_path=location,
            device="cpu",
            compute_type="int8",
            purpose="instant_preview",
            local_realtime=True,
        )

    def _runtime_preflight(self, model: Any, specialist: bool, source_language: Optional[str], device: str) -> None:
        state_prefix = "CUDA" if device == "cuda" else "CPU"
        emit_event(
            "state",
            state=f"{state_prefix}_PREFLIGHT",
            model="kotoba-bilingual" if specialist else self.model_size,
            local_realtime=True,
        )
        language = "en" if specialist and source_language == "ja" else (source_language or "en")
        task = "translate" if source_language not in {None, "en"} else "transcribe"
        duration = 0.60 if device == "cuda" else 0.32
        timeline = np.arange(int(TARGET_SAMPLE_RATE * duration), dtype=np.float32) / float(TARGET_SAMPLE_RATE)
        probe_audio = (0.006 * np.sin(2.0 * np.pi * 440.0 * timeline)).astype(np.float32)
        passes = 2 if device == "cuda" else 1
        timings: list[int] = []
        for _index in range(passes):
            tick = time.perf_counter()
            segments, _ = model.transcribe(
                probe_audio,
                language=language,
                task=task,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                without_timestamps=True,
            )
            # faster-whisper returns a generator; consuming it is required to
            # execute inference and make the preload real rather than cosmetic.
            list(segments)
            timings.append(max(0, int((time.perf_counter() - tick) * 1000.0)))
        emit_event(
            "state",
            state=f"{state_prefix}_PREFLIGHT_PASSED",
            model="kotoba-bilingual" if specialist else self.model_size,
            warmup_ms=timings[0],
            steady_ms=timings[-1],
            local_realtime=True,
        )

    def _cuda_preflight(self, model: Any, specialist: bool, source_language: Optional[str]) -> None:
        self._runtime_preflight(model, specialist, source_language, "cuda")

    def _load(self, size: str, device: str, compute_type: str, specialist: bool = False, run_preflight: bool = True) -> None:
        previous_device = self.device
        self.device = device
        try:
            model, location = self._construct_model(size, device, compute_type)
            if run_preflight:
                self._runtime_preflight(model, specialist, self.session_language or self.language, device)
            self.model = model
            self.model_size = size
            self.compute_type = compute_type
            self.specialist_active = bool(specialist and size == "kotoba-bilingual")
            emit_event(
                "state",
                state="MODEL_READY",
                model=size,
                model_path=location,
                device=device,
                compute_type=compute_type,
                offline=True,
                local_realtime=True,
            )
            self.dual_stream_cpu_specialist = bool(
                self.specialist_active and device == "cpu" and self.profile not in {"accurate", "quality"}
            )
            if self.dual_stream_cpu_specialist:
                self._ensure_fast_preview_model()
                emit_event(
                    "state",
                    state="JAPANESE_DUAL_STREAM_ACTIVE",
                    preview_model=self.fast_preview_model_size,
                    correction_model="kotoba-bilingual",
                    behavior="instant_preview_async_specialist_correction",
                    local_realtime=True,
                )
            if self.specialist_active:
                emit_event(
                    "state",
                    state="JAPANESE_SPECIALIST_CPU_ACTIVE" if device == "cpu" else "JAPANESE_SPECIALIST_ACTIVE",
                    model=size,
                    device=device,
                    source_language="ja",
                    bridge_language="en",
                    local_realtime=True,
                )
        except Exception:
            self.device = previous_device
            raise

    @staticmethod
    def _looks_like_cuda_runtime_error(exc: BaseException) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        needles = ("cublas", "cudnn", "cuda", "cudart", "nvcuda", "dll is not found", "cannot be loaded")
        return any(item in text for item in needles)

    def _desired_model_for_language(self, language: Optional[str]) -> tuple[str, bool]:
        if self.japanese_specialist and language == "ja":
            try:
                self._model_location("kotoba-bilingual")
                return "kotoba-bilingual", True
            except FileNotFoundError as exc:
                if not self._specialist_unavailable_reported:
                    self._specialist_unavailable_reported = True
                    emit_event(
                        "state",
                        state="JAPANESE_SPECIALIST_UNAVAILABLE",
                        message=str(exc),
                        fallback_model=self.fallback_model_size,
                        local_realtime=True,
                    )
        return self.generic_model_size if self.device == "cuda" else self.fallback_model_size, False

    def _fallback_to_cpu(self, exc: BaseException) -> None:
        source_language = self.session_language or self.language
        preserve_specialist = bool((self.specialist_active or self.japanese_specialist) and source_language == "ja")
        target_size = "kotoba-bilingual" if preserve_specialist else self.fallback_model_size
        emit_event(
            "state",
            state="HYBRID_FAILOVER",
            reason="CUDA_RUNTIME_UNAVAILABLE",
            message=str(exc),
            from_device="cuda",
            to_device="cpu",
            preserve_model=target_size,
            local_realtime=True,
        )
        if preserve_specialist:
            emit_event(
                "state",
                state="JAPANESE_SPECIALIST_CPU_LOADING",
                model=target_size,
                local_realtime=True,
            )
        self._fallback_used = True
        try:
            self._load(target_size, "cpu", "int8", specialist=preserve_specialist, run_preflight=False)
        except Exception as cpu_exc:
            if not preserve_specialist:
                raise
            emit_event(
                "state",
                state="JAPANESE_SPECIALIST_CPU_FAILED",
                model=target_size,
                message=str(cpu_exc),
                fallback_model=self.fallback_model_size,
                local_realtime=True,
            )
            self.specialist_active = False
            self._load(self.fallback_model_size, "cpu", "int8", specialist=False, run_preflight=False)

    def load(self) -> None:
        desired_size, specialist = self._desired_model_for_language(self.session_language or self.language)
        try:
            self._load(desired_size, self.device, self.compute_type, specialist=specialist, run_preflight=True)
        except Exception as exc:
            if self.device == "cuda" and self.allow_cpu_fallback and self._looks_like_cuda_runtime_error(exc):
                self._fallback_to_cpu(exc)
                return
            raise

    def _activate_language(self, language: str, reason: str) -> None:
        target_language = _language_code(language) or language
        if not target_language:
            return
        self.session_language = target_language
        desired_size, specialist = self._desired_model_for_language(target_language)
        current_specialist = bool(self.specialist_active and self.model_size == "kotoba-bilingual")
        if desired_size == self.model_size and specialist == current_specialist:
            return
        emit_event(
            "state",
            state="LANGUAGE_MODEL_SWITCHING",
            detected_language=target_language,
            from_model=self.model_size,
            to_model=desired_size,
            reason=reason,
            local_realtime=True,
        )
        try:
            self._load(desired_size, self.device, self.compute_type, specialist=specialist, run_preflight=self.device == "cuda")
        except Exception as exc:
            if self.device == "cuda" and self.allow_cpu_fallback and self._looks_like_cuda_runtime_error(exc):
                self._fallback_to_cpu(exc)
            else:
                emit_event(
                    "state",
                    state="LANGUAGE_MODEL_SWITCH_FAILED",
                    message=str(exc),
                    target_language=target_language,
                    local_realtime=True,
                )

    def _soft_glossary(self, text: str) -> str:
        clean = _clean_text(text)
        if "GFL2" not in self.game.upper() and "EXILIUM" not in self.game.upper():
            return clean
        replacements = {
            "may ling": "Mayling",
            "mei ling": "Mayling",
            "crolic": "Krolik",
            "krollick": "Krolik",
            "vep lee": "Vepley",
            "makkiato": "Makiatto",
            "macchiato": "Makiatto",
            "clukai": "Klukai",
            "groza": "Groza",
            "colphne": "Colphne",
        }
        import re

        output = clean
        for source, target in replacements.items():
            output = re.sub(rf"\b{re.escape(source)}\b", target, output, flags=re.IGNORECASE)
        return output

    def _transcribe_once(
        self,
        model: Any,
        audio: np.ndarray,
        source_language: Optional[str],
        specialist: bool,
        retry: bool = False,
        stable: bool = False,
    ) -> tuple[str, Any, str]:
        if specialist and source_language == "ja":
            language_for_model = "en"
            task = "translate"
        elif source_language == "en":
            language_for_model = "en"
            task = "transcribe"
        else:
            language_for_model = source_language
            task = "translate"
        specialist_gpu = bool(specialist and source_language == "ja" and self.device == "cuda")
        if specialist_gpu:
            if self.profile in {"accurate", "quality"}:
                beam_size = 4 if stable else 3
            elif self.profile in {"speed", "instant", "fast"}:
                beam_size = 2 if stable else 1
            else:
                beam_size = 3 if stable else 2
        elif specialist and source_language == "ja":
            beam_size = 2 if stable and self.profile in {"accurate", "quality"} else 1
        else:
            beam_size = 1
        kwargs = {
            "language": language_for_model,
            "task": task,
            "beam_size": beam_size,
            "best_of": max(1, beam_size),
            "patience": 1.0,
            "temperature": 0.15 if retry else 0.0,
            "condition_on_previous_text": False,
            "vad_filter": False,
            "word_timestamps": False,
            "without_timestamps": True,
            "initial_prompt": None,
            "repetition_penalty": 1.16 if retry else 1.10,
            "no_repeat_ngram_size": 4 if retry else 3,
            "compression_ratio_threshold": 2.15 if specialist else 2.0,
            "log_prob_threshold": -1.25 if specialist else -1.0,
            "no_speech_threshold": 0.52 if specialist else 0.62,
        }
        segments, info = model.transcribe(audio, **kwargs)
        text = self._soft_glossary(" ".join(str(item.text or "") for item in segments))
        return text, info, task

    def _language_context(self, audio: np.ndarray) -> tuple[LanguageDecision, str]:
        decision = self.language_watchdog.observe(audio, self.session_language or self.language)
        if decision.global_language:
            self._activate_language(decision.global_language, "LANGUAGE_WATCHDOG")
        source_language = decision.segment_language or self.session_language or self.language
        if not source_language and decision.detected_language:
            source_language = decision.detected_language
        if not source_language:
            source_language = "auto"
        return decision, source_language

    def _run_transcription(
        self,
        model: Any,
        audio: np.ndarray,
        source_language: str,
        specialist: bool,
        allow_retry: bool,
        stable: bool = False,
    ) -> tuple[str, Any, str, list[str], bool, float]:
        duration_s = len(audio) / float(TARGET_SAMPLE_RATE)
        text, info, task = self._transcribe_once(
            model,
            audio,
            None if source_language == "auto" else source_language,
            specialist=specialist,
            stable=stable,
        )
        reasons = _asr_quality_reasons(text, duration_s, task)
        quality_retry = False
        if allow_retry and reasons and duration_s >= 2.0:
            quality_retry = True
            retry_audio = audio[-int(min(duration_s, 4.0) * TARGET_SAMPLE_RATE):]
            retry_text, retry_info, retry_task = self._transcribe_once(
                model,
                retry_audio,
                None if source_language == "auto" else source_language,
                specialist=specialist,
                retry=True,
                stable=True,
            )
            retry_reasons = _asr_quality_reasons(
                retry_text,
                len(retry_audio) / float(TARGET_SAMPLE_RATE),
                retry_task,
            )
            if len(retry_reasons) < len(reasons):
                text, info, task, reasons = retry_text, retry_info, retry_task, retry_reasons
        return text, info, task, reasons, quality_retry, duration_s

    @property
    def specialist_correction_enabled(self) -> bool:
        enabled = str(os.environ.get("ORT_AUDIO_BACKGROUND_SPECIALIST_CORRECTION", "0")).lower() in {
            "1", "true", "yes", "on"
        }
        return bool(enabled and self.dual_stream_cpu_specialist and self.specialist_active and self.model is not None)

    def transcribe_specialist_correction(self, samples: np.ndarray) -> tuple[str, dict]:
        if not self.specialist_correction_enabled:
            return "", {"quality_reject_reasons": ["SPECIALIST_CORRECTION_DISABLED"]}
        started = time.perf_counter()
        audio = np.asarray(samples, dtype=np.float32)
        # A live correction must never build an unbounded backlog. Six seconds
        # preserves useful sentence context while putting a hard ceiling on the
        # expensive CPU Kotoba pass.
        maximum = int(6.0 * TARGET_SAMPLE_RATE)
        if len(audio) > maximum:
            audio = audio[-maximum:]
        with self._specialist_lock:
            text, info, task, reasons, quality_retry, _duration = self._run_transcription(
                self.model,
                audio,
                "ja",
                specialist=True,
                allow_retry=False,
                stable=True,
            )
        detected = str(getattr(info, "language", "ja") or "ja")
        probability = float(getattr(info, "language_probability", 1.0) or 1.0)
        metadata = {
            "requested_language": self.requested_language,
            "detected_language": detected,
            "language_probability": probability,
            "source_language": "ja",
            "bridge_language": "en",
            "asr_task": task,
            "japanese_specialist": True,
            "specialist_correction": True,
            "provisional": False,
            "quality_retry": quality_retry,
            "asr_ms": max(0, int((time.perf_counter() - started) * 1000.0)),
            "model_used": "kotoba-bilingual",
        }
        if reasons:
            metadata["quality_reject_reasons"] = reasons
            return "", metadata
        return text, metadata

    def transcribe(self, samples: np.ndarray, stable: bool = False) -> tuple[str, dict]:
        if self.model is None:
            raise RuntimeError("Model ASR belum dimuat.")
        started = time.perf_counter()
        audio = np.asarray(samples, dtype=np.float32)
        try:
            decision, source_language = self._language_context(audio)
            use_fast_preview = bool(
                self.dual_stream_cpu_specialist
                and self.fast_preview_model is not None
                and source_language == "ja"
            )
            active_model = self.fast_preview_model if use_fast_preview else self.model
            active_specialist = bool(self.specialist_active and not use_fast_preview)
            inference_audio = audio
            japanese_context = source_language == "ja"
            if self.profile in {"speed", "instant", "fast"}:
                window_s = (8.0 if stable else 5.5) if japanese_context else (7.0 if stable else 4.5)
            elif self.profile in {"accurate", "quality"}:
                window_s = (16.0 if stable else 10.0) if japanese_context else (14.0 if stable else 8.0)
            else:
                window_s = (12.0 if stable else 7.5) if japanese_context else (10.0 if stable else 6.0)
            if self.device != "cuda":
                if self.profile in {"speed", "instant", "fast"}:
                    window_s = 3.8 if stable else 2.4
                elif self.profile in {"accurate", "quality"}:
                    window_s = 8.0 if stable else 4.5
                else:
                    window_s = 6.0 if stable else 3.2
            if use_fast_preview and not stable:
                window_s = min(window_s, 4.0)
            maximum = int(window_s * TARGET_SAMPLE_RATE)
            if len(inference_audio) > maximum:
                inference_audio = inference_audio[-maximum:]
            allow_quality_retry = bool(
                stable
                and not use_fast_preview
                and self.profile in {"accurate", "quality"}
            )
            text, info, task, reasons, quality_retry, _duration = self._run_transcription(
                active_model,
                inference_audio,
                source_language,
                specialist=active_specialist,
                allow_retry=allow_quality_retry,
                stable=stable,
            )
            self._last_reject_reasons = reasons

            detected = str(getattr(info, "language", decision.detected_language or source_language or "") or "")
            probability = float(getattr(info, "language_probability", decision.probability or 0.0) or 0.0)
            if not self.session_language and detected and probability >= 0.55:
                self.session_language = detected
                emit_event(
                    "state",
                    state="LANGUAGE_PROVISIONAL_LOCK",
                    detected_language=detected,
                    language_probability=probability,
                    local_realtime=True,
                )
            metadata = {
                "requested_language": self.requested_language,
                "detected_language": detected,
                "language_probability": probability,
                "source_language": source_language,
                "bridge_language": "en",
                "asr_task": task,
                "japanese_specialist": bool(self.specialist_active),
                "language_watchdog_state": decision.state,
                "quality_retry": quality_retry,
                "asr_ms": max(0, int((time.perf_counter() - started) * 1000.0)),
                "provisional": bool(use_fast_preview),
                "specialist_correction_pending": bool(stable and use_fast_preview and self.specialist_correction_enabled),
                "model_used": self.fast_preview_model_size if use_fast_preview else self.model_size,
            }
            if reasons:
                metadata["quality_reject_reasons"] = reasons
                return "", metadata
            return text, metadata
        except Exception as exc:
            if self.device == "cuda" and self.allow_cpu_fallback and not self._fallback_used and self._looks_like_cuda_runtime_error(exc):
                self._fallback_to_cpu(exc)
                return self.transcribe(samples, stable=stable)
            raise


class FakeModelAdapter:
    """Deterministic recognizer used only by the packaged integration self-test."""

    device = "cpu"
    compute_type = "fake"
    model_size = "fake-streaming"

    def transcribe(self, samples: np.ndarray, stable: bool = False) -> tuple[str, dict]:
        seconds = len(samples) / float(TARGET_SAMPLE_RATE)
        if seconds < 1.20:
            text = "Saya"
        elif seconds < 2.10:
            text = "Saya sedang mencoba"
        elif seconds < 3.10:
            text = "Saya sedang mencoba terjemahan langsung"
        else:
            text = "Saya sedang mencoba terjemahan langsung tanpa menunggu jeda"
        return text, {"detected_language": "id", "language_probability": 1.0, "asr_ms": 12}


class LatestCorrectionMailbox:
    """Keeps only the latest stable segment for an expensive correction pass."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._latest: Optional[Snapshot] = None
        self._closed = False

    def put(self, snapshot: Snapshot) -> None:
        with self._condition:
            self._latest = snapshot
            self._condition.notify_all()

    def get(self, timeout: float = 0.2) -> Optional[Snapshot]:
        deadline = time.monotonic() + max(0.01, float(timeout))
        with self._condition:
            while not self._closed and self._latest is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            snapshot = self._latest
            self._latest = None
            return snapshot

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class SpecialistCorrectionWorker:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.mailbox = LatestCorrectionMailbox()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ort-kotoba-correction", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit(self, snapshot: Snapshot) -> None:
        self.mailbox.put(snapshot)

    def stop(self) -> None:
        self.stop_event.set()
        self.mailbox.close()
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            snapshot = self.mailbox.get(0.2)
            if snapshot is None:
                continue
            started = time.perf_counter()
            try:
                text, metadata = self.model.transcribe_specialist_correction(snapshot.samples)
                if not text:
                    emit_event(
                        "state",
                        state="SPECIALIST_CORRECTION_SKIPPED",
                        segment_id=snapshot.result_id,
                        reasons=list(metadata.get("quality_reject_reasons") or []),
                        local_realtime=True,
                    )
                    continue
                emit_event(
                    "transcript",
                    segment_id=snapshot.result_id,
                    result_id=snapshot.result_id,
                    revision=snapshot.revision + 100000,
                    stable=True,
                    text=text,
                    audio_seconds=round(snapshot.audio_seconds, 3),
                    model=str(metadata.pop("model_used", "kotoba-bilingual")),
                    profile="specialist-correction",
                    asr_device="cpu",
                    asr_compute_type="int8",
                    correction_elapsed_ms=max(0, int((time.perf_counter() - started) * 1000.0)),
                    local_realtime=True,
                    **metadata,
                )
            except Exception as exc:
                emit_event(
                    "state",
                    state="SPECIALIST_CORRECTION_FAILED",
                    segment_id=snapshot.result_id,
                    message=str(exc),
                    local_realtime=True,
                )


class StreamingInferenceWorker:
    def __init__(self, model: Any) -> None:
        self.model = model
        profile = str(getattr(model, "profile", "normal") or "normal").lower()
        self.mailbox = LatestSnapshotMailbox(max_finals=4 if profile in {"accurate", "quality"} else 2)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ort-local-realtime-asr", daemon=True)
        self.last_text_by_result: dict[str, str] = {}
        self.last_emit_at_by_result: dict[str, float] = {}
        self.last_reject_at_by_result: dict[str, float] = {}
        self.feedback: queue.SimpleQueue[dict] = queue.SimpleQueue()
        self.profile = profile
        # Subtitle context is intentionally bounded. Long monologues are rolled
        # into new subtitle windows instead of growing one paragraph forever.
        display_words = 48 if profile in {"accurate", "quality"} else 36 if profile == "normal" else 28
        self.turn_context = RollingTurnContext(max_history_words=96, display_words=display_words)
        self.final_done: dict[str, threading.Event] = {}
        self.correction_worker: Optional[SpecialistCorrectionWorker] = None
        if bool(getattr(model, "specialist_correction_enabled", False)):
            self.correction_worker = SpecialistCorrectionWorker(model)

    def push_feedback(self, kind: str, result_id: str, *, text: str = "", stable: bool = False) -> None:
        self.feedback.put({
            "kind": str(kind),
            "result_id": str(result_id or ""),
            "text": _clean_text(text),
            "stable": bool(stable),
            "at": time.monotonic(),
        })

    def drain_feedback(self) -> list[dict]:
        rows: list[dict] = []
        while True:
            try:
                rows.append(self.feedback.get_nowait())
            except queue.Empty:
                break
        return rows

    def start(self) -> None:
        self.thread.start()
        if self.correction_worker is not None:
            self.correction_worker.start()

    def submit(self, snapshot: Snapshot) -> None:
        if snapshot.stable:
            self.final_done.setdefault(snapshot.result_id, threading.Event())
        self.mailbox.put(snapshot)

    def wait_final(self, result_id: str, timeout: float = 3.0) -> bool:
        event = self.final_done.setdefault(result_id, threading.Event())
        return event.wait(max(0.0, float(timeout)))

    def stop(self) -> None:
        self.stop_event.set()
        self.mailbox.close()
        if self.thread.is_alive():
            self.thread.join(timeout=4.0)
        if self.correction_worker is not None:
            self.correction_worker.stop()

    def _minimum_display_interval(self) -> float:
        if self.profile in {"speed", "instant", "fast"}:
            return 0.30
        if self.profile in {"accurate", "quality"}:
            return 0.58
        return 0.46

    def _should_emit_partial(self, result_id: str, previous: str, current: str, now: float) -> bool:
        if not _has_semantic_text(current):
            return False
        if not previous:
            return True
        if _clean_text(previous).casefold() == _clean_text(current).casefold():
            return False
        elapsed = now - float(self.last_emit_at_by_result.get(result_id, 0.0) or 0.0)
        if elapsed >= self._minimum_display_interval():
            return True
        # Allow fast prefix growth, but coalesce full rewrites. Rolling ASR may
        # revise every word at 300 ms; displaying each revision makes the
        # Indonesian subtitle look broken even though inference is fast.
        old = _clean_text(previous)
        clean = _clean_text(current)
        prefix_growth = clean.casefold().startswith(old.casefold()) and len(clean) >= len(old) + max(4, int(len(old) * 0.30))
        if prefix_growth:
            return True
        # A completed clause may appear slightly before the normal interval, but
        # never on every 300 ms rewrite.
        if clean.endswith((".", "!", "?", "…")) and len(clean) >= 5:
            return elapsed >= self._minimum_display_interval() * 0.65
        return False

    def _emit_reject_throttled(self, snapshot: Snapshot, metadata: dict) -> None:
        now = time.monotonic()
        last = float(self.last_reject_at_by_result.get(snapshot.result_id, 0.0) or 0.0)
        reasons = list(metadata.get("quality_reject_reasons") or ["EMPTY", "NO_SPEECH"])
        important = any(reason not in {"EMPTY", "NO_SPEECH"} for reason in reasons)
        if not snapshot.stable and not important and now - last < 1.2:
            return
        self.last_reject_at_by_result[snapshot.result_id] = now
        emit_event(
            "quality_reject",
            segment_id=snapshot.result_id,
            reasons=reasons,
            metrics={
                "audio_seconds": snapshot.audio_seconds,
                "asr_ms": metadata.get("asr_ms", 0),
                "quality_retry": bool(metadata.get("quality_retry")),
            },
            overlay_visible=False,
            local_realtime=True,
        )

    def _run(self) -> None:
        while not self.stop_event.is_set():
            snapshot = self.mailbox.get(0.2)
            if snapshot is None:
                continue
            try:
                text, metadata = self.model.transcribe(snapshot.samples, stable=snapshot.stable)
                previous = self.last_text_by_result.get(snapshot.result_id, "")
                final_context_fallback = bool(
                    snapshot.stable
                    and previous
                    and (not text or not _has_semantic_text(text))
                )
                if final_context_fallback:
                    text = previous
                    metadata.pop("quality_reject_reasons", None)
                    metadata["final_context_fallback"] = True
                    metadata["turn_context_words"] = len(previous.split())
                    metadata["turn_display_words"] = len(previous.split())
                    metadata["turn_context_truncated"] = previous.startswith("… ")
                    metadata["turn_context_revision"] = 0
                    metadata["turn_appended_words"] = 0
                elif not text or not _has_semantic_text(text):
                    self.push_feedback("no_speech", snapshot.result_id, stable=snapshot.stable)
                    self._emit_reject_throttled(snapshot, metadata)
                    continue
                if not final_context_fallback:
                    context = self.turn_context.update(snapshot.result_id, text, stable=snapshot.stable)
                    text = context.text
                    metadata["turn_context_words"] = context.full_words
                    metadata["turn_display_words"] = context.words
                    metadata["turn_context_truncated"] = context.truncated
                    metadata["turn_context_revision"] = context.revisions
                    metadata["turn_appended_words"] = context.appended_words
                now = time.monotonic()
                if not snapshot.stable and not self._should_emit_partial(snapshot.result_id, previous, text, now):
                    continue
                self.last_text_by_result[snapshot.result_id] = text
                self.last_emit_at_by_result[snapshot.result_id] = now
                self.push_feedback("semantic", snapshot.result_id, text=text, stable=snapshot.stable)
                event_type = "transcript" if snapshot.stable else "partial_transcript"
                model_used = str(metadata.pop("model_used", getattr(self.model, "model_size", "")))
                emit_event(
                    event_type,
                    segment_id=snapshot.result_id,
                    result_id=snapshot.result_id,
                    revision=snapshot.revision,
                    stable=bool(snapshot.stable),
                    text=text,
                    audio_seconds=round(snapshot.audio_seconds, 3),
                    model=model_used,
                    profile="realtime",
                    asr_device="cpu" if metadata.get("provisional") else str(getattr(self.model, "device", "cpu")),
                    asr_compute_type="int8" if metadata.get("provisional") else str(getattr(self.model, "compute_type", "")),
                    local_realtime=True,
                    **metadata,
                )
                if (
                    snapshot.stable
                    and bool(metadata.get("specialist_correction_pending"))
                    and self.correction_worker is not None
                ):
                    self.correction_worker.submit(snapshot)
            except Exception as exc:
                emit_event(
                    "error",
                    stage="local_realtime_asr",
                    code="LOCAL_REALTIME_ASR_FAILED",
                    message=str(exc),
                    fatal=True,
                    local_realtime=True,
                )
            finally:
                if snapshot.stable:
                    self.final_done.setdefault(snapshot.result_id, threading.Event()).set()
                    emit_event("segment_complete", segment_id=snapshot.result_id, local_realtime=True)
                    self.turn_context.clear(snapshot.result_id)


class UtteranceController:
    def __init__(self, worker: StreamingInferenceWorker, policy: LocalRealtimePolicy) -> None:
        self.worker = worker
        self.policy = policy
        self.pre_roll: Deque[np.ndarray] = deque()
        self.pre_roll_samples = 0
        self.active_chunks: list[np.ndarray] = []
        self.active_samples = 0
        self.turn_samples = 0
        self.active_result_id = ""
        self.revision = 0
        self.last_voice_at = 0.0
        self.last_partial_at = 0.0
        self.noise_floor = 0.0015
        self.sequence = 0
        self.last_semantic_at = 0.0
        self.semantic_silence_since = 0.0
        self.semantic_no_speech_count = 0
        self.last_semantic_text = ""

    def _consume_inference_feedback(self, now: float) -> None:
        for row in self.worker.drain_feedback():
            if str(row.get("result_id") or "") != self.active_result_id:
                continue
            kind = str(row.get("kind") or "")
            if kind == "semantic":
                self.last_semantic_at = float(row.get("at") or now)
                self.last_semantic_text = _clean_text(row.get("text"))
                self.semantic_silence_since = 0.0
                self.semantic_no_speech_count = 0
            elif kind == "no_speech":
                self.semantic_no_speech_count += 1
                if self.semantic_silence_since <= 0.0:
                    self.semantic_silence_since = float(row.get("at") or now)

    def _semantic_boundary_ready(self, now: float) -> tuple[bool, str]:
        if not self.active_result_id or not self.last_semantic_text:
            return False, ""
        if self.semantic_no_speech_count < self.policy.semantic_no_speech_passes:
            return False, ""
        since = self.semantic_silence_since or self.last_semantic_at
        silence = max(0.0, now - since)
        sentence_end = self.last_semantic_text.rstrip().endswith((".", "!", "?", "…"))
        threshold = self.policy.short_pause_s if sentence_end else self.policy.long_pause_s
        if silence >= threshold:
            return True, "semantic_sentence_pause" if sentence_end else "semantic_long_pause"
        return False, ""

    def _rollover_ready(self, duration: float) -> tuple[bool, str]:
        if duration >= self.policy.hard_turn_s:
            return True, "hard_turn_limit"
        if duration < self.policy.subtitle_window_s:
            return False, ""
        if not self.last_semantic_text:
            return False, ""
        sentence_end = self.last_semantic_text.rstrip().endswith((".", "!", "?", "…"))
        if sentence_end or self.semantic_no_speech_count > 0:
            return True, "subtitle_window"
        return False, ""

    def _append_pre_roll(self, chunk: np.ndarray) -> None:
        self.pre_roll.append(chunk.copy())
        self.pre_roll_samples += len(chunk)
        maximum = max(1, int(self.policy.pre_roll_s * TARGET_SAMPLE_RATE))
        while self.pre_roll and self.pre_roll_samples > maximum:
            removed = self.pre_roll.popleft()
            self.pre_roll_samples -= len(removed)

    def _start(self, now: float) -> None:
        self.sequence += 1
        self.active_result_id = f"live-{int(now * 1000)}-{self.sequence:06d}"
        self.active_chunks = [item.copy() for item in self.pre_roll]
        self.active_samples = sum(len(item) for item in self.active_chunks)
        self.turn_samples = self.active_samples
        self.revision = 0
        self.last_voice_at = now
        self.last_partial_at = 0.0
        self.last_semantic_at = now
        self.semantic_silence_since = 0.0
        self.semantic_no_speech_count = 0
        self.last_semantic_text = ""
        emit_event(
            "state",
            state="SPEECH_ACTIVE",
            segment_id=self.active_result_id,
            local_realtime=True,
        )

    def _snapshot(self, stable: bool, now: float) -> Optional[Snapshot]:
        if not self.active_result_id or self.active_samples <= 0:
            return None
        self.revision += 1
        samples = np.concatenate(self.active_chunks).astype(np.float32, copy=False)
        return Snapshot(
            result_id=self.active_result_id,
            revision=self.revision,
            samples=samples.copy(),
            stable=stable,
            created_at=now,
            audio_seconds=len(samples) / float(TARGET_SAMPLE_RATE),
        )

    def _trim_active_window(self) -> None:
        """Keep ASR memory bounded without ending the active speaking turn."""
        maximum = max(1, int(self.policy.max_phrase_s * TARGET_SAMPLE_RATE))
        if self.active_samples <= maximum:
            return
        full = np.concatenate(self.active_chunks).astype(np.float32, copy=False)
        kept = full[-maximum:].astype(np.float32, copy=True)
        self.active_chunks = [kept]
        self.active_samples = len(kept)
        emit_event(
            "metric",
            name="continuous_turn_window_shift",
            segment_id=self.active_result_id,
            retained_audio_seconds=round(self.active_samples / float(TARGET_SAMPLE_RATE), 3),
            turn_audio_seconds=round(self.turn_samples / float(TARGET_SAMPLE_RATE), 3),
            local_realtime=True,
        )

    def _finish(self, now: float, carry: bool) -> str:
        result_id = self.active_result_id
        snapshot = self._snapshot(True, now)
        carry_samples = max(0, int(self.policy.carry_over_s * TARGET_SAMPLE_RATE))
        carry_chunk = np.empty(0, dtype=np.float32)
        if carry and self.active_chunks and carry_samples:
            full = np.concatenate(self.active_chunks)
            carry_chunk = full[-carry_samples:].astype(np.float32, copy=True)
        if snapshot is not None:
            self.worker.submit(snapshot)
        self.active_chunks = []
        self.active_samples = 0
        self.turn_samples = 0
        self.active_result_id = ""
        self.revision = 0
        self.last_partial_at = 0.0
        self.last_semantic_at = 0.0
        self.semantic_silence_since = 0.0
        self.semantic_no_speech_count = 0
        self.last_semantic_text = ""
        self.pre_roll.clear()
        self.pre_roll_samples = 0
        if carry and carry_chunk.size:
            self.pre_roll.append(carry_chunk)
            self.pre_roll_samples = len(carry_chunk)
            self._start(now)
        return result_id

    def feed(self, chunk: np.ndarray, now: Optional[float] = None) -> None:
        current = time.monotonic() if now is None else float(now)
        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return
        self._consume_inference_feedback(current)
        level = _rms(samples)
        threshold = max(self.policy.minimum_rms, self.noise_floor * self.policy.noise_multiplier)
        speech = level >= threshold
        if not speech and not self.active_result_id:
            self.noise_floor = max(0.0005, min(0.02, self.noise_floor * 0.97 + level * 0.03))
        self._append_pre_roll(samples)

        started_now = False
        if not self.active_result_id:
            if speech:
                self._start(current)
                started_now = True
            else:
                return

        if not started_now:
            self.active_chunks.append(samples.copy())
            self.active_samples += len(samples)
            self.turn_samples += len(samples)
        if speech:
            self.last_voice_at = current

        duration = self.turn_samples / float(TARGET_SAMPLE_RATE)
        if duration >= self.policy.first_partial_s:
            if self.last_partial_at <= 0.0 or current - self.last_partial_at >= self.policy.partial_interval_s:
                snapshot = self._snapshot(False, current)
                if snapshot is not None:
                    self.worker.submit(snapshot)
                    self.last_partial_at = current

        if self.active_samples / float(TARGET_SAMPLE_RATE) > self.policy.max_phrase_s:
            self._trim_active_window()

        semantic_ready, semantic_reason = self._semantic_boundary_ready(current)
        rollover_ready, rollover_reason = self._rollover_ready(duration)
        # Energy VAD alone must not cut a long monologue at every tiny pause.
        # Once semantic text exists, use a shorter threshold only after sentence
        # punctuation and a longer threshold for an unfinished clause.
        if self.last_semantic_text:
            semantic_sentence_end = self.last_semantic_text.rstrip().endswith((".", "!", "?", "…"))
            energy_threshold = self.policy.short_pause_s if semantic_sentence_end else self.policy.long_pause_s
        else:
            energy_threshold = self.policy.endpoint_s
        energy_pause = bool(not speech and current - self.last_voice_at >= energy_threshold)
        if semantic_ready or energy_pause:
            reason = semantic_reason or ("energy_sentence_pause" if self.last_semantic_text.rstrip().endswith((".", "!", "?", "…")) else "energy_long_pause")
            emit_event(
                "metric",
                name="smart_turn_boundary",
                segment_id=self.active_result_id,
                reason=reason,
                turn_audio_seconds=round(duration, 3),
                semantic_no_speech_count=self.semantic_no_speech_count,
                local_realtime=True,
            )
            self._finish(current, carry=False)
        elif rollover_ready:
            emit_event(
                "metric",
                name="subtitle_window_rollover",
                segment_id=self.active_result_id,
                reason=rollover_reason,
                turn_audio_seconds=round(duration, 3),
                local_realtime=True,
            )
            self._finish(current, carry=True)

    def flush(self, now: Optional[float] = None) -> str:
        if not self.active_result_id:
            return ""
        return self._finish(time.monotonic() if now is None else float(now), carry=False)


def _resolve_loopback_device(manager: Any, requested_index: int) -> dict:
    loopbacks = [dict(item) for item in manager.get_loopback_device_info_generator()]
    if requested_index >= 0:
        for item in loopbacks:
            if int(item.get("index", -1)) == requested_index:
                return item
        raise RuntimeError(f"Perangkat loopback index {requested_index} tidak ditemukan.")
    try:
        return dict(manager.get_default_wasapi_loopback())
    except Exception:
        pass
    if loopbacks:
        return loopbacks[0]
    raise RuntimeError("WASAPI loopback tidak ditemukan. Pastikan perangkat output aktif.")


def _stream_loopback(controller: UtteranceController, device_index: int, policy: LocalRealtimePolicy) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Audio internal real-time lokal memerlukan Windows WASAPI.")
    import pyaudiowpatch as pyaudio

    last_meter = 0.0
    with pyaudio.PyAudio() as manager:
        device = _resolve_loopback_device(manager, int(device_index))
        channels = max(1, int(device.get("maxInputChannels", 1)))
        source_rate = int(float(device.get("defaultSampleRate", 48000)))
        source_index = int(device.get("index", -1))
        source_name = str(device.get("name") or "WASAPI Loopback")
        frames_per_buffer = max(256, min(2048, int(source_rate * policy.chunk_ms / 1000.0)))
        emit_event(
            "state",
            state="STREAMING",
            device=source_name,
            device_index=source_index,
            channels=channels,
            sample_rate=source_rate,
            local_realtime=True,
            **policy.as_dict(),
        )
        with manager.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=source_rate,
            frames_per_buffer=frames_per_buffer,
            input=True,
            input_device_index=source_index,
        ) as stream:
            while not STOP_REQUESTED:
                payload = stream.read(frames_per_buffer, exception_on_overflow=False)
                mono = _mono_float_from_pcm16(payload, channels)
                audio_16k = _resample_linear(mono, source_rate)
                now = time.monotonic()
                controller.feed(audio_16k, now)
                if now - last_meter >= 0.5:
                    emit_event("meter", rms=round(_rms(audio_16k), 6), speech_active=bool(controller.active_result_id), local_realtime=True)
                    last_meter = now


def _stream_wav(controller: UtteranceController, path: Path, policy: LocalRealtimePolicy) -> None:
    with wave.open(str(path), "rb") as source:
        channels = max(1, int(source.getnchannels()))
        width = int(source.getsampwidth())
        source_rate = int(source.getframerate())
        if width != 2:
            raise RuntimeError("Uji local realtime memerlukan WAV PCM 16-bit.")
        frames_per_chunk = max(1, int(source_rate * policy.chunk_ms / 1000.0))
        emit_event(
            "state",
            state="STREAMING",
            device=str(path),
            channels=channels,
            sample_rate=source_rate,
            local_realtime=True,
            **policy.as_dict(),
        )
        while not STOP_REQUESTED:
            payload = source.readframes(frames_per_chunk)
            if not payload:
                break
            mono = _mono_float_from_pcm16(payload, channels)
            audio_16k = _resample_linear(mono, source_rate)
            controller.feed(audio_16k, time.monotonic())
            time.sleep(len(audio_16k) / float(TARGET_SAMPLE_RATE))


def _wait_for_start_gate(path_value: str, timeout_s: float = 180.0) -> None:
    token = str(path_value or "").strip()
    if not token:
        return
    gate = Path(token).expanduser().resolve()
    emit_event(
        "state",
        state="PRELOAD_WAITING_FOR_START",
        start_gate=str(gate),
        local_realtime=True,
    )
    deadline = time.monotonic() + max(10.0, float(timeout_s))
    while not STOP_REQUESTED:
        if gate.is_file():
            emit_event(
                "state",
                state="PRELOAD_ACTIVATED",
                start_gate=str(gate),
                local_realtime=True,
            )
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Audio Lab preload gate timeout: {gate}")
        time.sleep(0.05)
    raise RuntimeError("Audio Lab dihentikan sebelum capture diaktifkan.")


def run_stream(args: argparse.Namespace) -> int:
    requested_language = str(args.language or "auto")
    language = _language_code(requested_language)
    japanese_specialist = _is_japanese_specialist_mode(requested_language) or (
        language in {None, "ja"}
        and str(os.environ.get("ORT_AUDIO_JA_SPECIALIST", "auto")).lower() in {"1", "true", "yes", "on", "auto"}
    )
    policy = resolve_policy(args.profile, args.asr_device)
    model = ModelAdapter(
        model_root=Path(args.model_root).expanduser().resolve(),
        model_size=args.model_size,
        fallback_model_size=args.fallback_model_size,
        device=args.asr_device,
        compute_type=args.compute_type,
        cpu_threads=args.cpu_threads,
        language=language,
        allow_cpu_fallback=bool(args.allow_cpu_fallback),
        game=args.game,
        requested_language=requested_language,
        japanese_specialist=japanese_specialist,
        language_correction_mode=args.language_correction,
        language_locked=bool(args.language_lock),
        profile=args.profile,
    )
    try:
        model.load()
        active_policy = resolve_policy(args.profile, model.device)
        worker = StreamingInferenceWorker(model)
        worker.start()
        controller = UtteranceController(worker, active_policy)
        emit_event(
            "state",
            state="LOCAL_REALTIME_READY",
            model=model.model_size,
            device=model.device,
            compute_type=model.compute_type,
            language=language or "auto",
            requested_language=requested_language,
            bridge_language="en",
            asr_task=("transcribe" if language == "en" else "translate"),
            japanese_specialist=bool(model.specialist_active),
            language_correction=model.language_watchdog.policy.mode,
            language_locked=model.language_locked,
            continuous_turn_context=True,
            context_history_words=96,
            local_realtime=True,
            **active_policy.as_dict(),
        )
        _wait_for_start_gate(args.start_gate_file)
        if args.input_mode == "file":
            test_path = Path(args.test_file).expanduser().resolve()
            if not test_path.is_file():
                raise FileNotFoundError(f"File audio uji tidak ditemukan: {test_path}")
            _stream_wav(controller, test_path, active_policy)
        else:
            _stream_loopback(controller, int(args.device_index), active_policy)
        final_id = controller.flush()
        if final_id:
            worker.wait_final(final_id, 4.0)
        worker.stop()
        emit_event("state", state="STOPPED", local_realtime=True)
        return 0
    except Exception as exc:
        emit_event(
            "error",
            stage="local_realtime_stream",
            code="LOCAL_REALTIME_STREAM_FAILED",
            message=str(exc),
            fatal=True,
            local_realtime=True,
        )
        return 1


def run_self_test() -> int:
    global _EVENT_SINK
    events: list[dict] = []
    _EVENT_SINK = events
    try:
        model = FakeModelAdapter()
        policy = LocalRealtimePolicy(
            profile="self-test",
            first_partial_s=0.30,
            partial_interval_s=0.25,
            endpoint_s=0.30,
            max_phrase_s=6.0,
            pre_roll_s=0.10,
            carry_over_s=0.10,
            minimum_rms=0.003,
            noise_multiplier=2.0,
            short_pause_s=0.20,
            long_pause_s=0.55,
            subtitle_window_s=5.0,
            hard_turn_s=9.0,
        )
        worker = StreamingInferenceWorker(model)
        worker.start()
        controller = UtteranceController(worker, policy)
        start = 1000.0
        chunk_samples = int(TARGET_SAMPLE_RATE * 0.02)
        phase = np.arange(chunk_samples, dtype=np.float32)
        speech_chunk = (0.05 * np.sin(2.0 * np.pi * 220.0 * phase / TARGET_SAMPLE_RATE)).astype(np.float32)
        silence_chunk = np.zeros(chunk_samples, dtype=np.float32)
        # Four seconds of uninterrupted speech: partials must be generated before
        # any pause or endpoint occurs.
        for index in range(200):
            controller.feed(speech_chunk, start + index * 0.02)
            time.sleep(0.001)
        # Silence is only used to commit the final result.
        for index in range(20):
            controller.feed(silence_chunk, start + 4.0 + index * 0.02)
            time.sleep(0.001)
        final_id = controller.flush(start + 4.5)
        if final_id:
            worker.wait_final(final_id, 2.0)
        time.sleep(0.1)
        worker.stop()

        partials = [item for item in events if item.get("type") == "partial_transcript"]
        finals = [item for item in events if item.get("type") == "transcript" and item.get("stable")]
        translated_displays = [
            {
                "at_audio_s": item.get("audio_seconds"),
                "source": item.get("text"),
                "translation": "ID · " + str(item.get("text") or ""),
                "stable": bool(item.get("stable")),
            }
            for item in partials + finals
        ]
        first_partial_audio_s = float(partials[0].get("audio_seconds", 99.0)) if partials else 99.0
        passed = bool(
            len(partials) >= 3
            and len(finals) >= 1
            and first_partial_audio_s < 1.2
            and all(not item.get("stable") for item in partials)
            and translated_displays
        )
        payload = {
            "passed": passed,
            "continuous_speech_seconds": 4.0,
            "partial_count": len(partials),
            "final_count": len(finals),
            "first_partial_audio_ms": int(first_partial_audio_s * 1000),
            "translation_updates_before_final": len(partials),
            "pause_required_for_first_translation": False,
            "display_trace": translated_displays[:8],
        }
    finally:
        _EVENT_SINK = None
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0 if payload.get("passed") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORT local rolling-partial real-time ASR sidecar")
    parser.add_argument("--stream-json", action="store_true")
    parser.add_argument("--self-test-json", action="store_true")
    parser.add_argument("--profile", default="normal")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-root", default="")
    parser.add_argument("--model-size", default="base")
    parser.add_argument("--fallback-model-size", default="base")
    parser.add_argument("--asr-device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--cpu-threads", type=int, default=max(1, min(4, os.cpu_count() or 4)))
    parser.add_argument("--input-mode", choices=["loopback", "file"], default="loopback")
    parser.add_argument("--device-index", default="-1")
    parser.add_argument("--test-file", default="")
    parser.add_argument("--game", default="GFL2_EXILIUM")
    parser.add_argument("--allow-cpu-fallback", action="store_true")
    parser.add_argument("--language-correction", default=os.environ.get("ORT_AUDIO_LANGUAGE_AUTOCORRECT", "balanced"))
    parser.add_argument("--language-lock", action="store_true", default=str(os.environ.get("ORT_AUDIO_LANGUAGE_LOCK", "0")).lower() in {"1", "true", "yes", "on"})
    parser.add_argument("--start-gate-file", default=os.environ.get("ORT_AUDIO_START_GATE_FILE", ""))
    return parser


def main() -> int:
    _install_signal_handlers()
    args = build_parser().parse_args()
    if args.self_test_json:
        return run_self_test()
    if args.stream_json:
        return run_stream(args)
    print("Use --stream-json or --self-test-json", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
