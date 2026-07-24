#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace
import io
import json
import sys
import tempfile

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.glossary import apply_audio_glossary
from app.audio.profiles import get_audio_profile
from app.audio.quality_gate import assess_asr_quality
from app.audio.runtime_modes import HybridFailoverController, resolve_audio_plan
from app.audio.segment_ledger import SegmentLedger, SegmentTask
from audio_translation_sidecar import split_audio_clauses
from audio_asr_sidecar import run_worker
from build_info import APP_VERSION_TAG, RELEASE_NAME
import audio_runtime_backend


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")
    for path in (ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt", ROOT.parents[1] / "VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_mode_contracts() -> None:
    cpu_speed = resolve_audio_plan("cpu", "speed")
    cpu_normal = resolve_audio_plan("cpu", "normal")
    gpu_normal = resolve_audio_plan("gpu", "normal")
    gpu_accurate = resolve_audio_plan("gpu", "accurate")
    hybrid_normal = resolve_audio_plan("hybrid", "normal")
    hybrid_accurate = resolve_audio_plan("hybrid", "accurate")
    assert_true((cpu_speed.primary.model_size, cpu_normal.primary.model_size) == ("base", "small"), "CPU model mapping changed")
    assert_true(cpu_normal.primary.device == "cpu" and cpu_normal.primary.compute_type == "int8", "CPU mode touches a non-CPU ASR path")
    assert_true(gpu_normal.primary.model_size == "small" and gpu_accurate.primary.model_size == "medium", "GPU model mapping changed")
    assert_true(gpu_normal.primary.device == "cuda" and gpu_normal.primary.compute_type == "int8_float16", "GPU compute contract changed")
    assert_true(gpu_normal.fallback is None, "strict GPU mode gained a silent CPU fallback")
    assert_true(hybrid_normal.fallback and hybrid_normal.fallback.model_size == "base", "Hybrid Normal fallback changed")
    assert_true(hybrid_accurate.fallback and hybrid_accurate.fallback.model_size == "small", "Hybrid Accurate fallback changed")


def test_cpu_probe_does_not_touch_cuda() -> None:
    calls = []
    original = audio_runtime_backend._probe_python

    def fake_probe(python_path, device, paths):
        calls.append(device)
        return {
            "ready": True,
            "installed": True,
            "file_test": True,
            "live_loopback": True,
            "requested_device": device,
            "python": str(python_path),
        }

    audio_runtime_backend._probe_python = fake_probe
    try:
        with tempfile.TemporaryDirectory() as tmp:
            result = audio_runtime_backend.probe_audio_runtime(True, Path(tmp), "cpu")
            assert_true(result.get("ready") and result.get("effective_mode") == "cpu", "CPU probe did not resolve to CPU")
            assert_true(calls == ["cpu"], f"CPU mode probed CUDA: {calls}")
    finally:
        audio_runtime_backend._probe_python = original
        audio_runtime_backend._clear_probe_cache()


def test_gpu_model_requires_load_validation() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        runtime = root / "runtime"
        (root / "runtime_paths.json").write_text(json.dumps({"runtime_root": str(runtime)}), encoding="utf-8")
        paths = audio_runtime_backend.audio_runtime_paths(root)
        spec = resolve_audio_plan("gpu", "normal").primary
        assert_true(
            not audio_runtime_backend._gpu_model_validated(paths, spec),
            "GPU model was trusted without a successful CUDA construction",
        )
        audio_runtime_backend._record_gpu_validation(paths, spec, True, "simulated CUDA construction")
        assert_true(audio_runtime_backend._gpu_model_validated(paths, spec), "GPU validation marker was not accepted")
        medium = resolve_audio_plan("gpu", "accurate").primary
        assert_true(
            not audio_runtime_backend._gpu_model_validated(paths, medium),
            "small-model validation incorrectly unlocked medium",
        )


def test_effective_mode_uses_gpu_load_evidence() -> None:
    original_probe = audio_runtime_backend.probe_audio_runtime
    original_models = audio_runtime_backend.audio_model_status
    audio_runtime_backend.probe_audio_runtime = lambda **_kwargs: {
        "ready": True,
        "cpu": {"ready": True},
        "gpu": {"ready": True, "vram_free_mb": 5000},
    }
    audio_runtime_backend.audio_model_status = lambda *_args, **_kwargs: {
        "primary_ready": True,
        "fallback_ready": True,
        "primary": {"ready": True},
        "fallback": {"ready": True},
    }
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime_paths.json").write_text(
                json.dumps({"runtime_root": str(root / "runtime")}), encoding="utf-8"
            )
            strict = audio_runtime_backend.resolve_effective_audio_mode("gpu", "normal", root, True)
            assert_true(not strict["ready"] and strict["reason"] == "GPU_MODEL_NOT_VALIDATED", "strict GPU ignored missing load evidence")
            guarded = audio_runtime_backend.resolve_effective_audio_mode("hybrid", "normal", root, True)
            assert_true(guarded["ready"] and guarded["effective_mode"] == "cpu_guard", "Hybrid did not guard on CPU")
            paths = audio_runtime_backend.audio_runtime_paths(root)
            audio_runtime_backend._record_gpu_validation(paths, resolve_audio_plan("gpu", "normal").primary, True)
            strict = audio_runtime_backend.resolve_effective_audio_mode("gpu", "normal", root, True)
            assert_true(strict["ready"] and strict["effective_mode"] == "gpu", "validated GPU did not unlock strict mode")
    finally:
        audio_runtime_backend.probe_audio_runtime = original_probe
        audio_runtime_backend.audio_model_status = original_models


