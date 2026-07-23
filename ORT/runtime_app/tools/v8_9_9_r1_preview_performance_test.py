from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    sidecar_path = ROOT / "audio_realtime_local_sidecar.py"
    audio_main_path = ROOT / "audio_main.py"
    build_info_path = ROOT / "build_info.py"
    launcher_path = ROOT / "launcher_backend.py"

    sidecar_source = sidecar_path.read_text(encoding="utf-8")
    audio_source = audio_main_path.read_text(encoding="utf-8")
    build_source = build_info_path.read_text(encoding="utf-8")
    launcher_source = launcher_path.read_text(encoding="utf-8")

    assert_true('ORT_AUDIO_SHOW_SOURCE", "1"' in audio_source, "preview source must default to visible")
    assert_true("Preview EN:" in audio_source, "English/source preview label missing")
    assert_true('ORT_AUDIO_SHOW_SOURCE"] = "1"' in launcher_source, "launcher still hides preview")
    assert_true("JAPANESE_DUAL_STREAM_ACTIVE" in sidecar_source, "dual stream state missing")
    assert_true("FAST_PREVIEW_MODEL_READY" in sidecar_source, "fast preview model state missing")
    assert_true("ORT_AUDIO_BACKGROUND_SPECIALIST_CORRECTION" in sidecar_source, "background correction guard missing")
    assert_true("v8-9-9-r1-preview-cpu-dual-stream" in build_source, "R1 build channel missing")

    sidecar = load_module("ort_v899_r1_sidecar", sidecar_path)
    events: list[dict] = []
    sidecar._EVENT_SINK = events

    class FakeFastModel:
        model_size = "base-preview"
        device = "cpu"
        compute_type = "int8"
        specialist_correction_enabled = False

        def transcribe(self, samples, stable=False):
            time.sleep(0.015)
            seconds = len(samples) / float(sidecar.TARGET_SAMPLE_RATE)
            text = "fast preview" if not stable else "fast final"
            return text, {
                "asr_ms": 15,
                "source_language": "ja",
                "bridge_language": "en",
                "asr_task": "translate",
                "japanese_specialist": True,
                "provisional": True,
                "specialist_correction_pending": False,
                "model_used": "base-preview",
            }

    worker = sidecar.StreamingInferenceWorker(FakeFastModel())
    worker.start()
    samples = np.ones(int(sidecar.TARGET_SAMPLE_RATE * 1.0), dtype=np.float32) * 0.01
    worker.submit(sidecar.Snapshot("r1", 1, samples, False, time.monotonic(), 1.0))
    worker.submit(sidecar.Snapshot("r1", 2, samples, True, time.monotonic(), 1.0))
    assert_true(worker.wait_final("r1", 1.0), "fast final did not complete")
    worker.stop()

    transcript_events = [item for item in events if item.get("type") in {"partial_transcript", "transcript"}]
    assert_true(transcript_events, "no streaming transcript events")
    assert_true(any(item.get("provisional") for item in transcript_events), "preview event was not marked provisional")
    assert_true(any(item.get("model") == "base-preview" for item in transcript_events), "preview model metadata missing")


    events.clear()

    class FakeCorrectingModel(FakeFastModel):
        specialist_correction_enabled = True

        def transcribe_specialist_correction(self, samples):
            time.sleep(0.03)
            return "specialist correction", {
                "asr_ms": 30,
                "source_language": "ja",
                "bridge_language": "en",
                "asr_task": "translate",
                "japanese_specialist": True,
                "specialist_correction": True,
                "provisional": False,
                "model_used": "kotoba-bilingual",
            }

        def transcribe(self, samples, stable=False):
            text, metadata = super().transcribe(samples, stable=stable)
            metadata["specialist_correction_pending"] = bool(stable)
            return text, metadata

    correcting_worker = sidecar.StreamingInferenceWorker(FakeCorrectingModel())
    correcting_worker.start()
    correcting_worker.submit(sidecar.Snapshot("corr", 1, samples, True, time.monotonic(), 1.0))
    assert_true(correcting_worker.wait_final("corr", 1.0), "fast final with correction did not complete")
    time.sleep(0.15)
    correcting_worker.stop()
    assert_true(
        any(item.get("specialist_correction") and item.get("text") == "specialist correction" for item in events),
        "specialist correction event missing",
    )

    mailbox = sidecar.LatestCorrectionMailbox()
    first = sidecar.Snapshot("old", 1, samples, True, time.monotonic(), 1.0)
    latest = sidecar.Snapshot("latest", 2, samples, True, time.monotonic(), 1.0)
    mailbox.put(first)
    mailbox.put(latest)
    selected = mailbox.get(0.1)
    assert_true(selected is not None and selected.result_id == "latest", "correction mailbox must keep only latest")

    print("ORT v8.9.9 R1 preview/performance regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
