from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from .profiles import AudioProfile, get_audio_profile


VALID_AUDIO_MODES = ("cpu", "gpu", "hybrid")


def normalize_audio_mode(value: str | None) -> str:
    token = str(value or "hybrid").strip().lower()
    return token if token in VALID_AUDIO_MODES else "hybrid"


@dataclass(frozen=True)
class ASRWorkerSpec:
    role: str
    model_size: str
    device: str
    compute_type: str
    cpu_threads: int
    beam_size: int
    best_of: int
    retry_beam_size: int
    minimum_free_vram_mb: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AudioExecutionPlan:
    requested_mode: str
    profile_key: str
    primary: ASRWorkerSpec
    fallback: Optional[ASRWorkerSpec]
    translator_device: str = "cpu"
    translator_compute_type: str = "int8"

    @property
    def required_model_sizes(self) -> tuple[str, ...]:
        values = [self.primary.model_size]
        if self.fallback is not None and self.fallback.model_size not in values:
            values.append(self.fallback.model_size)
        return tuple(values)

    def as_dict(self) -> dict:
        return {
            "requested_mode": self.requested_mode,
            "profile_key": self.profile_key,
            "primary": self.primary.as_dict(),
            "fallback": self.fallback.as_dict() if self.fallback else None,
            "translator_device": self.translator_device,
            "translator_compute_type": self.translator_compute_type,
            "required_model_sizes": list(self.required_model_sizes),
        }


def _cpu_spec(profile: AudioProfile, model_size: str, role: str) -> ASRWorkerSpec:
    return ASRWorkerSpec(
        role=role,
        model_size=model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=profile.cpu_threads,
        beam_size=profile.beam_size,
        best_of=profile.best_of,
        retry_beam_size=profile.retry_beam_size,
    )


def _gpu_spec(profile: AudioProfile, role: str = "primary") -> ASRWorkerSpec:
    reserve = 2600 if profile.gpu_model_size == "medium" else 1400
    return ASRWorkerSpec(
        role=role,
        model_size=profile.gpu_model_size,
        device="cuda",
        compute_type="int8_float16",
        cpu_threads=max(2, min(4, profile.cpu_threads)),
        beam_size=profile.beam_size,
        best_of=profile.best_of,
        retry_beam_size=profile.retry_beam_size,
        minimum_free_vram_mb=reserve,
    )


def resolve_audio_plan(mode: str | None, profile_key: str | None) -> AudioExecutionPlan:
    requested = normalize_audio_mode(mode)
    profile = get_audio_profile(profile_key)
    if requested == "cpu":
        return AudioExecutionPlan(
            requested_mode=requested,
            profile_key=profile.key,
            primary=_cpu_spec(profile, profile.model_size, "primary"),
            fallback=None,
        )
    if requested == "gpu":
        return AudioExecutionPlan(
            requested_mode=requested,
            profile_key=profile.key,
            primary=_gpu_spec(profile),
            fallback=None,
        )
    return AudioExecutionPlan(
        requested_mode=requested,
        profile_key=profile.key,
        primary=_gpu_spec(profile),
        fallback=_cpu_spec(profile, profile.hybrid_fallback_model_size, "fallback"),
    )


@dataclass
class HybridFailoverController:
    requested_mode: str
    effective_mode: str
    gpu_failures: int = 0
    circuit_open: bool = False

    @classmethod
    def create(cls, requested_mode: str, effective_mode: str | None = None) -> "HybridFailoverController":
        requested = normalize_audio_mode(requested_mode)
        effective = str(effective_mode or requested).strip().lower()
        return cls(requested_mode=requested, effective_mode=effective)

    def worker_failure(self, worker_device: str, reason: str) -> dict:
        device = str(worker_device or "").strip().lower()
        failure_reason = str(reason or "ASR_WORKER_EXIT")
        if self.requested_mode == "hybrid" and device == "cuda":
            self.gpu_failures += 1
            self.circuit_open = self.gpu_failures >= 2
            self.effective_mode = "cpu_fallback" if self.circuit_open else "cpu_recovery"
            return {
                "action": "fallback_cpu",
                "replay_inflight": True,
                "retry_gpu_after_replay": not self.circuit_open,
                "effective_mode": self.effective_mode,
                "reason": failure_reason,
                "gpu_failures": self.gpu_failures,
                "circuit_open": self.circuit_open,
            }
        return {
            "action": "stop",
            "replay_inflight": False,
            "effective_mode": self.effective_mode,
            "reason": failure_reason,
            "gpu_failures": self.gpu_failures,
            "circuit_open": self.circuit_open,
        }
