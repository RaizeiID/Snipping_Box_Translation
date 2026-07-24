#!/usr/bin/env python3
from __future__ import annotations

import io
import sys
import tempfile
import threading
import time
import types
import wave
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

# The distributed patch intentionally contains changed files only. These tiny
# stubs allow this regression to validate the patch in isolation; a complete ORT
# installation uses the real modules from v8.9.4.
if "app.audio.glossary" not in sys.modules:
    glossary_stub = types.ModuleType("app.audio.glossary")
    glossary_stub.load_audio_glossary = lambda _game: {
        "asr_phrases": ["グローザ", "Groza"],
        "asr_aliases": {"グローザ": "Groza"},
    }
    sys.modules["app.audio.glossary"] = glossary_stub
if "app.audio.streaming" not in sys.modules:
    streaming_stub = types.ModuleType("app.audio.streaming")

    def pcm16_to_mono_float(payload: bytes, channels: int):
        samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        return samples.astype(np.float32)

    def resample_linear(audio, source_rate: int, target_rate: int):
        signal = np.asarray(audio, dtype=np.float32).reshape(-1)
        if signal.size == 0 or source_rate == target_rate:
            return signal
        target_size = max(1, int(round(signal.size * target_rate / source_rate)))
        return np.interp(
            np.linspace(0.0, 1.0, target_size, endpoint=False),
            np.linspace(0.0, 1.0, signal.size, endpoint=False),
            signal,
        ).astype(np.float32)

    streaming_stub.pcm16_to_mono_float = pcm16_to_mono_float
    streaming_stub.resample_linear = resample_linear
    streaming_stub.audio_rms = lambda audio: float(np.sqrt(np.mean(np.square(audio)))) if np.asarray(audio).size else 0.0
    sys.modules["app.audio.streaming"] = streaming_stub

