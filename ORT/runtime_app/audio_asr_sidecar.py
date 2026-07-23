from __future__ import annotations

import argparse
import faulthandler
import importlib.metadata
import importlib.util
import json
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from app.audio.profiles import AudioProfile, get_audio_profile, profile_payload
from app.audio.model_store import canonical_model_dir, inspect_local_model, inspect_model_dir, model_problem_text
from app.audio.glossary import apply_audio_glossary
from app.audio.quality_gate import aggregate_segment_metrics, assess_asr_quality
from app.audio.streaming import LiveAudioSegmenter, TranscriptDeduplicator, audio_rms, pcm16_to_mono_float, resample_linear


EVENT_PREFIX = "ORT_AUDIO_EVENT "
TARGET_SAMPLE_RATE = 16000
STOP_EVENT = threading.Event()
MODEL_REPOSITORIES = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
}
MODEL_ALLOW_PATTERNS = (
    "config.json",
    "model.bin",
    "preprocessor_config.json",
    "tokenizer.json",
    "vocabulary.*",
)


def emit_event(event_type: str, **payload: Any) -> None:
    event = {"type": str(event_type), "ts": time.time(), **payload}
    print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def _signal_stop(*_args: Any) -> None:
    STOP_EVENT.set()


def _install_signal_handlers() -> None:
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _signal_stop)
            except Exception:
                pass


def _language_value(value: str | None) -> Optional[str]:
    token = str(value or "auto").strip().lower()
    return None if token in {"", "auto", "auto_detect"} else token


def _configure_hub_downloads() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")


def _configure_cuda_dll_paths() -> list[str]:
    if os.name != "nt":
        return []
    candidates: list[Path] = []
    explicit = str(os.environ.get("ORT_AUDIO_CUDA_PATH", "") or "").strip()
    if explicit:
        candidates.append(Path(explicit))
    for key, value in os.environ.items():
        if key == "CUDA_PATH" or key.startswith("CUDA_PATH_V12"):
            if value:
                candidates.append(Path(value) / "bin")
    try:
        import nvidia.cublas.lib
        candidates.append(Path(nvidia.cublas.lib.__file__).resolve().parent)
    except Exception:
        pass
    try:
        import nvidia.cudnn.lib
        candidates.append(Path(nvidia.cudnn.lib.__file__).resolve().parent)
    except Exception:
        pass
    activated: list[str] = []
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
            if not resolved.is_dir() or str(resolved) in activated:
                continue
            os.add_dll_directory(str(resolved))
            os.environ["PATH"] = str(resolved) + os.pathsep + os.environ.get("PATH", "")
            activated.append(str(resolved))
        except Exception:
            continue
    return activated


def _cached_model_revision(model_root: Path, repository: str) -> Optional[str]:
    ref_path = model_root / ("models--" + repository.replace("/", "--")) / "refs" / "main"
    try:
        revision = ref_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if len(revision) == 40 and all(character in "0123456789abcdefABCDEF" for character in revision):
        return revision
    return None


def _download_whisper_once(model_size: str, model_root: Path, target: Path, attempt: int) -> Path:
    if attempt <= 1:
        from faster_whisper.utils import download_model

        return Path(download_model(
            model_size,
            output_dir=str(target),
            cache_dir=str(model_root),
        )).expanduser().resolve()

    from huggingface_hub import snapshot_download

    repository = MODEL_REPOSITORIES.get(model_size)
    if not repository:
        raise RuntimeError(f"Repository model tidak dikenal: {model_size}")
    revision = _cached_model_revision(model_root, repository)
    return Path(snapshot_download(
        repository,
        revision=revision or "main",
        local_dir=str(target),
        cache_dir=str(model_root),
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
        max_workers=1,
    )).expanduser().resolve()


