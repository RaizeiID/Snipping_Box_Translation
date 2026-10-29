"""ORT v9.0.6 Stage 4 pluggable speech detection for the realtime audio path.

The realtime sidecar historically decided "is this speech?" with an RMS level
compared against an adaptive noise floor. That rule cannot tell loud game music
from a speaking character: any sustained tone above the floor reads as speech,
which starts a turn and feeds non-dialog audio into ASR.

This module makes the detector swappable so the energy rule and a neural VAD can
be compared on the same stream:

  heuristic  the original RMS + adaptive noise floor, unchanged
  silero     streaming Silero VAD v6 (ONNX) with hysteresis
  hybrid     energy pre-gate, Silero confirmation (default when VAD is on)

Silero costs no new dependency: onnxruntime and silero_vad_v6.onnx already ship
inside the faster-whisper install used by the audio runtimes. A missing model or
a failed session never breaks capture -- the factory falls back to the energy
detector and reports why.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

import numpy as np


TARGET_SAMPLE_RATE = 16000

# Silero v6 consumes fixed 512-sample windows (32 ms at 16 kHz) and carries a
# 64-sample context tail plus LSTM state between windows.
_SILERO_WINDOW = 512
_SILERO_CONTEXT = 64
_SILERO_STATE = 128


@dataclass(frozen=True)
class SpeechDecision:
    speech: bool
    level: float
    probability: float
    backend: str


class SpeechDetector(Protocol):
    backend: str

    def feed(self, samples: np.ndarray, active: bool) -> SpeechDecision: ...

    def reset(self) -> None: ...

    def describe(self) -> dict: ...


def _rms(samples: np.ndarray) -> float:
    source = np.asarray(samples, dtype=np.float32).reshape(-1)
    if source.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(source), dtype=np.float64)))


class EnergySpeechDetector:
    """The original RMS + adaptive noise floor rule, extracted verbatim.

    The noise floor only adapts while no turn is active, so a long utterance
    cannot raise the floor high enough to mute itself.
    """

    backend = "heuristic"

    def __init__(self, minimum_rms: float, noise_multiplier: float) -> None:
        self.minimum_rms = float(minimum_rms)
        self.noise_multiplier = float(noise_multiplier)
        self.noise_floor = 0.0015

    def feed(self, samples: np.ndarray, active: bool) -> SpeechDecision:
        level = _rms(samples)
        threshold = max(self.minimum_rms, self.noise_floor * self.noise_multiplier)
        speech = level >= threshold
        if not speech and not active:
            self.noise_floor = max(0.0005, min(0.02, self.noise_floor * 0.97 + level * 0.03))
        return SpeechDecision(speech, level, 1.0 if speech else 0.0, self.backend)

    def reset(self) -> None:
        self.noise_floor = 0.0015

    def describe(self) -> dict:
        return {
            "backend": self.backend,
            "minimum_rms": self.minimum_rms,
            "noise_multiplier": self.noise_multiplier,
        }


def resolve_silero_model_path(explicit: str = "") -> Optional[Path]:
    """Locate silero_vad_v6.onnx, preferring an explicit override."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    override = os.environ.get("ORT_AUDIO_VAD_MODEL", "").strip()
    if override:
        candidates.append(Path(override))
    try:
        from faster_whisper.utils import get_assets_path

        assets = Path(get_assets_path())
        candidates.extend([
            assets / "silero_vad_v6.onnx",
            assets / "silero_vad.onnx",
        ])
    except Exception:
        pass
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


