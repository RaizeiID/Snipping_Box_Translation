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
    "speed": AudioProfile(
        key="speed",
        label="Speed",
        model_size="base",
        gpu_model_size="small",
        hybrid_fallback_model_size="base",
        cpu_threads=3,
        beam_size=2,
        best_of=2,
        retry_beam_size=4,
        normal_chunk_seconds=2.8,
        min_speech_seconds=0.45,
        max_speech_seconds=4.6,
        min_silence_ms=360,
        speech_pad_ms=220,
        pre_roll_ms=320,
        vad_threshold=0.0075,
        description="Respons tercepat tanpa model tiny; memakai base pada CPU dan small pada GPU.",
    ),
    "normal": AudioProfile(
        key="normal",
        label="Normal",
        model_size="small",
        gpu_model_size="small",
        hybrid_fallback_model_size="base",
        cpu_threads=4,
        beam_size=3,
        best_of=3,
        retry_beam_size=5,
        normal_chunk_seconds=3.8,
        min_speech_seconds=0.55,
        max_speech_seconds=8.0,
        min_silence_ms=520,
        speech_pad_ms=260,
        pre_roll_ms=380,
        vad_threshold=0.0060,
        description="Keseimbangan kualitas dialog Jepang, latensi, dan penggunaan sumber daya.",
    ),
    "accurate": AudioProfile(
        key="accurate",
        label="Accurate",
        model_size="small",
        gpu_model_size="medium",
        hybrid_fallback_model_size="small",
        cpu_threads=6,
        beam_size=5,
        best_of=5,
        retry_beam_size=7,
        normal_chunk_seconds=4.8,
        min_speech_seconds=0.70,
        max_speech_seconds=10.0,
        min_silence_ms=680,
        speech_pad_ms=300,
        pre_roll_ms=440,
        vad_threshold=0.0050,
        description="Pencarian terlebar; medium pada GPU dan small pada CPU dengan kebutuhan memori lebih besar.",
    ),
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