def _prepare_whisper(profile: AudioProfile, model_root: Path, retry_count: int = 3, model_size: str | None = None) -> Path:
    _configure_hub_downloads()

    selected_model = str(model_size or profile.model_size).strip().lower()
    model_root.mkdir(parents=True, exist_ok=True)
    target = canonical_model_dir(model_root, selected_model)
    inspection = inspect_model_dir(target, selected_model)
    if inspection.ready:
        emit_event(
            "state",
            state="MODEL_DOWNLOAD_READY",
            model=selected_model,
            model_path=str(target),
            cached=True,
            optional_missing_files=list(inspection.optional_missing_files),
            optional_invalid_files=list(inspection.optional_invalid_files),
        )
        return target

    attempts = max(1, min(5, int(retry_count or 3)))
    last_error = ""
    for attempt in range(1, attempts + 1):
        emit_event(
            "state",
            state="MODEL_DOWNLOADING",
            model=selected_model,
            attempt=attempt,
            attempts=attempts,
            model_path=str(target),
            missing_files=list(inspection.missing_files),
            invalid_files=list(inspection.invalid_files),
        )
        try:
            resolved = _download_whisper_once(selected_model, model_root, target, attempt)
            inspection = inspect_model_dir(resolved, selected_model)
            if not inspection.ready:
                raise RuntimeError("Snapshot selesai dipanggil tetapi belum lengkap (" + model_problem_text(inspection) + ").")
            emit_event(
                "state",
                state="MODEL_DOWNLOAD_READY",
                model=selected_model,
                model_path=str(resolved),
                cached=False,
                attempt=attempt,
                optional_missing_files=list(inspection.optional_missing_files),
                optional_invalid_files=list(inspection.optional_invalid_files),
            )
            return resolved
        except Exception as exc:
            last_error = str(exc)
            inspection = inspect_model_dir(target, selected_model)
            emit_event(
                "warning",
                stage="model_download",
                code="MODEL_DOWNLOAD_RETRY" if attempt < attempts else "MODEL_DOWNLOAD_INCOMPLETE",
                model=selected_model,
                attempt=attempt,
                attempts=attempts,
                missing_files=list(inspection.missing_files),
                invalid_files=list(inspection.invalid_files),
                message=last_error,
            )
            if attempt < attempts:
                time.sleep(min(8.0, 1.5 * (2 ** (attempt - 1))))

    problem = model_problem_text(inspection)
    raise RuntimeError(
        f"Model {selected_model} belum lengkap setelah {attempts} percobaan ({problem}). "
        "Unduhan yang sudah masuk tetap disimpan dan akan dilanjutkan saat setup Audio ditekan lagi. "
        f"Kesalahan terakhir: {last_error}"
    )


def _load_whisper(
    profile: AudioProfile,
    model_root: Path,
    model_size: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
):
    selected_model = str(model_size or profile.model_size).strip().lower()
    selected_device = "cuda" if str(device).strip().lower() == "cuda" else "cpu"
    selected_compute = str(compute_type or ("int8_float16" if selected_device == "cuda" else "int8"))
    os.environ.setdefault("OMP_NUM_THREADS", str(profile.cpu_threads))
    if selected_device == "cuda":
        _configure_cuda_dll_paths()
    else:
        os.environ.setdefault("CT2_USE_EXPERIMENTAL_PACKED_GEMM", "1")
    from faster_whisper import WhisperModel

    inspection = inspect_local_model(model_root, selected_model)
    if not inspection.ready:
        raise RuntimeError(
            f"Model lokal {selected_model} belum lengkap ({model_problem_text(inspection)}). "
            "Jalankan setup Audio untuk melanjutkan unduhan sebelum memulai Audio."
        )

    emit_event(
        "state",
        state="MODEL_LOADING",
        model=selected_model,
        device=selected_device,
        compute_type=selected_compute,
        cpu_threads=profile.cpu_threads,
    )
    kwargs = {
        "device": selected_device,
        "compute_type": selected_compute,
        "num_workers": 1,
        "local_files_only": True,
    }
    if selected_device == "cpu":
        kwargs["cpu_threads"] = profile.cpu_threads
    model = WhisperModel(inspection.path, **kwargs)
    emit_event(
        "state",
        state="MODEL_READY",
        model=selected_model,
        model_path=inspection.path,
        device=selected_device,
        compute_type=selected_compute,
        offline=True,
    )
    return model


