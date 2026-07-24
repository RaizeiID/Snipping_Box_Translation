#!/usr/bin/env python3
from __future__ import annotations

import json
import io
import subprocess
import sys
import tempfile
import wave
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.cloud_streaming import (
    CloudFallbackLatch,
    LiveSubtitleStabilizer,
    normalize_audio_engine,
    normalize_audio_usage,
    normalize_source_locale,
    resolve_cloud_engine,
)
from audio_cloud_backend import parse_cloud_events
from audio_cloud_sidecar import RollingPcmBuffer, _write_replay
from build_info import APP_VERSION_TAG, RELEASE_NAME
import audio_cloud_backend
import audio_cloud_sidecar


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Cloud Live Media Streaming Update", "Real-Time Video Translation Update"}, f"unexpected release: {RELEASE_NAME}")
    for path in (ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt", PROJECT_ROOT / "VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_engine_resolution() -> None:
    assert_true(normalize_audio_engine("cloud") == "azure", "cloud alias did not resolve to Azure")
    assert_true(normalize_audio_engine("cloud_fallback") == "azure_fallback", "fallback alias changed")
    assert_true(normalize_audio_usage("media") == "live_media", "media alias changed")
    assert_true(normalize_source_locale("ja") == "ja-JP", "Japanese locale mapping changed")

    cloud = resolve_cloud_engine("azure", True, False)
    assert_true(cloud.ready and cloud.effective == "azure", "strict Azure did not resolve")
    strict_failure = resolve_cloud_engine("azure", False, True)
    assert_true(not strict_failure.ready and strict_failure.effective == "azure", "strict Azure silently fell back")
    guarded = resolve_cloud_engine("azure_fallback", False, True)
    assert_true(guarded.ready and guarded.effective == "local_guard", "Azure fallback did not guard locally")
    hybrid = resolve_cloud_engine("azure_fallback", True, True)
    assert_true(hybrid.ready and hybrid.effective == "azure", "Azure was not primary when both paths were ready")


def test_interim_final_stabilization() -> None:
    gate = LiveSubtitleStabilizer(minimum_interim_interval=0.12)
    first = gate.accept(
        {"type": "interim", "result_id": "r1", "source": "作戦を", "translation": "Operasi", "cloud_ms": 180},
        now=0.82,
    )
    duplicate = gate.accept(
        {"type": "interim", "result_id": "r1", "source": "作戦を", "translation": "Operasi", "cloud_ms": 170},
        now=0.86,
    )
    expanded = gate.accept(
        {"type": "interim", "result_id": "r1", "source": "作戦を開始する", "translation": "Memulai operasi", "cloud_ms": 190},
        now=1.26,
    )
    final = gate.accept(
        {"type": "final", "result_id": "r1", "source": "作戦を開始する", "translation": "Mulai operasinya.", "cloud_ms": 210},
        now=1.84,
    )
    duplicate_final = gate.accept(
        {"type": "final", "result_id": "r1-copy", "source": "作戦を開始する", "translation": "Mulai operasinya."},
        now=2.0,
    )
    legitimate_repeat = gate.accept(
        {"type": "final", "result_id": "r2", "source": "作戦を開始する", "translation": "Mulai operasinya."},
        now=3.5,
    )
    assert_true(first and first["stable"] is False and first["translation"] == "Operasi", "first interim was not displayable")
    assert_true(duplicate is None, "identical high-frequency interim was not throttled")
    assert_true(expanded and expanded["display_sequence"] == 2, "expanded interim was lost")
    assert_true(final and final["stable"] and final["display_sequence"] == 3, "final did not atomically replace interim")
    assert_true(duplicate_final and duplicate_final["display_sequence"] == 4, "different result ids were incorrectly merged")
    assert_true(legitimate_repeat and legitimate_repeat["display_sequence"] == 5, "a later repeated line was incorrectly hidden")


def test_fallback_latch_and_replay() -> None:
    latch = CloudFallbackLatch()
    first = latch.activate("NETWORK_LOST", "replay.npy")
    second = latch.activate("NETWORK_LOST_AGAIN", "replay-2.npy")
    assert_true(first and first["effective_engine"] == "local_fallback", "first cloud failure did not activate fallback")
    assert_true(second is None and latch.reason == "NETWORK_LOST", "fallback flapped after activation")

    rolling = RollingPcmBuffer(seconds=1.0)
    samples = np.full(16000, 0.05, dtype=np.float32)
    rolling.append(np.clip(samples * 32767.0, -32768, 32767).astype("<i2").tobytes())
    with tempfile.TemporaryDirectory() as temporary:
        path = _write_replay(Path(temporary), rolling)
        replay = np.load(path, allow_pickle=False)
        assert_true(replay.size == 16000, f"rolling replay length changed: {replay.size}")
        assert_true(float(np.max(np.abs(replay))) > 0.04, "rolling replay lost audio amplitude")


def test_sidecar_simulation_timing() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "audio_cloud_sidecar.py"), "--self-test-json"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    events = parse_cloud_events(result.stdout)
    self_test = next((item for item in events if item.get("type") == "self_test"), {})
    interim = next((item for item in events if item.get("type") == "interim"), {})
    final = next((item for item in events if item.get("type") == "final"), {})
    assert_true(result.returncode == 0 and self_test.get("ready"), f"cloud sidecar self-test failed: {result.stdout}")
    assert_true(int(interim.get("at_ms", 9999)) <= 1200, "first simulated interim missed the real-time target")
    assert_true(int(final.get("at_ms", 0)) > int(interim.get("at_ms", 9999)), "final arrived before interim")
    assert_true(self_test.get("credential_exposed") is False, "self-test reported credential exposure")