def test_failover_and_segment_replay() -> None:
    ledger = SegmentLedger(max_pending=2)
    task = SegmentTask("seg-14", "segment.npy", "npy", 3.2, 1.0)
    ledger.submit(task)
    inflight = ledger.dispatch_next()
    assert_true(inflight and inflight.segment_id == "seg-14", "segment was not dispatched")
    replay = ledger.requeue_inflight()
    replay_again = ledger.dispatch_next()
    assert_true(replay and replay_again and replay.segment_id == replay_again.segment_id == "seg-14", "replay changed segment identity")

    hybrid = HybridFailoverController.create("hybrid", "hybrid")
    decision = hybrid.worker_failure("cuda", "CUDA_OUT_OF_MEMORY")
    assert_true(
        decision["action"] == "fallback_cpu"
        and decision["replay_inflight"]
        and decision["retry_gpu_after_replay"]
        and not decision["circuit_open"],
        "first Hybrid failure did not schedule CPU replay and one GPU retry",
    )
    second = hybrid.worker_failure("cuda", "CUDA_OUT_OF_MEMORY")
    assert_true(second["action"] == "fallback_cpu" and second["circuit_open"] and not second["retry_gpu_after_replay"], "second GPU failure did not open the circuit")
    strict_gpu = HybridFailoverController.create("gpu", "gpu")
    strict_decision = strict_gpu.worker_failure("cuda", "CUDA_OUT_OF_MEMORY")
    assert_true(strict_decision["action"] == "stop" and not strict_decision["replay_inflight"], "GPU mode silently fell back")


def test_japanese_quality_gate() -> None:
    good = assess_asr_quality(
        "We will return to the base after this mission.",
        audio_seconds=3.8,
        avg_logprob=-0.35,
        no_speech_prob=0.08,
        compression_ratio=1.2,
        language_probability=0.96,
        detected_language="ja",
        expected_language="ja",
    )
    assert_true(good.accepted, f"valid dialogue rejected: {good}")
    hallucination = assess_asr_quality(
        "Please subscribe to my channel.",
        audio_seconds=2.0,
        avg_logprob=-0.2,
        no_speech_prob=0.1,
        compression_ratio=1.0,
        language_probability=0.9,
        detected_language="ja",
        expected_language="ja",
    )
    assert_true(not hallucination.accepted and "HALLUCINATION_PHRASE" in hallucination.reasons, "known hallucination passed")
    repeated = assess_asr_quality(
        "I was the only one I was the only one I was the only one I was the only one",
        audio_seconds=2.1,
        avg_logprob=-0.6,
        no_speech_prob=0.1,
        compression_ratio=2.0,
        language_probability=0.8,
        detected_language="ja",
        expected_language="ja",
    )
    assert_true(not repeated.accepted and "REPETITION" in repeated.reasons, "repetition hallucination passed")