def _nvidia_memory() -> dict:
    try:
        result = __import__("subprocess").run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free,name", "--format=csv,noheader,nounits"],
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8.0,
            check=False,
        )
        line = next((item.strip() for item in result.stdout.splitlines() if item.strip()), "")
        parts = [item.strip() for item in line.split(",", 2)]
        if result.returncode == 0 and len(parts) >= 2:
            return {
                "vram_total_mb": int(float(parts[0])),
                "vram_free_mb": int(float(parts[1])),
                "gpu_name": parts[2] if len(parts) > 2 else "NVIDIA GPU",
            }
    except Exception:
        pass
    return {}


def dependency_probe(asr_device: str = "cpu") -> Dict[str, Any]:
    requested_device = "cuda" if str(asr_device).strip().lower() == "cuda" else "cpu"
    result: Dict[str, Any] = {
        "python": sys.executable,
        "platform": sys.platform,
        "faster_whisper": False,
        "numpy": True,
        "pyaudiowpatch": False,
        "live_loopback": False,
        "file_test": False,
        "requested_device": requested_device,
        "cuda_ready": False,
        "cuda_device_count": 0,
        "cuda_compute_types": [],
    }
    errors = []
    if importlib.util.find_spec("faster_whisper") is not None:
        result["faster_whisper"] = True
        try:
            result["faster_whisper_version"] = importlib.metadata.version("faster-whisper")
        except Exception:
            result["faster_whisper_version"] = "unknown"
        result["file_test"] = True
    else:
        errors.append("faster-whisper: module not found")
    if importlib.util.find_spec("pyaudiowpatch") is not None:
        result["pyaudiowpatch"] = True
        try:
            result["pyaudiowpatch_version"] = importlib.metadata.version("PyAudioWPatch")
        except Exception:
            result["pyaudiowpatch_version"] = "unknown"
        result["live_loopback"] = sys.platform == "win32"
    else:
        errors.append("PyAudioWPatch: module not found")
    if requested_device == "cuda" and result["faster_whisper"]:
        try:
            dll_paths = _configure_cuda_dll_paths()
            import ctranslate2

            device_count = int(ctranslate2.get_cuda_device_count())
            compute_types = sorted(str(item) for item in ctranslate2.get_supported_compute_types("cuda")) if device_count > 0 else []
            result["cuda_device_count"] = device_count
            result["cuda_compute_types"] = compute_types
            result["cuda_dll_paths"] = dll_paths
            result["cuda_ready"] = device_count > 0 and "int8_float16" in compute_types
            result.update(_nvidia_memory())
            if not result["cuda_ready"]:
                errors.append("CUDA ASR tidak mendukung int8_float16 atau perangkat CUDA tidak ditemukan")
        except Exception as exc:
            errors.append(f"CUDA probe: {type(exc).__name__}: {exc}")
    base_ready = bool(result["faster_whisper"] and (result["pyaudiowpatch"] if sys.platform == "win32" else True))
    result["ready"] = base_ready and (result["cuda_ready"] if requested_device == "cuda" else True)
    result["errors"] = errors
    return result


def list_loopback_devices() -> list[Dict[str, Any]]:
    if sys.platform != "win32":
        return []
    import pyaudiowpatch as pyaudio

    devices: list[Dict[str, Any]] = []
    with pyaudio.PyAudio() as manager:
        for item in manager.get_loopback_device_info_generator():
            devices.append({
                "index": int(item.get("index", -1)),
                "name": str(item.get("name", "WASAPI Loopback")),
                "channels": max(1, int(item.get("maxInputChannels", 1))),
                "sample_rate": int(float(item.get("defaultSampleRate", 48000))),
                "is_default": False,
            })
        try:
            default_device = manager.get_default_wasapi_loopback()
            default_index = int(default_device.get("index", -1))
            for item in devices:
                item["is_default"] = item["index"] == default_index
        except Exception:
            pass
    return devices


def _resolve_loopback_device(manager: Any, requested_index: int) -> Dict[str, Any]:
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
    try:
        wasapi = manager.get_host_api_info_by_type(__import__("pyaudiowpatch").paWASAPI)
        output = manager.get_device_info_by_index(wasapi["defaultOutputDevice"])
        output_name = str(output.get("name", ""))
        for item in loopbacks:
            if output_name and output_name in str(item.get("name", "")):
                return item
    except Exception:
        pass
    if loopbacks:
        return loopbacks[0]
    raise RuntimeError("WASAPI loopback tidak ditemukan. Pastikan perangkat output aktif dan driver audio Windows tersedia.")


