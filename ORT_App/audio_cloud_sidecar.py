from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Any, Deque, Iterable, Optional

import numpy as np

from app.audio.cloud_streaming import (
    normalize_audio_usage,
    normalize_realtime_profile,
    normalize_source_locale,
    normalize_target_language,
    resolve_live_media_policy,
)
from app.audio.glossary import load_audio_glossary
from app.audio.streaming import audio_rms, pcm16_to_mono_float, resample_linear


EVENT_PREFIX = "ORT_AUDIO_CLOUD_EVENT "
CREDENTIAL_SERVICE = "ORT Translation Azure Speech"
CREDENTIAL_ACCOUNT = "subscription_key"
TARGET_SAMPLE_RATE = 16000
PCM_BYTES_PER_SECOND = TARGET_SAMPLE_RATE * 2
STOP_REQUESTED = False
_PRINT_LOCK = threading.Lock()


def emit_event(event_type: str, **payload: Any) -> None:
    event = {"type": str(event_type), "ts": time.time(), **payload}
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


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _keyring_module():
    import keyring

    return keyring


def _credential_details() -> tuple[str, str]:
    environment_key = str(os.environ.get("ORT_AZURE_SPEECH_KEY", "") or "").strip()
    if environment_key:
        return environment_key, "environment"
    stored = str(_keyring_module().get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT) or "").strip()
    return stored, "keyring" if stored else "none"


def _credential_key() -> str:
    return _credential_details()[0]


def _credential_region(config_path: Path) -> str:
    environment_region = str(os.environ.get("ORT_AZURE_SPEECH_REGION", "") or "").strip()
    if environment_region:
        return environment_region
    return str(_load_json(config_path).get("region") or "").strip()


def save_config_from_stdin(config_path: Path) -> int:
    try:
        raw = sys.stdin.readline()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("Payload konfigurasi Azure tidak valid.")
        region = str(payload.get("region") or "").strip()
        api_key = str(payload.get("api_key") or "").strip()
        if not region:
            raise ValueError("Region Azure Speech wajib diisi.")
        if api_key:
            _keyring_module().set_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT, api_key)
        if not api_key and not _credential_key():
            raise ValueError("API key Azure Speech belum tersimpan.")
        config = {
            "provider": "azure",
            "region": region,
            "source_locale": normalize_source_locale(str(payload.get("source_locale") or "ja-JP")),
            "target_language": normalize_target_language(str(payload.get("target_language") or "id")),
            "realtime_profile": normalize_realtime_profile(str(payload.get("realtime_profile") or "normal")),
            "updated_at": time.time(),
        }
        _write_json(config_path, config)
        emit_event(
            "config_saved",
            provider="azure",
            region=region,
            source_locale=config["source_locale"],
            target_language=config["target_language"],
            realtime_profile=config["realtime_profile"],
            credential_set=True,
        )
        return 0
    except Exception as exc:
        emit_event("error", stage="save_config", code="AZURE_CONFIG_SAVE_FAILED", message=str(exc), fatal=True)
        return 1


def clear_credentials(config_path: Path) -> int:
    try:
        keyring = _keyring_module()
        before = str(keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT) or "").strip()
        if before:
            keyring.delete_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
        remaining = str(keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT) or "").strip()
        if remaining:
            raise RuntimeError("Windows Credential Manager masih mengembalikan API key setelah penghapusan.")
        environment_set = bool(str(os.environ.get("ORT_AZURE_SPEECH_KEY", "") or "").strip())
        config = _load_json(config_path)
        if config:
            config["credential_cleared_at"] = time.time()
            _write_json(config_path, config)
        if environment_set:
            emit_event(
                "credentials_partially_cleared",
                provider="azure",
                credential_set=True,
                credential_source="environment",
                message="Credential Manager sudah dibersihkan, tetapi ORT_AZURE_SPEECH_KEY masih aktif di environment dan tidak dapat dihapus oleh aplikasi.",
            )
            return 2
        emit_event("credentials_cleared", provider="azure", credential_set=False, credential_source="none")
        return 0
    except Exception as exc:
        emit_event("error", stage="clear_credentials", code="AZURE_CREDENTIAL_CLEAR_FAILED", message=str(exc), fatal=True)
        return 1


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