class SileroSpeechDetector:
    """Streaming Silero VAD v6.

    faster-whisper's own wrapper is batch-oriented: it rebuilds the LSTM state
    on every call, which is wrong for a live stream. This keeps h/c and the
    context tail across calls and consumes the 20 ms capture chunks by buffering
    them into 512-sample windows.

    Between windows the previous decision is held, so a 20 ms chunk never
    silently reports "no speech" just because a window is not complete yet.
    """

    backend = "silero"

    def __init__(
        self,
        model_path: Path,
        *,
        threshold: float = 0.5,
        neg_threshold: Optional[float] = None,
        intra_op_threads: int = 1,
    ) -> None:
        import onnxruntime

        self.model_path = Path(model_path)
        self.threshold = float(threshold)
        # Hysteresis: entering speech needs `threshold`, leaving it needs to drop
        # below the lower `neg_threshold`. A single threshold makes the decision
        # chatter around quiet consonants and breaks turns mid-word.
        self.neg_threshold = float(
            max(0.01, self.threshold - 0.15) if neg_threshold is None else neg_threshold
        )
        options = onnxruntime.SessionOptions()
        # Keep the VAD on one thread. The ASR model owns the CPU budget; an
        # unbounded ONNX thread pool here would contend with it.
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = max(1, int(intra_op_threads))
        options.enable_cpu_mem_arena = False
        options.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
            sess_options=options,
        )
        self._buffer = np.zeros(0, dtype=np.float32)
        self._triggered = False
        self._probability = 0.0
        self._windows = 0
        self._reset_state()

    def _reset_state(self) -> None:
        self._h = np.zeros((1, 1, _SILERO_STATE), dtype=np.float32)
        self._c = np.zeros((1, 1, _SILERO_STATE), dtype=np.float32)
        self._context = np.zeros((1, _SILERO_CONTEXT), dtype=np.float32)

    def _infer(self, window: np.ndarray) -> float:
        shaped = window.reshape(1, _SILERO_WINDOW)
        batched = np.concatenate([self._context, shaped], axis=1).astype(np.float32)
        output, self._h, self._c = self.session.run(
            None, {"input": batched, "h": self._h, "c": self._c}
        )
        self._context = shaped[:, -_SILERO_CONTEXT:]
        self._windows += 1
        return float(np.asarray(output).reshape(-1)[0])

    def feed(self, samples: np.ndarray, active: bool) -> SpeechDecision:
        del active  # Silero needs no turn state; it is stateless w.r.t. the turn.
        source = np.asarray(samples, dtype=np.float32).reshape(-1)
        level = _rms(source)
        if source.size:
            self._buffer = np.concatenate([self._buffer, source])
        while self._buffer.size >= _SILERO_WINDOW:
            window = self._buffer[:_SILERO_WINDOW]
            self._buffer = self._buffer[_SILERO_WINDOW:]
            probability = self._infer(window)
            self._probability = probability
            if probability >= self.threshold:
                self._triggered = True
            elif probability < self.neg_threshold:
                self._triggered = False
        return SpeechDecision(self._triggered, level, self._probability, self.backend)

    def reset(self) -> None:
        self._buffer = np.zeros(0, dtype=np.float32)
        self._triggered = False
        self._probability = 0.0
        self._reset_state()

    def describe(self) -> dict:
        return {
            "backend": self.backend,
            "model": self.model_path.name,
            "threshold": self.threshold,
            "neg_threshold": self.neg_threshold,
            "windows_processed": self._windows,
        }


class HybridSpeechDetector:
    """Energy pre-gate in front of Silero.

    Silero decides what counts as speech. The energy rule only suppresses audio
    that is far below the adaptive floor, which skips inference during long
    silences and stops a decaying Silero tail from holding a turn open over a
    genuinely quiet stream.
    """

    backend = "hybrid"

    def __init__(self, energy: EnergySpeechDetector, silero: SileroSpeechDetector, *, floor_ratio: float = 0.55) -> None:
        self.energy = energy
        self.silero = silero
        self.floor_ratio = float(floor_ratio)

    def feed(self, samples: np.ndarray, active: bool) -> SpeechDecision:
        energy_decision = self.energy.feed(samples, active)
        floor = max(self.energy.minimum_rms, self.energy.noise_floor * self.energy.noise_multiplier)
        if energy_decision.level < floor * self.floor_ratio:
            # Clearly below the noise floor. Keep Silero's stream continuous by
            # still feeding it, but do not let a stale trigger survive silence.
            decision = self.silero.feed(samples, active)
            return SpeechDecision(False, energy_decision.level, decision.probability, self.backend)
        decision = self.silero.feed(samples, active)
        return SpeechDecision(decision.speech, energy_decision.level, decision.probability, self.backend)

    def reset(self) -> None:
        self.energy.reset()
        self.silero.reset()

    def describe(self) -> dict:
        payload = {"backend": self.backend, "floor_ratio": self.floor_ratio}
        payload.update({f"silero_{k}": v for k, v in self.silero.describe().items() if k != "backend"})
        payload.update({f"energy_{k}": v for k, v in self.energy.describe().items() if k != "backend"})
        return payload


def normalize_backend(value: str) -> str:
    key = str(value or "heuristic").strip().lower().replace("-", "_")
    if key in {"silero", "neural", "vad_silero"}:
        return "silero"
    if key in {"hybrid", "auto", "mixed"}:
        return "hybrid"
    return "heuristic"


def build_speech_detector(
    backend: str,
    *,
    minimum_rms: float,
    noise_multiplier: float,
    threshold: float = 0.5,
    neg_threshold: Optional[float] = None,
    model_path: str = "",
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> SpeechDetector:
    """Build the requested detector, degrading to energy instead of failing.

    Audio capture must never die because a VAD model is missing, so every
    failure path returns a working energy detector and reports the reason.
    """
    requested = normalize_backend(backend)
    energy = EnergySpeechDetector(minimum_rms, noise_multiplier)
    if requested == "heuristic":
        return energy

    def report(reason: str, detail: str = "") -> None:
        if on_event is not None:
            on_event(
                "VAD_BACKEND_FALLBACK",
                {
                    "requested_backend": requested,
                    "effective_backend": energy.backend,
                    "reason": reason,
                    "detail": detail,
                },
            )

    located = resolve_silero_model_path(model_path)
    if located is None:
        report("VAD_MODEL_MISSING", "silero_vad_v6.onnx not found in faster-whisper assets")
        return energy
    try:
        silero = SileroSpeechDetector(
            located, threshold=threshold, neg_threshold=neg_threshold
        )
    except Exception as exc:
        report("VAD_SESSION_FAILED", f"{type(exc).__name__}: {exc}")
        return energy
    if requested == "silero":
        return silero
    return HybridSpeechDetector(energy, silero)