def test_fake_azure_stream_callbacks() -> None:
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
            self.targets = []

        def add_target_language(self, language):
            self.targets.append(language)

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
            self.writes = 0

        def write(self, payload):
            assert payload
            self.writes += 1
            if self.writes == 1:
                result = SimpleNamespace(
                    result_id="fake-1",
                    text="作戦を",
                    translations={"id": "Operasi"},
                    offset=0,
                    duration=500000,
                    reason=None,
                )
                self.sdk.recognizer.recognizing.emit(SimpleNamespace(result=result))
            elif self.writes == 3:
                result = SimpleNamespace(
                    result_id="fake-1",
                    text="作戦を開始する",
                    translations={"id": "Mulai operasinya."},
                    offset=0,
                    duration=1500000,
                    reason=self.sdk.ResultReason.TranslatedSpeech,
                )
                self.sdk.recognizer.recognized.emit(SimpleNamespace(result=result))

        def close(self):
            return None

    class FakeSdk:
        class ResultReason:
            TranslatedSpeech = "translated"
            NoMatch = "no_match"

        class PropertyId:
            SpeechServiceResponse_StablePartialResultThreshold = "stable"
            Speech_SegmentationSilenceTimeoutMs = "silence"
            SpeechServiceConnection_InitialSilenceTimeoutMs = "initial"

        class PhraseListGrammar:
            @staticmethod
            def from_recognizer(_recognizer):
                return SimpleNamespace(addPhrase=lambda _phrase: None)

        def __init__(self):
            self.translation = SimpleNamespace(
                SpeechTranslationConfig=TranslationConfig,
                TranslationRecognizer=self._recognizer_factory,
            )
            self.audio = SimpleNamespace(
                AudioStreamFormat=lambda **_kwargs: object(),
                PushAudioInputStream=self._stream_factory,
                AudioConfig=lambda **_kwargs: object(),
            )
            self.recognizer = None
            self.stream = None

        def _stream_factory(self, **_kwargs):
            self.stream = PushStream(self)
            return self.stream

        def _recognizer_factory(self, **_kwargs):
            self.recognizer = FakeRecognizer(self)
            return self.recognizer

    original_sdk = audio_cloud_sidecar._speech_sdk
    original_key = audio_cloud_sidecar._credential_key
    original_region = audio_cloud_sidecar._credential_region
    fake_sdk = FakeSdk()
    audio_cloud_sidecar._speech_sdk = lambda: fake_sdk
    audio_cloud_sidecar._credential_key = lambda: "secret-not-logged"
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
                output.writeframes(np.full(6400, 700, dtype="<i2").tobytes())
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
            assert_true(code == 0, f"fake Azure stream failed: {output.getvalue()}")
            assert_true(any(item.get("type") == "interim" for item in events), "fake SDK emitted no interim")
            assert_true(any(item.get("type") == "final" for item in events), "fake SDK emitted no final")
            assert_true("secret-not-logged" not in output.getvalue(), "subscription key leaked into cloud events")
    finally:
        audio_cloud_sidecar._speech_sdk = original_sdk
        audio_cloud_sidecar._credential_key = original_key
        audio_cloud_sidecar._credential_region = original_region
        audio_cloud_sidecar.STOP_REQUESTED = False