def _transcribe_once(
    model: Any,
    source: Any,
    profile: AudioProfile,
    processing: str,
    language: Optional[str],
    beam_size: int,
) -> tuple[list[Any], Any]:
    vad_enabled = str(processing or "vad").lower() == "vad"
    segments, info = model.transcribe(
        source,
        language=language,
        task="translate",
        beam_size=max(1, int(beam_size)),
        best_of=max(1, int(profile.best_of)),
        temperature=0.0,
        condition_on_previous_text=False,
        without_timestamps=True,
        repetition_penalty=1.08,
        no_repeat_ngram_size=3,
        vad_filter=vad_enabled,
        vad_parameters={
            "min_silence_duration_ms": profile.min_silence_ms,
            "speech_pad_ms": profile.speech_pad_ms,
        } if vad_enabled else None,
    )
    return list(segments), info


def _inference_payload(
    model: Any,
    source: Any,
    *,
    profile: AudioProfile,
    processing: str,
    language: Optional[str],
    audio_seconds: float,
    model_size: str,
    device: str,
    compute_type: str,
    allow_retry: bool = True,
) -> dict:
    started = time.perf_counter()
    rows, info = _transcribe_once(model, source, profile, processing, language, profile.beam_size)
    text = " ".join(str(row.text or "").strip() for row in rows).strip()
    measured_seconds = float(audio_seconds or 0.0)
    if measured_seconds <= 0.0 and rows:
        measured_seconds = max(float(getattr(row, "end", 0.0) or 0.0) for row in rows)
    avg_logprob, no_speech_prob, compression_ratio = aggregate_segment_metrics(rows)
    detected_language = str(getattr(info, "language", "") or "")
    language_probability = float(getattr(info, "language_probability", 0.0) or 0.0)
    decision = assess_asr_quality(
        text,
        audio_seconds=measured_seconds,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
        language_probability=language_probability,
        detected_language=detected_language,
        expected_language=language or "",
    )
    retried = False
    if allow_retry and decision.retry_recommended:
        retried = True
        retry_rows, retry_info = _transcribe_once(model, source, profile, processing, language, profile.retry_beam_size)
        retry_text = " ".join(str(row.text or "").strip() for row in retry_rows).strip()
        retry_avg, retry_no_speech, retry_compression = aggregate_segment_metrics(retry_rows)
        retry_detected = str(getattr(retry_info, "language", "") or "")
        retry_language_probability = float(getattr(retry_info, "language_probability", 0.0) or 0.0)
        retry_decision = assess_asr_quality(
            retry_text,
            audio_seconds=measured_seconds,
            avg_logprob=retry_avg,
            no_speech_prob=retry_no_speech,
            compression_ratio=retry_compression,
            language_probability=retry_language_probability,
            detected_language=retry_detected,
            expected_language=language or "",
        )
        if retry_decision.accepted or (not decision.accepted and len(retry_decision.reasons) < len(decision.reasons)):
            rows = retry_rows
            info = retry_info
            text = retry_text
            detected_language = retry_detected
            language_probability = retry_language_probability
            decision = retry_decision
    game = str(os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")) or "CUSTOM")
    corrected, glossary_hits = apply_audio_glossary(text, game)
    return {
        "text": corrected,
        "raw_text": text,
        "detected_language": detected_language,
        "language_probability": language_probability,
        "asr_ms": int((time.perf_counter() - started) * 1000),
        "audio_seconds": round(measured_seconds, 3),
        "model": model_size,
        "profile": profile.key,
        "asr_device": device,
        "asr_compute_type": compute_type,
        "quality": decision.as_dict(),
        "quality_retry": retried,
        "glossary_hits": glossary_hits,
    }


def _classify_runtime_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".casefold()
    if "out of memory" in text or "cuda_error_out_of_memory" in text:
        return "CUDA_OUT_OF_MEMORY"
    if "cublas" in text:
        return "CUBLAS_ERROR"
    if "cudnn" in text:
        return "CUDNN_ERROR"
    if "cuda" in text:
        return "CUDA_RUNTIME_ERROR"
    return "ASR_INFERENCE_ERROR"


def _load_request_source(request: dict) -> tuple[Any, float]:
    path = Path(str(request.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Segmen audio tidak ditemukan: {path}")
    kind = str(request.get("kind") or "npy").strip().lower()
    if kind == "npy":
        audio = np.load(path, allow_pickle=False)
        signal_data = np.asarray(audio, dtype=np.float32).reshape(-1)
        return signal_data, float(request.get("audio_seconds", 0.0) or (signal_data.size / TARGET_SAMPLE_RATE))
    return str(path), float(request.get("audio_seconds", 0.0) or 0.0)


def run_worker(
    model: Any,
    *,
    profile: AudioProfile,
    processing: str,
    language: Optional[str],
    model_size: str,
    device: str,
    compute_type: str,
) -> int:
    for raw in sys.stdin:
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except Exception as exc:
            emit_event("error", stage="protocol", code="INVALID_JSON", message=str(exc))
            continue
        request_type = str(request.get("type") or "").strip().lower()
        if request_type == "shutdown":
            return 0
        if request_type != "transcribe":
            emit_event("error", stage="protocol", code="UNSUPPORTED_REQUEST", message=request_type or "-")
            continue
        segment_id = str(request.get("segment_id") or "")
        try:
            source, audio_seconds = _load_request_source(request)
            emit_event("state", state="TRANSCRIBING", segment_id=segment_id, seconds=round(audio_seconds, 3), device=device)
            payload = _inference_payload(
                model,
                source,
                profile=profile,
                processing=processing,
                language=language,
                audio_seconds=audio_seconds,
                model_size=model_size,
                device=device,
                compute_type=compute_type,
            )
            if payload["quality"]["accepted"] and payload.get("text"):
                emit_event("transcript", segment_id=segment_id, **payload)
            else:
                emit_event(
                    "quality_reject",
                    segment_id=segment_id,
                    reasons=payload["quality"]["reasons"],
                    metrics=payload["quality"]["metrics"],
                    raw_text=payload.get("raw_text", ""),
                    asr_ms=payload.get("asr_ms", 0),
                    quality_retry=bool(payload.get("quality_retry")),
                    model=model_size,
                    asr_device=device,
                )
            emit_event("segment_complete", segment_id=segment_id, status="accepted" if payload["quality"]["accepted"] else "rejected")
        except Exception as exc:
            code = _classify_runtime_error(exc)
            emit_event("error", stage="asr", code=code, segment_id=segment_id, message=str(exc), fatal=True)
            return 70 if device == "cuda" else 71
    return 0


class ASRInferenceWorker:
    def __init__(self, model: Any, profile: AudioProfile, processing: str, language: Optional[str]):
        self.model = model
        self.profile = profile
        self.processing = processing
        self.language = language
        self.queue: queue.Queue[Optional[np.ndarray]] = queue.Queue(maxsize=2)
        self.thread = threading.Thread(target=self._run, name="ort-audio-asr", daemon=True)
        self.deduplicator = TranscriptDeduplicator()
        self.dropped_segments = 0

    def start(self) -> None:
        self.thread.start()

    def submit(self, audio: np.ndarray) -> None:
        item = np.asarray(audio, dtype=np.float32).reshape(-1)
        if item.size < int(TARGET_SAMPLE_RATE * 0.25):
            return
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                self.dropped_segments += 1
                emit_event("metric", name="asr_queue_drop", count=self.dropped_segments)
            except queue.Empty:
                pass
        self.queue.put_nowait(item)

    def stop(self) -> None:
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(None)
            except queue.Full:
                pass
        self.thread.join(timeout=3.0)

    def _run(self) -> None:
        while not STOP_EVENT.is_set():
            try:
                audio = self.queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if audio is None:
                self.queue.task_done()
                return
            try:
                self._transcribe(audio)
            except Exception as exc:
                emit_event("error", stage="asr", message=str(exc))
            finally:
                self.queue.task_done()

    def _transcribe(self, audio: np.ndarray) -> None:
        started = time.perf_counter()
        emit_event("state", state="TRANSCRIBING", seconds=round(audio.size / TARGET_SAMPLE_RATE, 3))
        vad_enabled = self.processing == "vad"
        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            task="translate",
            beam_size=self.profile.beam_size,
            best_of=self.profile.best_of,
            temperature=0.0,
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=vad_enabled,
            vad_parameters={
                "min_silence_duration_ms": self.profile.min_silence_ms,
                "speech_pad_ms": self.profile.speech_pad_ms,
            } if vad_enabled else None,
        )
        text = " ".join(str(segment.text or "").strip() for segment in segments).strip()
        clean = self.deduplicator.accept(text, allow_overlap_trim=self.processing == "normal")
        asr_ms = int((time.perf_counter() - started) * 1000)
        if clean:
            emit_event(
                "transcript",
                text=clean,
                detected_language=str(getattr(info, "language", "") or ""),
                language_probability=float(getattr(info, "language_probability", 0.0) or 0.0),
                asr_ms=asr_ms,
                audio_seconds=round(audio.size / TARGET_SAMPLE_RATE, 3),
                model=self.profile.model_size,
                profile=self.profile.key,
            )
        else:
            emit_event("state", state="LISTENING", asr_ms=asr_ms, reason="empty_or_duplicate")


def transcribe_file(model: Any, path: Path, profile: AudioProfile, processing: str, language: Optional[str]) -> int:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File audio tidak ditemukan: {path}")
    emit_event("state", state="FILE_TRANSCRIBING", path=path.name)
    started = time.perf_counter()
    vad_enabled = processing == "vad"
    segments, info = model.transcribe(
        str(path),
        language=language,
        task="translate",
        beam_size=profile.beam_size,
        best_of=profile.best_of,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=vad_enabled,
        vad_parameters={"min_silence_duration_ms": profile.min_silence_ms, "speech_pad_ms": profile.speech_pad_ms} if vad_enabled else None,
    )
    count = 0
    for segment in segments:
        clean = " ".join(str(segment.text or "").strip().split())
        if not clean:
            continue
        count += 1
        emit_event(
            "transcript",
            text=clean,
            detected_language=str(getattr(info, "language", "") or ""),
            language_probability=float(getattr(info, "language_probability", 0.0) or 0.0),
            asr_ms=int((time.perf_counter() - started) * 1000),
            audio_seconds=max(0.0, float(getattr(segment, "end", 0.0) or 0.0) - float(getattr(segment, "start", 0.0) or 0.0)),
            model=profile.model_size,
            profile=profile.key,
            file_segment=count,
        )
    emit_event("state", state="FILE_COMPLETE", segments=count, total_ms=int((time.perf_counter() - started) * 1000))
    return count


def capture_live(model: Any, profile: AudioProfile, processing: str, language: Optional[str], device_index: int) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Audio internal langsung saat ini memerlukan Windows WASAPI. Gunakan File audio uji pada sistem lain.")
    import pyaudiowpatch as pyaudio

    segmenter = LiveAudioSegmenter(profile, processing=processing, sample_rate=TARGET_SAMPLE_RATE)
    worker = ASRInferenceWorker(model, profile, processing, language)
    worker.start()
    last_meter = 0.0
    try:
        with pyaudio.PyAudio() as manager:
            device = _resolve_loopback_device(manager, device_index)
            channels = max(1, int(device.get("maxInputChannels", 1)))
            source_rate = int(float(device.get("defaultSampleRate", 48000)))
            source_name = str(device.get("name", "WASAPI Loopback"))
            source_index = int(device.get("index", -1))
            frames_per_buffer = max(512, min(2048, int(source_rate * 0.025)))
            emit_event(
                "state",
                state="LISTENING",
                device=source_name,
                device_index=source_index,
                channels=channels,
                sample_rate=source_rate,
                processing=processing,
            )
            with manager.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=source_rate,
                frames_per_buffer=frames_per_buffer,
                input=True,
                input_device_index=source_index,
            ) as stream:
                while not STOP_EVENT.is_set():
                    payload = stream.read(frames_per_buffer, exception_on_overflow=False)
                    mono = pcm16_to_mono_float(payload, channels)
                    audio_16k = resample_linear(mono, source_rate, TARGET_SAMPLE_RATE)
                    now = time.monotonic()
                    if now - last_meter >= 0.5:
                        emit_event(
                            "meter",
                            rms=round(audio_rms(audio_16k), 6),
                            speech_active=segmenter.speech_active,
                            threshold=round(segmenter.threshold, 6),
                        )
                        last_meter = now
                    segment = segmenter.feed(audio_16k)
                    if segment is not None:
                        worker.submit(segment)
    finally:
        remainder = segmenter.flush()
        if remainder is not None:
            worker.submit(remainder)
            time.sleep(0.1)
        worker.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORT Audio ASR CPU/GPU worker and setup sidecar")
    parser.add_argument("--profile", default="normal", choices=["speed", "normal", "accurate"])
    parser.add_argument("--processing", default="vad", choices=["normal", "vad"])
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-size", default="")
    parser.add_argument("--asr-device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--compute-type", default="")
    parser.add_argument("--model-root", default=str(Path(__file__).resolve().parent / "_runtime" / "audio_models"))
    parser.add_argument("--device-index", type=int, default=-1)
    parser.add_argument("--file", default="")
    parser.add_argument("--probe-json", action="store_true")
    parser.add_argument("--list-devices-json", action="store_true")
    parser.add_argument("--prepare-model", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--worker-json", action="store_true")
    parser.add_argument("--retry-count", type=int, default=3)
    parser.add_argument("--inspect-model-json", action="store_true")
    parser.add_argument("--profile-json", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    _install_signal_handlers()
    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass
    if args.profile_json:
        emit_event("profile", **profile_payload(args.profile))
        return 0
    if args.probe_json:
        probe = dependency_probe(args.asr_device)
        emit_event("probe", **probe)
        return 0 if probe.get("ready") else 1
    if args.list_devices_json:
        try:
            emit_event("devices", devices=list_loopback_devices(), platform=sys.platform)
            return 0
        except Exception as exc:
            emit_event("error", stage="devices", message=str(exc))
            return 2
    profile = get_audio_profile(args.profile)
    processing = str(args.processing or "vad").lower()
    model_size = str(args.model_size or profile.model_size).strip().lower()
    device = "cuda" if str(args.asr_device).lower() == "cuda" else "cpu"
    compute_type = str(args.compute_type or ("int8_float16" if device == "cuda" else "int8"))
    model_root = Path(args.model_root).expanduser().resolve()
    try:
        if args.inspect_model_json:
            emit_event("model_inspection", **inspect_local_model(model_root, model_size).as_dict())
            return 0
        if args.prepare_model:
            prepared_path = _prepare_whisper(profile, model_root, retry_count=args.retry_count, model_size=model_size)
            inspection = inspect_model_dir(prepared_path, model_size)
            if not inspection.ready:
                raise RuntimeError("Validasi model gagal setelah download: " + model_problem_text(inspection))
            if args.download_only:
                emit_event(
                    "prepared",
                    profile=profile.key,
                    model=model_size,
                    model_root=str(model_root),
                    model_path=inspection.path,
                    device="download_only",
                    files_verified=True,
                )
                return 0
        model = _load_whisper(profile, model_root, model_size=model_size, device=device, compute_type=compute_type)
        if args.prepare_model:
            emit_event(
                "prepared",
                profile=profile.key,
                model=model_size,
                model_root=str(model_root),
                model_path=inspection.path,
                files_verified=True,
            )
            return 0
        language = _language_value(args.language)
        if args.worker_json:
            return run_worker(
                model,
                profile=profile,
                processing=processing,
                language=language,
                model_size=model_size,
                device=device,
                compute_type=compute_type,
            )
        if args.file:
            transcribe_file(model, Path(args.file).expanduser().resolve(), profile, processing, language)
        else:
            capture_live(model, profile, processing, language, int(args.device_index))
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        emit_event("error", stage="runtime", message=str(exc))
        return 1
    finally:
        emit_event("state", state="STOPPED")


if __name__ == "__main__":
    raise SystemExit(main())