def list_devices() -> int:
    if sys.platform != "win32":
        emit_event("devices", devices=[], message="WASAPI loopback hanya tersedia di Windows.")
        return 0
    try:
        import pyaudiowpatch as pyaudio

        with pyaudio.PyAudio() as manager:
            default_index = -1
            try:
                default_index = int(manager.get_default_wasapi_loopback().get("index", -1))
            except Exception:
                pass
            devices = []
            for item in manager.get_loopback_device_info_generator():
                devices.append({
                    "index": int(item.get("index", -1)),
                    "name": str(item.get("name") or "WASAPI Loopback"),
                    "channels": int(item.get("maxInputChannels", 0) or 0),
                    "sample_rate": int(float(item.get("defaultSampleRate", 0) or 0)),
                    "is_default": int(item.get("index", -1)) == default_index,
                })
        emit_event("devices", devices=devices)
        return 0
    except Exception as exc:
        emit_event("error", stage="devices", code="WASAPI_DEVICE_LIST_FAILED", message=str(exc), fatal=False)
        return 1


def _speech_sdk():
    import azure.cognitiveservices.speech as speechsdk

    return speechsdk


def _set_speech_property(config: Any, speechsdk: Any, property_name: str, value: Any) -> bool:
    try:
        property_id = getattr(speechsdk.PropertyId, property_name)
        config.set_property(property_id, str(value))
        return True
    except Exception:
        return False


def _build_translation_config(
    speechsdk: Any,
    key: str,
    region: str,
    source_locale: str,
    target_language: str,
    usage: str,
    realtime_profile: str,
):
    policy = resolve_live_media_policy(usage, source_locale, realtime_profile)
    config = speechsdk.translation.SpeechTranslationConfig(subscription=key, region=region)
    config.speech_recognition_language = source_locale
    config.add_target_language(target_language)
    _set_speech_property(config, speechsdk, "SpeechServiceResponse_StablePartialResultThreshold", policy.stable_partial_threshold)
    _set_speech_property(config, speechsdk, "Speech_SegmentationSilenceTimeoutMs", policy.segmentation_silence_ms)
    _set_speech_property(config, speechsdk, "Speech_SegmentationMaximumTimeMs", policy.segmentation_maximum_ms)
    _set_speech_property(config, speechsdk, "SpeechServiceConnection_InitialSilenceTimeoutMs", policy.initial_silence_ms)
    return config, policy


def _build_push_recognizer(
    speechsdk: Any,
    key: str,
    region: str,
    source_locale: str,
    target_language: str,
    usage: str,
    game: str,
    realtime_profile: str = "normal",
):
    translation_config, policy = _build_translation_config(
        speechsdk,
        key,
        region,
        source_locale,
        target_language,
        usage,
        realtime_profile,
    )
    audio_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=TARGET_SAMPLE_RATE,
        bits_per_sample=16,
        channels=1,
    )
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=translation_config,
        audio_config=audio_config,
    )
    try:
        phrase_list = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
        glossary = load_audio_glossary(game)
        aliases = glossary.get("asr_aliases") or {}
        phrases = {str(item).strip() for item in (glossary.get("asr_phrases") or []) if str(item).strip()}
        phrases.update(str(key).strip() for key in aliases.keys() if str(key).strip())
        phrases.update(str(value).strip() for value in aliases.values() if str(value).strip())
        for phrase in sorted(phrases)[:250]:
            phrase_list.addPhrase(phrase)
    except Exception:
        pass
    return recognizer, push_stream, policy


