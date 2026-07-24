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
import audio_realtime_local_sidecar as realtime_sidecar
from audio_realtime_local_sidecar import (
    LanguageWatchdog,
    ModelAdapter,
    _asr_quality_reasons,
)
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


def make_adapter(language, requested="auto", specialist=False) -> ModelAdapter:
    return ModelAdapter(
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
        japanese_specialist=specialist,
        language_correction_mode="off",
        language_locked=False,
    )


def test_release_contract() -> None:
    assert_true(APP_VERSION_TAG == "v8.9.9", APP_VERSION_TAG)
    assert_true(RELEASE_NAME == "Safe Language Auto-Correct and Japanese Reliability Update", RELEASE_NAME)
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

    japanese = make_adapter("ja", "ja")
    japanese.model = CapturingModel("ja", "translated Japanese speech")
    _, ja_meta = japanese.transcribe(audio)
    ja_call = japanese.model.calls[-1]
    assert_true(ja_call["language"] == "ja" and ja_call["task"] == "translate", ja_call)

    specialist = make_adapter("ja", "ja_specialist", specialist=True)
    specialist.specialist_active = True
    specialist.model_size = "kotoba-bilingual"
    specialist.model = CapturingModel("en", "specialist bridge")
    _, specialist_meta = specialist.transcribe(audio)
    specialist_call = specialist.model.calls[-1]
    assert_true(specialist_call["language"] == "en" and specialist_call["task"] == "translate", specialist_call)
    assert_true(specialist_meta["japanese_specialist"] is True, specialist_meta)

    return {
        "english": {"language": en_call["language"], "task": en_call["task"]},
        "japanese": {"language": ja_call["language"], "task": ja_call["task"]},
        "specialist": {"language": specialist_call["language"], "task": specialist_call["task"]},
    }


def test_specialist_model_preserving_failover() -> dict:
    class DummyModel:
        def transcribe(self, *_args, **_kwargs):
            return [Segment("Japanese specialist bridge")], Info("en", 1.0)

    class DeterministicAdapter(ModelAdapter):
        def _model_location(self, size: str) -> str:
            return f"/fake/{size}"

        def _construct_model(self, size: str, device: str, compute_type: str):
            return DummyModel(), f"/fake/{size}"

        def _cuda_preflight(self, model, specialist: bool, source_language):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    adapter = DeterministicAdapter(
        model_root=ROOT,
        model_size="small",
        fallback_model_size="base",
        device="cuda",
        compute_type="int8_float16",
        cpu_threads=4,
        language="ja",
        allow_cpu_fallback=True,
        game="GFL2_EXILIUM",
        requested_language="ja_specialist",
        japanese_specialist=True,
        language_correction_mode="off",
        language_locked=False,
    )
    adapter.load()
    assert_true(adapter.device == "cpu", adapter.device)
    assert_true(adapter.model_size == "kotoba-bilingual", adapter.model_size)
    assert_true(adapter.specialist_active, "specialist flag lost")
    text, meta = adapter.transcribe(np.ones(16000, dtype=np.float32) * 0.01)
    assert_true(text == "Japanese specialist bridge", text)
    assert_true(meta["japanese_specialist"] is True, meta)
    return {"device": adapter.device, "model": adapter.model_size, "specialist": adapter.specialist_active}


def test_language_watchdog() -> dict:
    watchdog = LanguageWatchdog(ROOT, "en", "balanced", False, 2)
    decisions = [watchdog.record_detection("ja", 0.92, 100.0 + index * 2.0, "en") for index in range(4)]
    assert_true(not any(item.global_language for item in decisions[:3]), decisions)
    assert_true(decisions[-1].global_language == "ja", decisions[-1])

    locked = LanguageWatchdog(ROOT, "ja", "balanced", True, 2)
    short = locked.record_detection("en", 0.95, 200.0, "ja")
    assert_true(short.state == "TEMPORARY_CODE_SWITCH", short)
    assert_true(not short.global_language and short.segment_language == "en", short)
    for index in range(1, 8):
        final = locked.record_detection("en", 0.96, 200.0 + index * 2.0, "ja")
    assert_true(not final.global_language, final)
    return {
        "balanced_switch_after_confirmations": decisions[-1].global_language,
        "locked_code_switch": short.state,
    }


def test_repetition_guard() -> dict:
    repeated_ja = "チーズ " * 50
    repeated_en = "I'm not a good player. " * 25
    ja_reasons = _asr_quality_reasons(repeated_ja, 4.0, "translate")
    en_reasons = _asr_quality_reasons(repeated_en, 5.0, "translate")
    clean_reasons = _asr_quality_reasons("I will check the location and report back.", 3.0, "translate")
    assert_true("REPEAT_TOKEN_LOOP" in ja_reasons and "BRIDGE_NOT_ENGLISH" in ja_reasons, ja_reasons)
    assert_true(any(item.startswith("REPEAT") for item in en_reasons), en_reasons)
    assert_true(not clean_reasons, clean_reasons)
    return {"japanese": ja_reasons, "english": en_reasons}


def test_full_stack_wiring() -> None:
    parent = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    sidecar = (ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8")

    for marker in (
        "rolling-partial-v2",
        "ORT_AUDIO_LANGUAGE_AUTOCORRECT",
        "ORT_AUDIO_LANGUAGE_LOCK",
        "preserve_model",
        "JAPANESE_SPECIALIST_CPU_ACTIVE",
    ):
        assert_true(marker in parent + launcher + sidecar, f"marker missing: {marker}")
    for marker in ("Auto-Correct bahasa", "Conservative · 12 detik", "Balanced · 8 detik", "Kunci bahasa utama"):
        assert_true(marker in webui, f"webui marker missing: {marker}")
    for marker in ("REPEAT_TOKEN_LOOP", "BRIDGE_NOT_ENGLISH", "TEMPORARY_CODE_SWITCH", "LANGUAGE_SWITCH_CONFIRMED"):
        assert_true(marker in sidecar, f"sidecar marker missing: {marker}")
    for path in (
        ROOT / "tools" / "install_japanese_specialist_v8_9_9.py",
        ROOT / "tools" / "check_audio_gpu_v8_9_9.py",
        PROJECT_ROOT / "INSTALL_JAPANESE_SPECIALIST.bat",
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
    realtime_sidecar._EVENT_SINK = []
    test_release_contract()
    realtime = test_continuous_speech_self_test()
    routing = test_language_routing()
    failover = test_specialist_model_preserving_failover()
    watchdog = test_language_watchdog()
    repetition = test_repetition_guard()
    test_full_stack_wiring()
    test_engine_resolution()
    payload = {
        "status": "PASS",
        "version": APP_VERSION_TAG,
        "first_partial_audio_ms": realtime["first_partial_audio_ms"],
        "translation_updates_before_final": realtime["translation_updates_before_final"],
        "pause_required": realtime["pause_required_for_first_translation"],
        "language_routing": routing,
        "specialist_failover": failover,
        "language_watchdog": watchdog,
        "repetition_guard": repetition,
    }
    realtime_sidecar._EVENT_SINK = None
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
