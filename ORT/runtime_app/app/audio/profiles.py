from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class AudioProfile:
    key: str
    label: str
    model_size: str
    gpu_model_size: str
    hybrid_fallback_model_size: str
    cpu_threads: int
    beam_size: int
    best_of: int
    retry_beam_size: int
    normal_chunk_seconds: float
    min_speech_seconds: float
    max_speech_seconds: float
    min_silence_ms: int
    speech_pad_ms: int
    pre_roll_ms: int
    vad_threshold: float
    description: str


_PROFILES: Dict[str, AudioProfile] = {
    "speed": AudioProfile("speed", "Speed", "base", "small", "base", 3, 1, 1, 2, 2.6, 0.40, 4.2, 320, 200, 280, 0.0075, "Respons tercepat; Base INT8 pada CPU dan Small INT8-FP16 pada GPU."),
    "normal": AudioProfile("normal", "Normal", "base", "small", "base", 4, 1, 1, 2, 3.2, 0.45, 6.5, 420, 220, 320, 0.0060, "Realtime stabil: Base INT8 pada CPU, Small INT8-FP16 pada GPU, tanpa retry ganda selama live."),
    "accurate": AudioProfile("accurate", "Accurate", "small", "medium", "small", 6, 5, 5, 7, 4.8, 0.70, 10.0, 680, 300, 440, 0.0050, "Pencarian terlebar; Medium pada GPU dan Small pada CPU dengan kebutuhan sumber daya lebih besar."),
}


def get_audio_profile(key: str | None) -> AudioProfile:
    return _PROFILES.get(str(key or "normal").strip().lower(), _PROFILES["normal"])


def profile_choices() -> Tuple[Tuple[str, str], ...]:
    return tuple((profile.label, profile.key) for profile in _PROFILES.values())


def profile_payload(key: str | None) -> dict:
    profile = get_audio_profile(key)
    return {
        "key": profile.key,
        "label": profile.label,
        "model_size": profile.model_size,
        "gpu_model_size": profile.gpu_model_size,
        "hybrid_fallback_model_size": profile.hybrid_fallback_model_size,
        "cpu_threads": profile.cpu_threads,
        "beam_size": profile.beam_size,
        "best_of": profile.best_of,
        "retry_beam_size": profile.retry_beam_size,
        "normal_chunk_seconds": profile.normal_chunk_seconds,
        "min_speech_seconds": profile.min_speech_seconds,
        "max_speech_seconds": profile.max_speech_seconds,
        "min_silence_ms": profile.min_silence_ms,
        "speech_pad_ms": profile.speech_pad_ms,
        "pre_roll_ms": profile.pre_roll_ms,
        "vad_threshold": profile.vad_threshold,
        "description": profile.description,
    }