def network_test(config_path: Path, source_locale: str, target_language: str) -> dict:
    speechsdk = _speech_sdk()
    key = _credential_key()
    region = _credential_region(config_path)
    if not key or not region:
        raise RuntimeError("Kredensial atau region Azure Speech belum tersedia.")
    recognizer, push_stream, _policy = _build_push_recognizer(
        speechsdk,
        key,
        region,
        normalize_source_locale(source_locale),
        normalize_target_language(target_language),
        "live_media",
        "GFL2_EXILIUM",
        "speed",
    )
    connected = threading.Event()
    canceled = threading.Event()
    detail = {"error": ""}

    def on_started(_event: Any) -> None:
        connected.set()

    def on_canceled(event: Any) -> None:
        detail["error"] = str(getattr(getattr(event, "cancellation_details", None), "error_details", "") or "")
        canceled.set()

    recognizer.session_started.connect(on_started)
    recognizer.canceled.connect(on_canceled)
    recognizer.start_continuous_recognition_async().get()
    push_stream.write(bytes(PCM_BYTES_PER_SECOND // 5))
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and not connected.is_set() and not canceled.is_set():
        time.sleep(0.05)
    try:
        push_stream.close()
    except Exception:
        pass
    try:
        recognizer.stop_continuous_recognition_async().get()
    except Exception:
        pass
    return {
        "connected": connected.is_set() and not canceled.is_set(),
        "error": detail["error"][-1200:],
    }


def probe(config_path: Path, run_network_test: bool = False) -> int:
    result = {
        "provider": "azure",
        "sdk": False,
        "keyring": False,
        "wasapi": False,
        "credential_set": False,
        "region": _credential_region(config_path),
        "network_tested": bool(run_network_test),
        "cloud_connected": False,
        "errors": [],
    }
    try:
        speechsdk = _speech_sdk()
        result["sdk"] = True
        result["sdk_version"] = str(getattr(speechsdk, "__version__", "unknown"))
    except Exception as exc:
        result["errors"].append(f"Azure Speech SDK: {exc}")
    try:
        _keyring_module()
        result["keyring"] = True
        credential, credential_source = _credential_details()
        result["credential_set"] = bool(credential)
        result["credential_source"] = credential_source
    except Exception as exc:
        result["errors"].append(f"Windows Credential Manager: {exc}")
    if sys.platform == "win32":
        try:
            import pyaudiowpatch

            result["wasapi"] = True
            result["pyaudiowpatch_version"] = str(getattr(pyaudiowpatch, "__version__", "unknown"))
        except Exception as exc:
            result["errors"].append(f"PyAudioWPatch: {exc}")
    else:
        result["wasapi"] = False
    if run_network_test and result["sdk"] and result["credential_set"] and result["region"]:
        try:
            tested = network_test(config_path, "ja-JP", "id")
            result["cloud_connected"] = bool(tested.get("connected"))
            if tested.get("error"):
                result["errors"].append(str(tested["error"]))
        except Exception as exc:
            result["errors"].append(f"Azure connection: {exc}")
    result["ready"] = bool(
        result["sdk"]
        and result["keyring"]
        and result["credential_set"]
        and result["region"]
        and (result["wasapi"] if sys.platform == "win32" else True)
    )
    emit_event("probe", **result)
    return 0 if result["ready"] else 1


class RollingPcmBuffer:
    def __init__(self, seconds: float = 6.0):
        self.maximum_bytes = max(PCM_BYTES_PER_SECOND, int(float(seconds) * PCM_BYTES_PER_SECOND))
        self.parts: Deque[bytes] = deque()
        self.size = 0

    def append(self, payload: bytes) -> None:
        if not payload:
            return
        chunk = bytes(payload)
        if len(chunk) >= self.maximum_bytes:
            chunk = chunk[-self.maximum_bytes:]
            self.parts.clear()
            self.parts.append(chunk)
            self.size = len(chunk)
            return
        self.parts.append(chunk)
        self.size += len(chunk)
        while self.parts and self.size > self.maximum_bytes:
            overflow = self.size - self.maximum_bytes
            first = self.parts[0]
            if len(first) <= overflow:
                self.parts.popleft()
                self.size -= len(first)
                continue
            self.parts[0] = first[overflow:]
            self.size -= overflow
            break

    def as_float(self) -> np.ndarray:
        if not self.parts:
            return np.empty(0, dtype=np.float32)
        raw = b"".join(self.parts)
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32)
        return np.clip(samples / 32768.0, -1.0, 1.0)


def _float_to_pcm16(audio: np.ndarray) -> bytes:
    signal_data = np.asarray(audio, dtype=np.float32).reshape(-1)
    if signal_data.size == 0:
        return b""
    return np.clip(signal_data * 32767.0, -32768, 32767).astype("<i2").tobytes()


def _write_replay(spool_dir: Path, rolling: RollingPcmBuffer) -> str:
    signal_data = rolling.as_float()
    if signal_data.size < TARGET_SAMPLE_RATE // 3:
        return ""
    spool_dir.mkdir(parents=True, exist_ok=True)
    final_path = spool_dir / f"cloud-replay-{int(time.time() * 1000)}.npy"
    temporary_path = final_path.with_name("." + final_path.name + ".tmp.npy")
    np.save(temporary_path, signal_data, allow_pickle=False)
    os.replace(temporary_path, final_path)
    return str(final_path)


def _stream_loopback(
    push_stream: Any,
    device_index: int,
    rolling: RollingPcmBuffer,
    canceled: threading.Event,
    chunk_ms: int,
) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Audio internal Azure memerlukan Windows WASAPI.")
    import pyaudiowpatch as pyaudio

    last_meter = 0.0
    with pyaudio.PyAudio() as manager:
        device = _resolve_loopback_device(manager, int(device_index))
        channels = max(1, int(device.get("maxInputChannels", 1)))
        source_rate = int(float(device.get("defaultSampleRate", 48000)))
        source_index = int(device.get("index", -1))
        source_name = str(device.get("name") or "WASAPI Loopback")
        frames_per_buffer = max(256, min(2048, int(source_rate * max(10, int(chunk_ms)) / 1000.0)))
        emit_event(
            "state",
            state="STREAMING",
            cloud_connected=True,
            device=source_name,
            device_index=source_index,
            channels=channels,
            sample_rate=source_rate,
            chunk_ms=chunk_ms,
        )
        with manager.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=source_rate,
            frames_per_buffer=frames_per_buffer,
            input=True,
            input_device_index=source_index,
        ) as stream:
            while not STOP_REQUESTED and not canceled.is_set():
                payload = stream.read(frames_per_buffer, exception_on_overflow=False)
                mono = pcm16_to_mono_float(payload, channels)
                audio_16k = resample_linear(mono, source_rate, TARGET_SAMPLE_RATE)
                pcm = _float_to_pcm16(audio_16k)
                if pcm:
                    rolling.append(pcm)
                    push_stream.write(pcm)
                now = time.monotonic()
                if now - last_meter >= 0.5:
                    emit_event("meter", rms=round(audio_rms(audio_16k), 6), cloud_connected=True)
                    last_meter = now


