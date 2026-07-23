from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_hybrid_baseline_contract() -> None:
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    assert_true("_validated_cuda_baseline_ready" in launcher, "baseline helper missing")
    assert_true("HYBRID_CUDA_BASELINE_READY_ACTIVE_MODEL_PREFLIGHT" in launcher, "hybrid promotion missing")
    assert_true("japanese_gpu_candidate" in launcher, "promotion must remain Japanese-scoped")
    assert_true('effective_audio_mode in {"gpu", "hybrid"}' in launcher, "GPU capture runtime selection missing")


def test_semantic_and_partial_stability() -> None:
    sidecar = load_module("ort_v899_r2_f1_sidecar", ROOT / "audio_realtime_local_sidecar.py")
    assert_true(not sidecar._has_semantic_text("."), "punctuation must be suppressed")
    assert_true(sidecar._has_semantic_text("now"), "short meaningful English must pass")
    assert_true(sidecar._has_semantic_text("今"), "short meaningful Japanese must pass")

    class Model:
        profile = "normal"
        specialist_correction_enabled = False

    worker = sidecar.StreamingInferenceWorker(Model())
    now = 100.0
    assert_true(worker._should_emit_partial("s1", "", "now", now), "first partial must pass")
    worker.last_emit_at_by_result["s1"] = now
    assert_true(not worker._should_emit_partial("s1", "to worry", "to refrain", now + 0.10), "minor interval rewrite should coalesce")
    assert_true(worker._should_emit_partial("s1", "to worry", "to worry about this", now + 0.12), "clear prefix growth should pass")
    assert_true(worker._should_emit_partial("s1", "to worry", "to refrain", now + 0.50), "meaningful rewrite must not be held too long")


def test_reject_throttle() -> None:
    sidecar = sys.modules["ort_v899_r2_f1_sidecar"]
    events: list[dict] = []
    sidecar._EVENT_SINK = events

    class Model:
        profile = "normal"
        specialist_correction_enabled = False

    worker = sidecar.StreamingInferenceWorker(Model())
    snapshot = sidecar.Snapshot("s2", 1, np.ones(1600, dtype=np.float32), False, time.monotonic(), 0.1)
    metadata = {"quality_reject_reasons": ["EMPTY", "NO_SPEECH"], "asr_ms": 20}
    worker._emit_reject_throttled(snapshot, metadata)
    worker._emit_reject_throttled(snapshot, metadata)
    rejects = [item for item in events if item.get("type") == "quality_reject"]
    assert_true(len(rejects) == 1, rejects)


def test_overlay_guard_contract() -> None:
    main_source = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    assert_true("nonsemantic partial suppressed" in main_source, "ASR punctuation guard missing")
    assert_true("guarded translation kept off overlay" in main_source, "guard diagnostic overlay protection missing")
    build = (ROOT / "build_info.py").read_text(encoding="utf-8")
    assert_true("v8-9-9-r2-f1-hybrid-subtitle-continuity" in build, "release channel missing")


def main() -> int:
    test_hybrid_baseline_contract()
    test_semantic_and_partial_stability()
    test_reject_throttle()
    test_overlay_guard_contract()
    print("ORT v8.9.9 R2 F1 Hybrid/subtitle continuity regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