def test_persistent_asr_worker_protocol() -> None:
    calls = []

    class FakeModel:
        def transcribe(self, source, **kwargs):
            calls.append(kwargs)
            row = SimpleNamespace(
                text="We will return to the base.",
                start=0.0,
                end=2.4,
                avg_logprob=-0.2,
                no_speech_prob=0.05,
                compression_ratio=1.1,
            )
            return [row], SimpleNamespace(language="ja", language_probability=0.95)

    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "segment.npy"
        np.save(path, np.full(16000 * 2, 0.02, dtype=np.float32), allow_pickle=False)
        request = {
            "type": "transcribe",
            "segment_id": "seg-protocol",
            "path": str(path),
            "kind": "npy",
            "audio_seconds": 2.0,
        }
        old_stdin = sys.stdin
        output = io.StringIO()
        sys.stdin = io.StringIO(json.dumps(request) + "\n" + '{"type":"shutdown"}\n')
        try:
            with redirect_stdout(output):
                code = run_worker(
                    FakeModel(),
                    profile=get_audio_profile("normal"),
                    processing="vad",
                    language="ja",
                    model_size="small",
                    device="cuda",
                    compute_type="int8_float16",
                )
        finally:
            sys.stdin = old_stdin
        events = audio_runtime_backend.parse_sidecar_events(output.getvalue())
        assert_true(code == 0, f"persistent ASR worker failed: {code}")
        assert_true(any(item.get("type") == "transcript" and item.get("segment_id") == "seg-protocol" for item in events), "worker emitted no transcript")
        assert_true(any(item.get("type") == "segment_complete" for item in events), "worker did not acknowledge segment")
        assert_true(calls and calls[0].get("task") == "translate" and calls[0].get("vad_filter"), "Japanese translate/VAD options were not applied")


def test_glossary_and_clause_preservation() -> None:
    corrected, hits = apply_audio_glossary("Growza and Colfney are ready.", "GFL2_EXILIUM")
    assert_true(corrected == "Groza and Colphne are ready." and len(hits) == 2, f"GFL2 audio glossary failed: {corrected}")
    clauses = split_audio_clauses("I'm grateful for that. If that's the case, I'll return soon.")
    assert_true(len(clauses) == 2, f"audio clauses were merged: {clauses}")


def test_full_stack_wiring() -> None:
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    parent = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    worker = (ROOT / "audio_asr_sidecar.py").read_text(encoding="utf-8")
    backend = (ROOT / "audio_runtime_backend.py").read_text(encoding="utf-8")
    for marker in (
        'label="Perangkat ASR lokal / fallback"',
        '("CPU · Kompatibel", "cpu")',
        '("GPU · ASR CUDA ketat", "gpu")',
        '("Hybrid · Rekomendasi", "hybrid")',
    ):
        assert_true(marker in webui, f"WebUI mode marker missing: {marker}")
    for marker in (
        'env["ORT_AUDIO_REQUESTED_MODE"]',
        'env["ORT_AUDIO_EFFECTIVE_MODE"]',
        'env["ORT_AUDIO_CPU_PYTHON"]',
        'env["ORT_AUDIO_GPU_PYTHON"]',
        "requested_mode={requested_audio_mode} | effective_mode={effective_audio_mode}",
    ):
        assert_true(marker in launcher, f"launcher wiring missing: {marker}")
    assert_true("class CaptureBridge" in parent and "class ASRCoordinator" in parent, "capture and ASR are not process-separated")
    assert_true("HYBRID_FAILOVER" in parent and "replay_segment_id" in parent, "Hybrid replay telemetry missing")
    assert_true("HYBRID_GPU_RETRY" in parent and "_planned_switch_device" in parent, "two-strike Hybrid circuit wiring missing")
    assert_true('"--worker-json"' in parent and '"--asr-device"' in parent, "persistent ASR worker protocol missing")
    assert_true("assess_asr_quality" in worker and 'task="translate"' in worker, "quality gate or Japanese-to-English ASR path missing")
    assert_true('runtime_root / "audio_cpu"' in backend and 'runtime_root / "audio_gpu"' in backend, "CPU/GPU runtimes are not separate")
    assert_true('"model_root": cpu_root / "models"' in backend, "R6 model cache is not reused")
    for path in (ROOT / "audio_capture_sidecar.py", ROOT / "requirements_audio_gpu.txt"):
        assert_true(path.is_file(), f"required tri-mode file missing: {path.name}")


def main() -> None:
    test_release_identity()
    test_mode_contracts()
    test_cpu_probe_does_not_touch_cuda()
    test_gpu_model_requires_load_validation()
    test_effective_mode_uses_gpu_load_evidence()
    test_failover_and_segment_replay()
    test_japanese_quality_gate()
    test_persistent_asr_worker_protocol()
    test_glossary_and_clause_preservation()
    test_full_stack_wiring()
    print(f"{APP_VERSION_TAG} Audio Tri-Mode regression PASS")


if __name__ == "__main__":
    main()