from app.audio.cloud_streaming import LiveSubtitleStabilizer, resolve_live_media_policy
from audio_cloud_backend import parse_cloud_events
import audio_cloud_sidecar
from audio_cloud_sidecar import RollingPcmBuffer
from build_info import APP_VERSION_TAG, RELEASE_NAME


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Real-Time Video Translation Update", "Real-Time Cloud Enforcement Update"}, f"unexpected release: {RELEASE_NAME}")
    for path in (ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt", PROJECT_ROOT / "VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_japanese_realtime_policy() -> None:
    instant = resolve_live_media_policy("live_media", "ja-JP", "speed")
    balanced = resolve_live_media_policy("live_media", "ja-JP", "normal")
    accurate = resolve_live_media_policy("live_media", "ja-JP", "accurate")
    assert_true(instant.audio_chunk_ms == 20, "instant streaming is not using 20 ms chunks")
    assert_true(instant.segmentation_silence_ms < balanced.segmentation_silence_ms < accurate.segmentation_silence_ms, "profile endpoint ordering changed")
    assert_true(instant.stable_partial_threshold == 1, "instant profile does not expose early partials")
    assert_true(instant.segmentation_maximum_ms <= 7000, "Japanese instant phrases can still grow too long")


def test_phone_style_subtitle_coalescing() -> None:
    gate = LiveSubtitleStabilizer(minimum_interim_interval=0.10)
    first = gate.accept({"type": "interim", "result_id": "r1", "source": "作戦", "translation": "Operasi"}, now=1.00)
    burst = gate.accept({"type": "interim", "result_id": "r1", "source": "作戦を", "translation": "Operasi akan"}, now=1.05)
    newest = gate.accept({"type": "interim", "result_id": "r1", "source": "作戦を開始", "translation": "Operasi akan dimulai"}, now=1.12)
    final_a = gate.accept({"type": "final", "result_id": "r1", "source": "作戦を開始する", "translation": "Operasi dimulai."}, now=1.40)
    final_b = gate.accept({"type": "final", "result_id": "r2", "source": "作戦を開始する", "translation": "Operasi dimulai."}, now=1.50)
    stale = gate.accept({"type": "interim", "result_id": "r1", "source": "作戦", "translation": "Operasi"}, now=1.55)
    assert_true(first and first["display_revision"] == 1, "first interim missing")
    assert_true(burst is None, "rapid callback burst was not throttled")
    assert_true(newest and newest["display_revision"] == 2, "newest interim did not replace the same line")
    assert_true(final_a and final_a["stable"], "final did not lock the live line")
    assert_true(final_b is not None, "a second speaker repeating the same sentence was hidden")
    assert_true(stale is None, "stale interim arrived after final")


def test_rolling_buffer_keeps_tail() -> None:
    rolling = RollingPcmBuffer(seconds=1.0)
    samples = np.arange(32000, dtype=np.int16)
    rolling.append(samples.astype("<i2").tobytes())
    replay = rolling.as_float()
    assert_true(replay.size == 16000, f"oversized payload lost rolling tail: {replay.size}")
    expected_last = float(samples[-1]) / 32768.0
    assert_true(abs(float(replay[-1]) - expected_last) < 1e-5, "rolling buffer did not preserve the newest sample")


def test_connection_order_and_delayed_final_drain() -> None:
    class Signal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

        def emit(self, event):
            for callback in list(self.callbacks):
                callback(event)

    class Future:
        def get(self):
            return None

    class TranslationConfig:
        def __init__(self, subscription, region):
            self.subscription = subscription
            self.region = region
            self.speech_recognition_language = ""

        def add_target_language(self, _language):
            return None

        def set_property(self, *_args):
            return None

    class FakeRecognizer:
        def __init__(self, sdk):
            self.sdk = sdk
            self.recognizing = Signal()
            self.recognized = Signal()
            self.session_started = Signal()
            self.session_stopped = Signal()
            self.canceled = Signal()

        def start_continuous_recognition_async(self):
            self.session_started.emit(SimpleNamespace())
            return Future()

        def stop_continuous_recognition_async(self):
            return Future()

    class PushStream:
        def __init__(self, sdk):
            self.sdk = sdk
            self.closed = False

        def write(self, payload):
            assert payload

        def close(self):
            if self.closed:
                return
            self.closed = True

            def delayed_final():
                time.sleep(0.15)
                result = SimpleNamespace(
                    result_id="late-final",
                    text="作戦を開始する",
                    translations={"id": "Operasi dimulai."},
                    offset=0,
                    duration=2_000_000,
                    reason=self.sdk.ResultReason.TranslatedSpeech,
                )
                self.sdk.recognizer.recognized.emit(SimpleNamespace(result=result))
                self.sdk.recognizer.session_stopped.emit(SimpleNamespace())

            threading.Thread(target=delayed_final, daemon=True).start()

    class FakeSdk:
        class ResultReason:
            TranslatedSpeech = "translated"
            NoMatch = "no_match"

        class PropertyId:
            SpeechServiceResponse_StablePartialResultThreshold = "stable"
            Speech_SegmentationSilenceTimeoutMs = "silence"
            Speech_SegmentationMaximumTimeMs = "maximum"
            SpeechServiceConnection_InitialSilenceTimeoutMs = "initial"

        class PhraseListGrammar:
            @staticmethod
            def from_recognizer(_recognizer):
                return SimpleNamespace(addPhrase=lambda _phrase: None)

        def __init__(self):
            self.translation = SimpleNamespace(SpeechTranslationConfig=TranslationConfig, TranslationRecognizer=self.make_recognizer)
            self.audio = SimpleNamespace(
                AudioStreamFormat=lambda **_kwargs: object(),
                PushAudioInputStream=self.make_stream,
                AudioConfig=lambda **_kwargs: object(),
            )
            self.recognizer = None

        def make_recognizer(self, **_kwargs):
            self.recognizer = FakeRecognizer(self)
            return self.recognizer

        def make_stream(self, **_kwargs):
            return PushStream(self)

    original_sdk = audio_cloud_sidecar._speech_sdk
    original_key = audio_cloud_sidecar._credential_key
    original_region = audio_cloud_sidecar._credential_region
    audio_cloud_sidecar._speech_sdk = lambda: FakeSdk()
    audio_cloud_sidecar._credential_key = lambda: "test-secret"
    audio_cloud_sidecar._credential_region = lambda _path: "southeastasia"
    audio_cloud_sidecar.STOP_REQUESTED = False
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wav_path = root / "sample.wav"
            with wave.open(str(wav_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(np.full(3200, 500, dtype="<i2").tobytes())
            args = SimpleNamespace(
                config_path=str(root / "config.json"),
                source_locale="ja-JP",
                target_language="id",
                usage="live_media",
                realtime_profile="speed",
                game="GFL2_EXILIUM",
                input_mode="file",
                test_file=str(wav_path),
                device_index="-1",
                spool_dir=str(root / "spool"),
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = audio_cloud_sidecar.stream_cloud(args)
            events = parse_cloud_events(output.getvalue())
            states = [item.get("state") for item in events if item.get("type") == "state"]
            assert_true(code == 0, output.getvalue())
            assert_true(states.index("CONNECTING") < states.index("CLOUD_CONNECTED") < states.index("STREAMING"), f"invalid state order: {states}")
            assert_true(any(item.get("type") == "final" and item.get("result_id") == "late-final" for item in events), "delayed final was lost after EOF")
            assert_true("test-secret" not in output.getvalue(), "credential leaked into output")
    finally:
        audio_cloud_sidecar._speech_sdk = original_sdk
        audio_cloud_sidecar._credential_key = original_key
        audio_cloud_sidecar._credential_region = original_region
        audio_cloud_sidecar.STOP_REQUESTED = False


def test_credential_clear_failure_is_truthful() -> None:
    class BrokenKeyring:
        def get_password(self, *_args):
            return "still-present"

        def delete_password(self, *_args):
            raise RuntimeError("credential backend locked")

    original = audio_cloud_sidecar._keyring_module
    audio_cloud_sidecar._keyring_module = lambda: BrokenKeyring()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with redirect_stdout(output):
                code = audio_cloud_sidecar.clear_credentials(Path(temporary) / "config.json")
            events = parse_cloud_events(output.getvalue())
            assert_true(code != 0, "credential deletion failure was reported as success")
            assert_true(any(item.get("type") == "error" and item.get("code") == "AZURE_CREDENTIAL_CLEAR_FAILED" for item in events), output.getvalue())
    finally:
        audio_cloud_sidecar._keyring_module = original


def main() -> None:
    test_release_identity()
    test_japanese_realtime_policy()
    test_phone_style_subtitle_coalescing()
    test_rolling_buffer_keeps_tail()
    test_connection_order_and_delayed_final_drain()
    test_credential_clear_failure_is_truthful()
    print(f"{APP_VERSION_TAG} Real-Time Video Translation regression PASS")


if __name__ == "__main__":
    main()