def test_backend_resolution_without_credentials_in_process_env() -> None:
    original = audio_cloud_backend.probe_cloud_runtime
    audio_cloud_backend.probe_cloud_runtime = lambda *_args, **_kwargs: {
        "ready": True,
        "dependency_ready": True,
        "credential_set": True,
        "region": "southeastasia",
        "wasapi": True,
    }
    try:
        decision = audio_cloud_backend.resolve_audio_delivery("azure_fallback", True, ROOT, True)
        assert_true(decision["ready"] and decision["effective"] == "azure", "backend did not select Azure")
        assert_true(decision["cloud"].get("credential_set"), "credential presence was not represented as a boolean")
    finally:
        audio_cloud_backend.probe_cloud_runtime = original
        audio_cloud_backend.clear_cloud_probe_cache()


def test_secure_full_stack_wiring() -> None:
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    parent = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    sidecar = (ROOT / "audio_cloud_sidecar.py").read_text(encoding="utf-8")
    backend = (ROOT / "audio_cloud_backend.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements_audio_cloud.txt").read_text(encoding="utf-8")

    for marker in (
        'label="Jenis penggunaan"',
        '("Live Media · Rekomendasi", "live_media")',
        'label="Mesin Audio"',
        '("Azure Cloud · Real-time", "azure")',
        '("Azure + Local Fallback · Rekomendasi", "azure_fallback")',
        'type="password"',
        "Simpan & Uji Azure",
    ):
        assert_true(marker in webui, f"WebUI cloud marker missing: {marker}")
    for marker in (
        'env["ORT_AUDIO_ENGINE_REQUESTED"]',
        'env["ORT_AUDIO_ENGINE_EFFECTIVE"]',
        'env["ORT_AUDIO_USAGE"]',
        'env["ORT_AUDIO_CLOUD_PYTHON"]',
        'env["ORT_AUDIO_LOCAL_FALLBACK_READY"]',
    ):
        assert_true(marker in launcher, f"launcher cloud wiring missing: {marker}")
    for marker in (
        "class CloudBridge",
        "LiveSubtitleStabilizer",
        "set_cloud_translation",
        "AUDIO_CLOUD_INTERIM_DISPLAYED",
        "CLOUD_LOCAL_FAILOVER",
        "quality_reject_overlay_visible=False",
        'runtime_asr_model = "azure_speech_translation"',
        'asr_device="cloud"',
    ):
        assert_true(marker in parent, f"parent cloud marker missing: {marker}")
    assert_true("TranslationRecognizer" in sidecar and "recognizing.connect" in sidecar, "Azure interim callback is missing")
    assert_true("PushAudioInputStream" in sidecar and "TARGET_SAMPLE_RATE = 16000" in sidecar, "PCM streaming contract is missing")
    assert_true("keyring.set_password" not in sidecar, "credential implementation bypassed the keyring module boundary")
    assert_true(".set_password(CREDENTIAL_SERVICE" in sidecar, "Windows Credential Manager storage is missing")
    assert_true('env["ORT_AZURE_SPEECH_KEY"]' not in launcher and '"--api-key"' not in launcher, "API key entered the launcher command/environment path")
    assert_true("asr={active_asr_model}:{active_asr_device}:{active_compute}" in launcher, "Azure log can misreport the local fallback as active ASR")
    assert_true("input_text=payload" in backend, "credential payload is not passed through private stdin")
    assert_true("azure-cognitiveservices-speech" in requirements and "keyring" in requirements, "cloud dependencies are incomplete")
    assert_true("Audio ditolak oleh quality gate" not in parent, "quality rejection still replaces the overlay")


def main() -> None:
    test_release_identity()
    test_engine_resolution()
    test_interim_final_stabilization()
    test_fallback_latch_and_replay()
    test_sidecar_simulation_timing()
    test_fake_azure_stream_callbacks()
    test_backend_resolution_without_credentials_in_process_env()
    test_secure_full_stack_wiring()
    print(f"{APP_VERSION_TAG} Cloud Live Media Streaming regression PASS")


if __name__ == "__main__":
    main()
