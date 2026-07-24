#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.cloud_streaming import resolve_cloud_engine
from build_info import APP_VERSION_TAG, RELEASE_NAME
from audio_realtime_local_sidecar import ModelAdapter


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_contract() -> None:
    assert_true(APP_VERSION_TAG == "v8.9.7", f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME == "Continuous Rolling-Partial Translation Update", RELEASE_NAME)
    for path in (PROJECT_ROOT / "VERSION.txt", ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8-sig").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_continuous_speech_self_test() -> dict:
    sidecar = ROOT / "audio_realtime_local_sidecar.py"
    result = subprocess.run(
        [sys.executable, str(sidecar), "--self-test-json"],
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
    assert_true(int(payload.get("final_count", 0)) >= 1, payload)
    trace = payload.get("display_trace") or []
    assert_true(trace and trace[0].get("stable") is False, trace)
    assert_true(trace[-1].get("stable") is True, trace)
    return payload



def test_hybrid_cuda_failure_stays_realtime() -> None:
    class FailingCudaModel:
        def transcribe(self, *_args, **_kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    class Segment:
        text = "subtitle tetap berjalan"

    class Info:
        language = "id"
        language_probability = 1.0

    class CpuModel:
        def transcribe(self, *_args, **_kwargs):
            return [Segment()], Info()

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
    text, metadata = adapter.transcribe(np.ones(16000, dtype=np.float32) * 0.01)
    assert_true(text == "subtitle tetap berjalan", (text, metadata))
    assert_true(adapter.device == "cpu", adapter.device)
    assert_true(adapter.model_size == "base", adapter.model_size)


def test_full_stack_wiring() -> None:
    parent = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    for marker in (
        "class RealtimeLocalBridge",
        "audio_realtime_local_sidecar.py",
        "_start_local_realtime_pipeline",
        'event_type in {"partial_transcript", "transcript"}',
        "LOCAL_REALTIME_INTERIM",
        "Local Live · {'final' if stable else 'live'}",
    ):
        assert_true(marker in parent, f"audio_main marker missing: {marker}")
    for marker in (
        "runtime_version_contract",
        "INSTALASI ORT TERCAMPUR DAN AUDIO DIBLOKIR",
        "audio_local_realtime_rolling_partial",
        "faster-whisper rolling-partial",
        "network_test=probe_realtime_cloud",
    ):
        assert_true(marker in launcher, f"launcher marker missing: {marker}")
    for marker in (
        "Local Live · Rolling partial/offline",
        "Azure + Local Live Fallback",
        "jeda hanya mengunci final",
    ):
        assert_true(marker in webui, f"webui marker missing: {marker}")


def test_engine_resolution() -> None:
    local = resolve_cloud_engine("local", cloud_ready=False, local_ready=True)
    assert_true(local.effective == "local_live" and local.ready, local)
    fallback = resolve_cloud_engine("azure_fallback", cloud_ready=False, local_ready=True)
    assert_true(fallback.effective == "local_live" and fallback.ready, fallback)
    cloud = resolve_cloud_engine("azure_fallback", cloud_ready=True, local_ready=True)
    assert_true(cloud.effective == "azure" and cloud.ready, cloud)


def main() -> int:
    test_release_contract()
    payload = test_continuous_speech_self_test()
    test_hybrid_cuda_failure_stays_realtime()
    test_full_stack_wiring()
    test_engine_resolution()
    print(json.dumps({
        "status": "PASS",
        "version": APP_VERSION_TAG,
        "continuous_speech_seconds": payload["continuous_speech_seconds"],
        "first_partial_audio_ms": payload["first_partial_audio_ms"],
        "translation_updates_before_final": payload["translation_updates_before_final"],
        "pause_required": payload["pause_required_for_first_translation"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
