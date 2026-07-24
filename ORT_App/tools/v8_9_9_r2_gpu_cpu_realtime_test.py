from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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


def test_profile_contract() -> None:
    from app.audio.profiles import get_audio_profile

    normal = get_audio_profile("normal")
    assert_true(normal.model_size == "base", normal)
    assert_true(normal.gpu_model_size == "small", normal)
    assert_true(normal.hybrid_fallback_model_size == "base", normal)
    assert_true(normal.beam_size == 1 and normal.best_of == 1, normal)
    assert_true(normal.max_speech_seconds <= 6.5, normal)


def test_cuda_directory_discovery() -> None:
    from app.audio.cuda_bootstrap import discover_cuda_dll_directories

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        previous = os.environ.get("ORT_AUDIO_CUDA_DLL_DIRS")
        os.environ["ORT_AUDIO_CUDA_DLL_DIRS"] = str(path)
        try:
            result = discover_cuda_dll_directories()
            assert_true(path.resolve() in result, result)
        finally:
            if previous is None:
                os.environ.pop("ORT_AUDIO_CUDA_DLL_DIRS", None)
            else:
                os.environ["ORT_AUDIO_CUDA_DLL_DIRS"] = previous


def test_realtime_window_and_retry_policy() -> None:
    sidecar = load_module("ort_v899_r2_sidecar", ROOT / "audio_realtime_local_sidecar.py")
    sidecar._EVENT_SINK = []

    class Segment:
        text = "This sentence remains suitable for realtime translation."

    class Info:
        language = "en"
        language_probability = 0.99

    class CapturingModel:
        def __init__(self):
            self.lengths: list[int] = []

        def transcribe(self, audio, **_kwargs):
            self.lengths.append(len(audio))
            return [Segment()], Info()

    adapter = sidecar.ModelAdapter(
        model_root=ROOT,
        model_size="base",
        fallback_model_size="base",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        language="en",
        allow_cpu_fallback=False,
        game="GFL2_EXILIUM",
        requested_language="en",
        japanese_specialist=False,
        language_correction_mode="off",
        language_locked=False,
        profile="normal",
    )
    model = CapturingModel()
    adapter.model = model
    adapter.transcribe(np.ones(sidecar.TARGET_SAMPLE_RATE * 8, dtype=np.float32) * 0.01, stable=False)
    assert_true(len(model.lengths) == 1, model.lengths)
    assert_true(model.lengths[-1] <= int(sidecar.TARGET_SAMPLE_RATE * 3.2), model.lengths[-1])
    adapter.transcribe(np.ones(sidecar.TARGET_SAMPLE_RATE * 8, dtype=np.float32) * 0.01, stable=True)
    assert_true(len(model.lengths) == 2, model.lengths)
    assert_true(model.lengths[-1] <= int(sidecar.TARGET_SAMPLE_RATE * 6.0), model.lengths[-1])


def test_final_backpressure() -> None:
    sidecar = sys.modules["ort_v899_r2_sidecar"]
    events: list[dict] = []
    sidecar._EVENT_SINK = events
    mailbox = sidecar.LatestSnapshotMailbox(max_finals=2)
    samples = np.ones(1600, dtype=np.float32)
    for index in range(4):
        mailbox.put(sidecar.Snapshot(f"s{index}", 1, samples, True, time.monotonic(), 0.1))
    first = mailbox.get(0.1)
    second = mailbox.get(0.1)
    assert_true(first.result_id == "s2" and second.result_id == "s3", (first.result_id, second.result_id))
    assert_true(sum(item.get("name") == "realtime_final_backpressure_drop" for item in events) == 2, events)


def test_gpu_wiring() -> None:
    sidecar = (ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8")
    installer = (ROOT / "tools" / "install_audio_gpu_v8_9_9_r2.py").read_text(encoding="utf-8")
    checker = (ROOT / "tools" / "check_audio_gpu_v8_9_9.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements_audio_gpu.txt").read_text(encoding="utf-8")
    build = (ROOT / "build_info.py").read_text(encoding="utf-8")
    for marker in ("activate_cuda_dll_search", "CUDA_PREFLIGHT_PASSED", "warmup_ms", "steady_ms"):
        assert_true(marker in sidecar, marker)
    for marker in ("validated_cuda_", "real_gpu_inference_passed", "sitecustomize.py"):
        assert_true(marker in installer, marker)
    for package in ("nvidia-cublas-cu12", "nvidia-cudnn-cu12", "nvidia-cuda-runtime-cu12", "nvidia-cuda-nvrtc-cu12"):
        assert_true(package in requirements, package)
    assert_true("_validate_gpu" in checker, "checker does not run real inference")
    assert_true("v8-9-9-r2-gpu-runtime-normal-realtime" in build, "R2 release channel missing")
    assert_true((PROJECT_ROOT / "INSTALL_AUDIO_GPU_V8_9_9_R2.bat").is_file(), "GPU installer BAT missing")


def main() -> int:
    test_profile_contract()
    test_cuda_directory_discovery()
    test_realtime_window_and_retry_policy()
    test_final_backpressure()
    test_gpu_wiring()
    print("ORT v8.9.9 R2 GPU/CPU realtime regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
