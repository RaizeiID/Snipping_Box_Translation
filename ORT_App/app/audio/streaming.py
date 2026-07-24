from __future__ import annotations

import math
import time
from collections import deque
from typing import Deque, Optional

import numpy as np

from .profiles import AudioProfile


def pcm16_to_mono_float(payload: bytes, channels: int) -> np.ndarray:
    if not payload:
        return np.empty(0, dtype=np.float32)
    samples = np.frombuffer(payload, dtype=np.int16)
    channel_count = max(1, int(channels or 1))
    usable = samples.size - (samples.size % channel_count)
    if usable <= 0:
        return np.empty(0, dtype=np.float32)
    shaped = samples[:usable].reshape(-1, channel_count).astype(np.float32)
    mono = shaped.mean(axis=1) if channel_count > 1 else shaped[:, 0]
    return np.clip(mono / 32768.0, -1.0, 1.0).astype(np.float32, copy=False)


def resample_linear(audio: np.ndarray, source_rate: int, target_rate: int = 16000) -> np.ndarray:
    signal = np.asarray(audio, dtype=np.float32).reshape(-1)
    src = max(1, int(source_rate or target_rate))
    dst = max(1, int(target_rate))
    if signal.size == 0 or src == dst:
        return signal.astype(np.float32, copy=False)
    target_length = max(1, int(round(signal.size * (dst / float(src)))))
    old_positions = np.linspace(0.0, 1.0, num=signal.size, endpoint=False, dtype=np.float64)
    new_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False, dtype=np.float64)
    return np.interp(new_positions, old_positions, signal).astype(np.float32)


def audio_rms(audio: np.ndarray) -> float:
    signal = np.asarray(audio, dtype=np.float32).reshape(-1)
    if signal.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(np.square(signal), dtype=np.float64)) + 1e-12))


class LiveAudioSegmenter:
    def __init__(self, profile: AudioProfile, processing: str = "vad", sample_rate: int = 16000):
        self.profile = profile
        self.processing = str(processing or "vad").strip().lower()
        if self.processing not in {"normal", "vad"}:
            raise ValueError(f"Unsupported audio processing mode: {self.processing}")
        self.sample_rate = max(8000, int(sample_rate))
        self._normal_parts: list[np.ndarray] = []
        self._normal_samples = 0
        self._speech_parts: list[np.ndarray] = []
        self._speech_samples = 0
        self._speech_active = False
        self._silence_samples = 0
        self._noise_floor = 0.0015
        self._pre_roll: Deque[np.ndarray] = deque()
        self._pre_roll_samples = 0
        self._pre_roll_limit = int(self.sample_rate * (max(120, int(self.profile.pre_roll_ms)) / 1000.0))

    @property
    def speech_active(self) -> bool:
        return self._speech_active

    @property
    def threshold(self) -> float:
        return max(float(self.profile.vad_threshold), min(0.05, self._noise_floor * 2.35))

    def feed(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        signal = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if signal.size == 0:
            return None
        if self.processing == "normal":
            return self._feed_normal(signal)
        return self._feed_vad(signal)

    def flush(self) -> Optional[np.ndarray]:
        if self.processing == "normal":
            return self._emit_normal() if self._normal_samples else None
        min_samples = int(self.profile.min_speech_seconds * self.sample_rate)
        if self._speech_samples >= min_samples:
            return self._emit_speech()
        self._reset_speech()
        return None

    def _feed_normal(self, signal: np.ndarray) -> Optional[np.ndarray]:
        self._normal_parts.append(signal)
        self._normal_samples += signal.size
        target = int(self.profile.normal_chunk_seconds * self.sample_rate)
        if self._normal_samples < target:
            return None
        return self._emit_normal()

    def _emit_normal(self) -> np.ndarray:
        joined = np.concatenate(self._normal_parts).astype(np.float32, copy=False)
        overlap_count = min(joined.size, int(self.sample_rate * 0.18))
        overlap = joined[-overlap_count:].copy() if overlap_count else np.empty(0, dtype=np.float32)
        self._normal_parts = [overlap] if overlap.size else []
        self._normal_samples = overlap.size
        return joined

    def _feed_vad(self, signal: np.ndarray) -> Optional[np.ndarray]:
        rms = audio_rms(signal)
        if not self._speech_active:
            self._noise_floor = (self._noise_floor * 0.96) + (min(rms, 0.025) * 0.04)
            self._append_pre_roll(signal)
            if rms >= self.threshold:
                self._speech_active = True
                self._speech_parts = list(self._pre_roll)
                self._speech_samples = sum(part.size for part in self._speech_parts)
                self._pre_roll.clear()
                self._pre_roll_samples = 0
                self._silence_samples = 0
            return None

        self._speech_parts.append(signal)
        self._speech_samples += signal.size
        if rms < self.threshold * 0.78:
            self._silence_samples += signal.size
        else:
            self._silence_samples = 0

        min_samples = int(self.profile.min_speech_seconds * self.sample_rate)
        max_samples = int(self.profile.max_speech_seconds * self.sample_rate)
        silence_target = int((self.profile.min_silence_ms / 1000.0) * self.sample_rate)
        if self._speech_samples >= max_samples:
            return self._emit_speech()
        if self._speech_samples >= min_samples and self._silence_samples >= silence_target:
            return self._emit_speech()
        return None

    def _append_pre_roll(self, signal: np.ndarray) -> None:
        self._pre_roll.append(signal)
        self._pre_roll_samples += signal.size
        while self._pre_roll and self._pre_roll_samples > self._pre_roll_limit:
            removed = self._pre_roll.popleft()
            self._pre_roll_samples -= removed.size

    def _emit_speech(self) -> np.ndarray:
        joined = np.concatenate(self._speech_parts).astype(np.float32, copy=False)
        self._reset_speech()
        return joined

    def _reset_speech(self) -> None:
        self._speech_parts = []
        self._speech_samples = 0
        self._speech_active = False
        self._silence_samples = 0


class TranscriptDeduplicator:
    def __init__(self, duplicate_window_seconds: float = 20.0):
        self.duplicate_window_seconds = max(1.0, float(duplicate_window_seconds))
        self._last_text = ""
        self._last_words: list[str] = []
        self._last_at = 0.0

    def accept(self, text: str, allow_overlap_trim: bool = False) -> str:
        clean = " ".join(str(text or "").strip().split())
        if not clean:
            return ""
        now = time.monotonic()
        normalized = clean.casefold()
        if normalized == self._last_text and now - self._last_at <= self.duplicate_window_seconds:
            return ""
        words = clean.split()
        if allow_overlap_trim and self._last_words:
            previous = [word.casefold() for word in self._last_words]
            current = [word.casefold() for word in words]
            limit = min(len(previous), len(current), 14)
            trim = 0
            for count in range(limit, 0, -1):
                if previous[-count:] == current[:count]:
                    trim = count
                    break
            if trim and len(words) - trim >= 2:
                words = words[trim:]
                clean = " ".join(words)
                normalized = clean.casefold()
            elif trim == len(words):
                return ""
        self._last_text = normalized
        self._last_words = words
        self._last_at = now
        return clean
