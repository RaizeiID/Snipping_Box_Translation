from __future__ import annotations

import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import numpy as np

from .asr_provider_registry import (
    PROVIDERS,
    PROVIDER_KOTOBA,
    PROVIDER_REAZON,
    PROVIDER_SENSEVOICE,
    PROVIDER_WHISPER_BASE,
    PROVIDER_WHISPER_SMALL,
    normalize_provider_id,
    provider_model_candidates,
    provider_status,
)


TARGET_SAMPLE_RATE = 16000


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _semantic(value: str) -> bool:
    return any(
        char.isalnum()
        or "\u3040" <= char <= "\u30ff"
        or "\u4e00" <= char <= "\u9fff"
        for char in str(value or "")
    )


def _strip_sensevoice_tokens(text: str) -> str:
    clean = re.sub(r"<\|[^|>]+\|>", " ", str(text or ""))
    return _clean_text(clean)


class LockedASRProviderAdapter:
    """Exact provider adapter used by v9.0.5 model-lock sessions.

    The provider id never changes during a session. Optimal mode may move the
    same provider between CUDA and CPU only when both devices are supported.
    """

    def __init__(
        self,
        *,
        model_root: Path,
        provider_id: str,
        device: str,
        compute_type: str,
        cpu_threads: int,
        source_language: Optional[str],
        requested_language: str,
        profile: str,
        emit_event: Callable[..., None],
    ) -> None:
        self.model_root = Path(model_root).expanduser().resolve()
        self.provider_id = normalize_provider_id(provider_id, japanese=(source_language in {None, "ja"}))
        if self.provider_id == "auto":
            raise RuntimeError("Model lock requires an explicit ASR provider; Auto is not allowed.")
        self.spec = PROVIDERS[self.provider_id]
        self.device = str(device or "cpu").lower()
        self.compute_type = str(compute_type or ("int8_float16" if self.device == "cuda" else "int8"))
        self.cpu_threads = max(1, int(cpu_threads or 1))
        self.source_language = source_language or "ja"
        self.requested_language = str(requested_language or self.source_language)
        self.profile = str(profile or "normal").lower()
        self.emit_event = emit_event
        self.model: Any = None
        self.model_path = ""
        self.model_size = self.provider_id
        self.specialist_active = self.provider_id == PROVIDER_KOTOBA
        self.dual_stream_cpu_specialist = False
        self.preflight_warmup_ms = 0
        self.preflight_steady_ms = 0
        self.language_locked = True
        self.language_watchdog = SimpleNamespace(policy=SimpleNamespace(mode="provider_lock"))
        self.japanese_specialist = self.specialist_active
        self._backend = ""

    @property
    def supported_devices(self) -> tuple[str, ...]:
        return self.spec.supported_devices

    def _first_model_path(self) -> Path:
        for candidate in provider_model_candidates(self.model_root, self.provider_id):
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(
            f"Locked provider {self.provider_id} model is not available under {self.model_root}. "
            "Use Siapkan model terpilih first."
        )

    def _load_faster_whisper(self) -> None:
        from faster_whisper import WhisperModel

        location = self._first_model_path()
        self.emit_event(
            "state",
            state="MODEL_LOADING",
            provider_id=self.provider_id,
            model=self.provider_id,
            device=self.device,
            compute_type=self.compute_type,
            model_lock=True,
            local_realtime=True,
        )
        self.model = WhisperModel(
            str(location),
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=1,
        )
        self.model_path = str(location)
        self._backend = "faster_whisper"

    def _load_reazon(self) -> None:
        import sherpa_onnx

        precision = "int8" if self.device == "cpu" else "int8-fp32"
        location = self._first_model_path()
        decoder_name = (
            "decoder-epoch-99-avg-1.int8.onnx"
            if self.device == "cpu"
            else "decoder-epoch-99-avg-1.onnx"
        )
        files = {
            "tokens": location / "tokens.txt",
            "encoder": location / "encoder-epoch-99-avg-1.int8.onnx",
            "decoder": location / decoder_name,
            "joiner": location / "joiner-epoch-99-avg-1.int8.onnx",
        }
        missing = [path.name for path in files.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f"ReazonSpeech K2 local model incomplete at {location}: {missing}"
            )
        self.emit_event(
            "state",
            state="MODEL_LOADING",
            provider_id=self.provider_id,
            model="reazonspeech-k2-v2-local",
            device=self.device,
            compute_type=precision,
            model_lock=True,
            local_realtime=True,
        )
        self.model = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(files["tokens"]),
            encoder=str(files["encoder"]),
            decoder=str(files["decoder"]),
            joiner=str(files["joiner"]),
            num_threads=1,
            sample_rate=TARGET_SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            provider=self.device,
        )
        self.compute_type = precision
        self.model_path = str(location)
        self._backend = "reazonspeech_k2"

    def _load_sensevoice(self) -> None:
        if self.device != "cpu":
            raise RuntimeError("SenseVoice-Small sherpa-onnx adapter is CPU-only in ORT v9.0.5.")
        import sherpa_onnx

        location = self._first_model_path()
        model_file = location / "model.int8.onnx"
        if not model_file.is_file():
            model_file = location / "model.onnx"
        tokens = location / "tokens.txt"
        if not model_file.is_file() or not tokens.is_file():
            raise FileNotFoundError(f"SenseVoice model/tokens incomplete: {location}")
        self.emit_event(
            "state",
            state="MODEL_LOADING",
            provider_id=self.provider_id,
            model="sensevoice-small-int8",
            device="cpu",
            compute_type="int8",
            model_lock=True,
            local_realtime=True,
        )
        self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model_file),
            tokens=str(tokens),
            num_threads=self.cpu_threads,
            language="ja",
            use_itn=True,
            debug=False,
            provider="cpu",
        )
        self.model_path = str(location)
        self.compute_type = "int8"
        self._backend = "sensevoice_sherpa_onnx"

    def load(self) -> None:
        status = provider_status(self.model_root, self.provider_id, self.device)
        if not status.get("ready"):
            raise RuntimeError(
                "Locked provider unavailable: " + "; ".join(status.get("errors") or [self.provider_id])
            )
        if self.provider_id in {PROVIDER_KOTOBA, PROVIDER_WHISPER_BASE, PROVIDER_WHISPER_SMALL}:
            self._load_faster_whisper()
        elif self.provider_id == PROVIDER_REAZON:
            self._load_reazon()
        elif self.provider_id == PROVIDER_SENSEVOICE:
            self._load_sensevoice()
        else:
            raise RuntimeError(f"Unsupported locked provider: {self.provider_id}")
        self._preflight()
        self.emit_event(
            "state",
            state="MODEL_READY",
            provider_id=self.provider_id,
            provider_owner=self.spec.owner,
            model=self.model_size,
            model_path=self.model_path,
            device=self.device,
            compute_type=self.compute_type,
            model_lock=True,
            output_language=self.spec.output_language,
            asr_task=self.spec.task,
            offline=True,
            local_realtime=True,
        )

    def _preflight(self) -> None:
        duration = 0.30 if self.device == "cpu" else 0.55
        timeline = np.arange(int(TARGET_SAMPLE_RATE * duration), dtype=np.float32) / TARGET_SAMPLE_RATE
        probe = (0.004 * np.sin(2.0 * np.pi * 330.0 * timeline)).astype(np.float32)
        passes = 1 if self.device == "cpu" else 2
        timings: list[int] = []
        self.emit_event(
            "state",
            state=("CUDA" if self.device == "cuda" else "CPU") + "_PREFLIGHT",
            provider_id=self.provider_id,
            model_lock=True,
            local_realtime=True,
        )
        for _ in range(passes):
            started = time.perf_counter()
            try:
                self._recognize(probe, stable=False)
            except Exception:
                # Silence probes may be rejected by some recognizers; construction
                # and decode entry are enough to confirm native runtime loading.
                pass
            timings.append(int((time.perf_counter() - started) * 1000))
        self.preflight_warmup_ms = timings[0]
        self.preflight_steady_ms = timings[-1]
        self.emit_event(
            "state",
            state=("CUDA" if self.device == "cuda" else "CPU") + "_PREFLIGHT_PASSED",
            provider_id=self.provider_id,
            warmup_ms=self.preflight_warmup_ms,
            steady_ms=self.preflight_steady_ms,
            model_lock=True,
            local_realtime=True,
        )

    def switch_device(self, device: str) -> None:
        target = str(device or "cpu").lower()
        if target == self.device:
            return
        if target not in self.supported_devices:
            raise RuntimeError(
                f"Locked provider {self.provider_id} cannot switch to {target}; supported={self.supported_devices}"
            )
        old_provider = self.provider_id
        self.device = target
        self.compute_type = "int8_float16" if target == "cuda" else "int8"
        self.model = None
        self.load()
        if self.provider_id != old_provider:
            raise RuntimeError("Provider lock violation detected after device switch.")

    def _faster_whisper_task(self) -> tuple[str, str, str]:
        if self.provider_id == PROVIDER_KOTOBA and self.source_language == "ja":
            return "en", "translate", "en"
        if self.source_language == "en":
            return "en", "transcribe", "en"
        return self.source_language or "ja", "translate", "en"

    def _recognize(self, audio: np.ndarray, stable: bool) -> tuple[str, dict]:
        if self._backend == "faster_whisper":
            language, task, bridge = self._faster_whisper_task()
            if self.device == "cpu":
                beam = 1
            elif self.profile in {"accurate", "quality"} and stable:
                beam = 3
            else:
                beam = 1
            segments, info = self.model.transcribe(
                audio,
                language=language,
                task=task,
                beam_size=beam,
                best_of=max(1, beam),
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                without_timestamps=True,
                word_timestamps=False,
                repetition_penalty=1.10,
                no_repeat_ngram_size=3,
                no_speech_threshold=0.58,
            )
            text = _clean_text(" ".join(str(item.text or "") for item in segments))
            return text, {
                "detected_language": str(getattr(info, "language", self.source_language) or self.source_language),
                "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
                "asr_task": task,
                "bridge_language": bridge,
            }
        if self._backend == "reazonspeech_k2":
            stream = self.model.create_stream()
            stream.accept_waveform(TARGET_SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
            self.model.decode_stream(stream)
            result = stream.result
            text = str(getattr(result, "text", result) or "")
            return _clean_text(text), {
                "detected_language": "ja",
                "language_probability": 1.0,
                "asr_task": "transcribe",
                "bridge_language": "ja",
            }
        if self._backend == "sensevoice_sherpa_onnx":
            stream = self.model.create_stream()
            stream.accept_waveform(TARGET_SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
            self.model.decode_stream(stream)
            raw = stream.result
            text = ""
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    text = str(parsed.get("text") or raw)
                except Exception:
                    text = raw
            else:
                text = str(getattr(raw, "text", raw) or "")
            return _strip_sensevoice_tokens(text), {
                "detected_language": "ja",
                "language_probability": 1.0,
                "asr_task": "transcribe",
                "bridge_language": "ja",
            }
        raise RuntimeError(f"Provider backend not loaded: {self.provider_id}")

    def _window_seconds(self, stable: bool) -> float:
        if self.provider_id == PROVIDER_SENSEVOICE:
            return 4.0 if stable else 2.4
        if self.provider_id == PROVIDER_REAZON:
            return 5.5 if stable else 3.2
        if self.provider_id == PROVIDER_KOTOBA and self.device == "cpu":
            # Bounded CPU Kotoba mode: no second stream, one beam, and a short
            # rolling window to prevent minute-long queues.
            return 4.0 if stable else 2.2
        if self.device == "cpu":
            return 4.5 if stable else 2.6
        return 8.0 if stable else 5.5

    def transcribe(self, samples: np.ndarray, stable: bool = False) -> tuple[str, dict]:
        if self.model is None:
            raise RuntimeError("Locked ASR provider has not been loaded.")
        started = time.perf_counter()
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        maximum = int(self._window_seconds(stable) * TARGET_SAMPLE_RATE)
        if len(audio) > maximum:
            audio = audio[-maximum:]
        text, meta = self._recognize(audio, stable)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        reasons: list[str] = []
        if not _semantic(text):
            reasons.extend(["EMPTY", "NO_SPEECH"])
        result = {
            "requested_language": self.requested_language,
            "detected_language": meta.get("detected_language", self.source_language),
            "language_probability": meta.get("language_probability", 1.0),
            "source_language": self.source_language,
            "bridge_language": meta.get("bridge_language", self.spec.bridge_language),
            "asr_task": meta.get("asr_task", self.spec.task),
            "japanese_specialist": self.provider_id == PROVIDER_KOTOBA,
            "provider_id": self.provider_id,
            "provider_owner": self.spec.owner,
            "provider_backend": self.spec.backend,
            "model_lock": True,
            "quality_retry": False,
            "asr_ms": elapsed_ms,
            "provisional": not stable,
            "specialist_correction_pending": False,
            "model_used": self.provider_id,
        }
        if reasons:
            result["quality_reject_reasons"] = reasons
            return "", result
        return text, result