def _stream_wav(
    path: Path,
    push_stream: Any,
    rolling: RollingPcmBuffer,
    canceled: threading.Event,
    chunk_ms: int,
) -> None:
    with wave.open(str(path), "rb") as source:
        channels = max(1, int(source.getnchannels()))
        sample_width = int(source.getsampwidth())
        source_rate = int(source.getframerate())
        if sample_width != 2:
            raise RuntimeError("Uji Azure saat ini memerlukan WAV PCM 16-bit.")
        emit_event(
            "state",
            state="STREAMING",
            cloud_connected=True,
            device=str(path),
            channels=channels,
            sample_rate=source_rate,
            chunk_ms=chunk_ms,
        )
        frames_per_chunk = max(1, int(source_rate * max(10, int(chunk_ms)) / 1000.0))
        while not STOP_REQUESTED and not canceled.is_set():
            payload = source.readframes(frames_per_chunk)
            if not payload:
                break
            mono = pcm16_to_mono_float(payload, channels)
            audio_16k = resample_linear(mono, source_rate, TARGET_SAMPLE_RATE)
            pcm = _float_to_pcm16(audio_16k)
            if pcm:
                rolling.append(pcm)
                push_stream.write(pcm)
                time.sleep(len(pcm) / float(PCM_BYTES_PER_SECOND))


