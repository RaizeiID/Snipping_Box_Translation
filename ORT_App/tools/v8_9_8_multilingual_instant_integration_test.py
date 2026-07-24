#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.cloud_streaming import resolve_cloud_engine
from audio_realtime_local_sidecar import ModelAdapter
from build_info import APP_VERSION_TAG, RELEASE_NAME


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


class Segment:
    def __init__(self, text: str):
        self.text = text


class Info:
    def __init__(self, language: str, probability: float = 0.99):
        self.language = language
        self.language_probability = probability


class CapturingModel:
    def __init__(self, language: str, text: str = "bridge text"):
        self.language = language
        self.text = text
        self.calls: list[dict] = []

    def transcribe(self, _audio, **kwargs):
        self.calls.append(kwargs)
        return [Segment(self.text)], Info(self.language)


def make_adapter(language, requested="auto") -> ModelAdapter:
    adapter = ModelAdapter(
        model_root=ROOT,
        model_size="base",
        fallback_model_size="base",
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        language=language,
        allow_cpu_fallback=False,
        game="GFL2_EXILIUM",
        requested_language=requested,
        japanese_specialist=False,
    )
    return adapter


def test_release_contract() -> None:
    assert_true(APP_VERSION_TAG == "v8.9.8", APP_VERSION_TAG)
    assert_true(RELEASE_NAME == "Multilingual Instant Japanese Specialist Update", RELEASE_NAME)
    for path in (PROJECT_ROOT / "VERSION.txt", ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8-sig").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_continuous_speech_self_test() -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "audio_realtime_local_sidecar.py"), "--self-test-json"],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert_true(result.returncode == 0, result.stdout)
    payload = json.loads(result.stdout)
    assert_true(payload.get("passed"), payload)
    assert_true(payload.get("pause_required_for_first_translation") is False, payload)
    assert_true(int(payload.get("first_partial_audio_ms", 9999)) < 1000, payload)
    assert_true(int(payload.get("translation_updates_before_final", 0)) >= 3, payload)
    return payload


def test_language_routing() -> dict:
    audio = np.ones(16000, dtype=np.float32) * 0.01

    english = make_adapter("en", "en")
    english.model = CapturingModel("en", "hello")
    _, en_meta = english.transcribe(audio)
    en_call = english.model.calls[-1]
    assert_true(en_call["language"] == "en" and en_call["task"] == "transcribe", en_call)
    assert_true(en_meta["bridge_language"] == "en", en_meta)

    japanese = make_adapter("ja", "ja")
    japanese.model = CapturingModel("ja", "translated Japanese speech")
    _, ja_meta = japanese.transcribe(audio)
    ja_call = japanese.model.calls[-1]
    assert_true(ja_call["language"] == "ja" and ja_call["task"] == "translate", ja_call)
    assert_true(ja_meta["source_language"] == "ja" and ja_meta["bridge_language"] == "en", ja_meta)

    auto = make_adapter(None, "auto")
    auto.model = CapturingModel("ja", "auto Japanese bridge")
    _, auto_meta = auto.transcribe(audio)
    auto_call = auto.model.calls[-1]
    assert_true(auto_call["language"] is None and auto_call["task"] == "translate", auto_call)
    assert_true(auto.session_language == "ja", auto.session_language)
    assert_true(auto_meta["detected_language"] == "ja", auto_meta)

    specialist = make_adapter("ja", "ja_specialist")
    specialist.specialist_active = True
    specialist.model = CapturingModel("en", "specialist bridge")
    _, specialist_meta = specialist.transcribe(audio)
    specialist_call = specialist.model.calls[-1]
    assert_true(specialist_call["language"] == "en" and specialist_call["task"] == "translate", specialist_call)
    assert_true(specialist_meta["japanese_specialist"] is True, specialist_meta)

    return {
        "english": {"language": en_call["language"], "task": en_call["task"]},
        "japanese": {"language": ja_call["language"], "task": ja_call["task"]},
        "auto": {"language": auto_call["language"], "task": auto_call["task"], "locked": auto.session_language},
        "specialist": {"language": specialist_call["language"], "task": specialist_call["task"]},
    }


def test_cuda_failure_stays_realtime() -> None:
    class FailingCudaModel:
        def transcribe(self, *_args, **_kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    class CpuModel:
        def transcribe(self, *_args, **_kwargs):
            return [Segment("subtitle tetap berjalan")], Info("en", 1.0)

    class DeterministicAdapter(ModelAdapter):
        def _load(self, size: str, device: str, compute_type: str) -> None:
            self.model_size = size
            self.device = device
            self.compute_type = compute_type
            self.model = FailingCudaModel() if device == "cuda" else CpuModel()

    adapter = DeterministicAdapter(
        model_root=ROOT,
        model_size="small",
        fallback_model_size="base",
        device="cuda",
        compute_type="int8_float16",
        cpu_threads=4,
        language="en",
        allow_cpu_fallback=True,
        game="SPIDERMAN",
    )
    adapter.load()
    text, _ = adapter.transcribe(np.ones(16000, dtype=np.float32) * 0.01)
    assert_true(text == "subtitle tetap berjalan", text)
    assert_true(adapter.device == "cpu" and adapter.model_size == "base", (adapter.device, adapter.model_size))


def test_full_stack_wiring() -> None:
    parent = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    sidecar = (ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8")

    for marker in (
        "requested_language",
        "source_language",
        "bridge_language",
        "asr_task",
        "a completed translation is useful even when a newer ASR",
        "superseded translation ignored",
    ):
        assert_true(marker in parent, f"audio_main marker missing: {marker}")
    assert_true("stale translation blocked" not in parent, "old global translation starvation guard remains")

    for marker in (
        "GFL2_PERSISTED_EN_TO_SMART_AUTO",
        "ORT_AUDIO_LANGUAGE_REQUESTED",
        "ORT_AUDIO_JA_SPECIALIST",
        "ORT_AUDIO_ASR_BRIDGE_LANGUAGE",
    ):
        assert_true(marker in launcher, f"launcher marker missing: {marker}")

    for marker in ("Smart Auto", "Japanese Specialist", "Multilingual Bridge"):
        assert_true(marker in webui, f"webui marker missing: {marker}")

    for marker in ("LANGUAGE_LOCKED", "JAPANESE_SPECIALIST_ACTIVE", "task = \"translate\"", "bridge_language"):
        assert_true(marker in sidecar, f"sidecar marker missing: {marker}")

    for path in (
        ROOT / "tools" / "setup_japanese_specialist_v8_9_8.py",
        ROOT / "tools" / "check_audio_gpu_v8_9_8.py",
    ):
        assert_true(path.is_file(), f"missing tool: {path}")


def test_engine_resolution() -> None:
    local = resolve_cloud_engine("local", cloud_ready=False, local_ready=True)
    fallback = resolve_cloud_engine("azure_fallback", cloud_ready=False, local_ready=True)
    cloud = resolve_cloud_engine("azure_fallback", cloud_ready=True, local_ready=True)
    assert_true(local.effective == "local_live" and local.ready, local)
    assert_true(fallback.effective == "local_live" and fallback.ready, fallback)
    assert_true(cloud.effective == "azure" and cloud.ready, cloud)


def main() -> int:
    test_release_contract()
    realtime = test_continuous_speech_self_test()
    routing = test_language_routing()
    test_cuda_failure_stays_realtime()
    test_full_stack_wiring()
    test_engine_resolution()
    print(json.dumps({
        "status": "PASS",
        "version": APP_VERSION_TAG,
        "first_partial_audio_ms": realtime["first_partial_audio_ms"],
        "translation_updates_before_final": realtime["translation_updates_before_final"],
        "pause_required": realtime["pause_required_for_first_translation"],
        "language_routing": routing,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