def _drain_final_callbacks(
    policy: Any,
    counters: dict,
    callback_clock: dict,
    session_stopped: threading.Event,
) -> None:
    started = time.monotonic()
    final_before = int(counters.get("final", 0))
    while time.monotonic() - started < float(policy.final_drain_timeout_s):
        now = time.monotonic()
        quiet_for = now - float(callback_clock.get("last", started))
        received_new_final = int(counters.get("final", 0)) > final_before
        if session_stopped.is_set() and quiet_for >= 0.2:
            break
        if received_new_final and quiet_for >= float(policy.final_quiet_period_s):
            break
        time.sleep(0.04)


def stream_cloud(args: argparse.Namespace) -> int:
    config_path = Path(args.config_path).expanduser().resolve()
    config = _load_json(config_path)
    key = _credential_key()
    credential_source = "environment" if str(os.environ.get("ORT_AZURE_SPEECH_KEY", "") or "").strip() else ("keyring" if key else "none")
    region = _credential_region(config_path)
    source_locale = normalize_source_locale(args.source_locale or config.get("source_locale") or "")
    target_language = normalize_target_language(args.target_language or config.get("target_language") or "id")
    usage = normalize_audio_usage(args.usage)
    realtime_profile = normalize_realtime_profile(getattr(args, "realtime_profile", "") or config.get("realtime_profile") or "normal")
    if not key or not region:
        emit_event(
            "error",
            stage="credentials",
            code="AZURE_CREDENTIALS_MISSING",
            message="API key atau region Azure Speech belum tersimpan.",
            fatal=True,
            fallback_recommended=True,
        )
        return 2
    if not source_locale or source_locale.lower() in {"auto", "auto-detect"}:
        emit_event(
            "error",
            stage="language",
            code="AZURE_SOURCE_LANGUAGE_REQUIRED",
            message="Live Media Azure memerlukan bahasa sumber tetap agar hasil interim tersedia.",
            fatal=True,
            fallback_recommended=True,
        )
        return 2

    speechsdk = _speech_sdk()
    recognizer, push_stream, policy = _build_push_recognizer(
        speechsdk,
        key,
        region,
        source_locale,
        target_language,
        usage,
        args.game,
        realtime_profile,
    )
    canceled = threading.Event()
    session_started = threading.Event()
    session_stopped = threading.Event()
    input_finished = threading.Event()
    session_start = time.monotonic()
    audio_start = {"at": 0.0}
    counters = {"interim": 0, "final": 0}
    callback_clock = {"last": session_start, "first_interim": 0.0, "first_final": 0.0}
    cancellation = {"code": "", "message": ""}
    stream_closed = False

    def result_latency_ms(result: Any) -> int:
        try:
            base = float(audio_start.get("at") or session_start)
            audio_end_seconds = (float(getattr(result, "offset", 0) or 0) + float(getattr(result, "duration", 0) or 0)) / 10_000_000.0
            return max(0, int(((time.monotonic() - base) - audio_end_seconds) * 1000.0))
        except Exception:
            return 0

    def result_payload(result: Any) -> dict:
        translations = dict(getattr(result, "translations", {}) or {})
        return {
            "result_id": str(getattr(result, "result_id", "") or ""),
            "source": " ".join(str(getattr(result, "text", "") or "").split()),
            "translation": " ".join(str(translations.get(target_language, "") or "").split()),
            "source_locale": source_locale,
            "target_language": target_language,
            "cloud_ms": result_latency_ms(result),
            "session_elapsed_ms": max(0, int((time.monotonic() - session_start) * 1000.0)),
        }

    def on_recognizing(event: Any) -> None:
        payload = result_payload(event.result)
        if not payload["source"] and not payload["translation"]:
            return
        now = time.monotonic()
        callback_clock["last"] = now
        counters["interim"] += 1
        if not callback_clock["first_interim"]:
            callback_clock["first_interim"] = now
            emit_event(
                "telemetry",
                metric="first_interim_ms",
                value=max(0, int((now - float(audio_start.get("at") or session_start)) * 1000.0)),
                profile=realtime_profile,
            )
        emit_event("interim", sequence=counters["interim"], cloud_connected=True, provider="azure", **payload)

    def on_recognized(event: Any) -> None:
        result = event.result
        callback_clock["last"] = time.monotonic()
        if result.reason == speechsdk.ResultReason.TranslatedSpeech:
            payload = result_payload(result)
            if not payload["source"] and not payload["translation"]:
                return
            counters["final"] += 1
            if not callback_clock["first_final"]:
                callback_clock["first_final"] = callback_clock["last"]
                emit_event(
                    "telemetry",
                    metric="first_final_ms",
                    value=max(0, int((callback_clock["last"] - float(audio_start.get("at") or session_start)) * 1000.0)),
                    profile=realtime_profile,
                )
            emit_event("final", sequence=counters["final"], cloud_connected=True, provider="azure", **payload)
        elif result.reason == speechsdk.ResultReason.NoMatch:
            emit_event("drop", reason="NO_MATCH", provider="azure", overlay_visible=False)

    def on_started(_event: Any) -> None:
        session_started.set()
        emit_event(
            "state",
            state="CLOUD_CONNECTED",
            cloud_connected=True,
            provider="azure",
            region=region,
            source_locale=source_locale,
            target_language=target_language,
            usage=usage,
            realtime_profile=realtime_profile,
            credential_source=credential_source,
            **policy.as_dict(),
        )

    def on_stopped(_event: Any) -> None:
        session_stopped.set()
        if not STOP_REQUESTED and not input_finished.is_set():
            cancellation["code"] = "AZURE_SESSION_STOPPED_EARLY"
            cancellation["message"] = "Sesi Azure Speech berhenti sebelum aliran audio selesai."
            canceled.set()

    def on_canceled(event: Any) -> None:
        details = getattr(event, "cancellation_details", None)
        cancellation["code"] = str(getattr(details, "reason", "") or "AZURE_CANCELED")
        cancellation["message"] = str(getattr(details, "error_details", "") or "Koneksi Azure Speech dibatalkan.")
        canceled.set()

    recognizer.recognizing.connect(on_recognizing)
    recognizer.recognized.connect(on_recognized)
    recognizer.session_started.connect(on_started)
    recognizer.session_stopped.connect(on_stopped)
    recognizer.canceled.connect(on_canceled)

    rolling = RollingPcmBuffer(seconds=6.0)
    spool_dir = Path(args.spool_dir).expanduser().resolve()
    emit_event(
        "state",
        state="CONNECTING",
        cloud_connected=False,
        provider="azure",
        source_locale=source_locale,
        target_language=target_language,
        usage=usage,
        realtime_profile=realtime_profile,
    )
    try:
        recognizer.start_continuous_recognition_async().get()
        # A short silent pre-roll opens the service connection without exposing a
        # false STREAMING state to the UI.
        push_stream.write(bytes(PCM_BYTES_PER_SECOND // 10))
        if not session_started.wait(float(policy.connection_timeout_s)):
            if canceled.is_set():
                raise RuntimeError(cancellation["message"] or "Koneksi Azure Speech dibatalkan.")
            raise TimeoutError("Azure Speech tidak mengonfirmasi koneksi dalam batas waktu.")
        audio_start["at"] = time.monotonic()
        emit_event("telemetry", metric="cloud_connect_ms", value=max(0, int((audio_start["at"] - session_start) * 1000.0)))
        if args.input_mode == "file":
            file_path = Path(args.test_file).expanduser().resolve()
            if not file_path.is_file() or file_path.suffix.lower() != ".wav":
                raise RuntimeError("Uji Azure memerlukan file WAV PCM 16-bit.")
            _stream_wav(file_path, push_stream, rolling, canceled, policy.audio_chunk_ms)
        else:
            _stream_loopback(push_stream, int(args.device_index), rolling, canceled, policy.audio_chunk_ms)
        input_finished.set()
        try:
            push_stream.close()
            stream_closed = True
        except Exception:
            pass
        _drain_final_callbacks(policy, counters, callback_clock, session_stopped)
        if canceled.is_set() and not STOP_REQUESTED:
            raise RuntimeError(cancellation["message"] or "Sesi Azure Speech berhenti.")
        emit_event(
            "telemetry",
            metric="session_summary",
            interim_count=counters["interim"],
            final_count=counters["final"],
            first_interim_ms=(
                max(0, int((callback_clock["first_interim"] - audio_start["at"]) * 1000.0))
                if callback_clock["first_interim"] and audio_start["at"] else None
            ),
            profile=realtime_profile,
        )
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        replay_path = _write_replay(spool_dir, rolling)
        emit_event(
            "error",
            stage="cloud_stream",
            code=cancellation["code"] or "AZURE_STREAM_FAILED",
            message=str(exc),
            fatal=True,
            fallback_recommended=True,
            replay_path=replay_path,
            cloud_connected=False,
        )
        return 1
    finally:
        input_finished.set()
        if not stream_closed:
            try:
                push_stream.close()
            except Exception:
                pass
        try:
            recognizer.stop_continuous_recognition_async().get()
        except Exception:
            pass
        emit_event(
            "state",
            state="CLOUD_STOPPED",
            cloud_connected=False,
            interim_count=counters["interim"],
            final_count=counters["final"],
            realtime_profile=realtime_profile,
        )

def self_test() -> int:
    timeline = [
        {"type": "interim", "at_ms": 820, "source": "作戦を", "translation": "Operasi"},
        {"type": "interim", "at_ms": 1260, "source": "作戦を開始する", "translation": "Memulai operasi"},
        {"type": "final", "at_ms": 1840, "source": "作戦を開始する", "translation": "Mulai operasinya."},
    ]
    for item in timeline:
        emit_event(item.pop("type"), provider="azure_simulated", cloud_connected=True, **item)
    emit_event(
        "self_test",
        ready=True,
        first_interim_ms=820,
        final_ms=1840,
        interim_before_final=True,
        credential_exposed=False,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORT Azure live media streaming sidecar")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--probe-json", action="store_true")
    action.add_argument("--save-config-json", action="store_true")
    action.add_argument("--clear-credentials-json", action="store_true")
    action.add_argument("--list-devices-json", action="store_true")
    action.add_argument("--stream", action="store_true")
    action.add_argument("--self-test-json", action="store_true")
    parser.add_argument("--network-test", action="store_true")
    parser.add_argument("--config-path", default=str(Path(__file__).resolve().parent / "_runtime" / "audio_cloud" / "config.json"))
    parser.add_argument("--source-locale", default="")
    parser.add_argument("--target-language", default="id")
    parser.add_argument("--usage", default="live_media")
    parser.add_argument("--realtime-profile", default="normal", choices=["speed", "normal", "accurate"])
    parser.add_argument("--game", default="GFL2_EXILIUM")
    parser.add_argument("--input-mode", default="loopback", choices=["loopback", "file"])
    parser.add_argument("--device-index", default="-1")
    parser.add_argument("--test-file", default="")
    parser.add_argument("--spool-dir", default=str(Path(os.environ.get("TEMP", ".")) / "ort_audio_cloud_spool"))
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    _install_signal_handlers()
    if args.save_config_json:
        return save_config_from_stdin(Path(args.config_path).expanduser().resolve())
    if args.clear_credentials_json:
        return clear_credentials(Path(args.config_path).expanduser().resolve())
    if args.list_devices_json:
        return list_devices()
    if args.probe_json:
        return probe(Path(args.config_path).expanduser().resolve(), bool(args.network_test))
    if args.self_test_json:
        return self_test()
    return stream_cloud(args)


if __name__ == "__main__":
    raise SystemExit(main())
