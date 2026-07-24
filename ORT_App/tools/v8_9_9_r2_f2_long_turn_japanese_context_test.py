from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_sidecar():
    spec = importlib.util.spec_from_file_location("ort_v899_r2_f2_sidecar", ROOT / "audio_realtime_local_sidecar.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("sidecar import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def test_turn_context_merge(sidecar) -> None:
    context = sidecar.RollingTurnContext(max_history_words=240, display_words=72)
    first = context.update("turn-1", "Thank you for waiting gentlemen.")
    second = context.update("turn-1", "gentlemen. One agent is still en route.")
    third = context.update("turn-1", "One agent is still en route, but these three are ready.")
    assert_true(first.full_words >= 5, first)
    assert_true("Thank you for waiting" in third.full_text, third.full_text)
    assert_true("One agent is still en route" in third.full_text, third.full_text)
    assert_true(third.full_words >= 13, third.full_words)
    shorter = context.update("turn-1", "still en route.")
    assert_true(shorter.full_words == third.full_words, (shorter.full_words, third.full_words))


def test_continuous_turn_window(sidecar) -> None:
    class Worker:
        def __init__(self):
            self.snapshots = []
        def submit(self, snapshot):
            self.snapshots.append(snapshot)

    events = []
    sidecar._EVENT_SINK = events
    policy = sidecar.LocalRealtimePolicy(
        profile="normal",
        first_partial_s=0.30,
        partial_interval_s=0.25,
        endpoint_s=0.60,
        max_phrase_s=1.0,
        pre_roll_s=0.20,
        carry_over_s=0.50,
        minimum_rms=0.003,
        noise_multiplier=2.0,
    )
    worker = Worker()
    controller = sidecar.UtteranceController(worker, policy)
    now = 10.0
    speech = np.ones(int(sidecar.TARGET_SAMPLE_RATE * 0.10), dtype=np.float32) * 0.02
    silence = np.zeros_like(speech)
    for _ in range(30):
        controller.feed(speech, now)
        now += 0.10
    speech_states = [event for event in events if event.get("state") == "SPEECH_ACTIVE"]
    assert_true(len(speech_states) == 1, speech_states)
    assert_true(controller.active_result_id, "long speech was ended prematurely")
    assert_true(any(event.get("name") == "continuous_turn_window_shift" for event in events), events)
    for _ in range(8):
        controller.feed(silence, now)
        now += 0.10
    finals = [snapshot for snapshot in worker.snapshots if snapshot.stable]
    assert_true(len(finals) == 1, len(finals))
    assert_true(finals[0].result_id == speech_states[0]["segment_id"], finals[0].result_id)
    sidecar._EVENT_SINK = None


def test_japanese_search_policy(sidecar) -> None:
    class Segment:
        text = "The entire Japanese sentence is preserved."
    class Info:
        language = "en"
        language_probability = 1.0
    class Model:
        def __init__(self):
            self.kwargs = []
        def transcribe(self, _audio, **kwargs):
            self.kwargs.append(kwargs)
            return [Segment()], Info()

    adapter = sidecar.ModelAdapter(
        model_root=ROOT,
        model_size="kotoba-bilingual",
        fallback_model_size="base",
        device="cuda",
        compute_type="int8_float16",
        cpu_threads=4,
        language="ja",
        allow_cpu_fallback=False,
        game="GFL2_EXILIUM",
        requested_language="ja-specialist",
        japanese_specialist=True,
        language_correction_mode="off",
        language_locked=False,
        profile="normal",
    )
    model = Model()
    audio = np.ones(sidecar.TARGET_SAMPLE_RATE * 2, dtype=np.float32) * 0.01
    adapter._transcribe_once(model, audio, "ja", specialist=True, stable=False)
    adapter._transcribe_once(model, audio, "ja", specialist=True, stable=True)
    assert_true(model.kwargs[0]["beam_size"] == 2, model.kwargs[0])
    assert_true(model.kwargs[1]["beam_size"] == 3, model.kwargs[1])
    assert_true(model.kwargs[0]["no_speech_threshold"] == 0.52, model.kwargs[0])
    assert_true(model.kwargs[0]["language"] == "en" and model.kwargs[0]["task"] == "translate", model.kwargs[0])


def test_parent_turn_handoff_contract() -> None:
    source = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    for marker in (
        "previous_final_grace",
        "latest_words < 4",
        "latest_age <= 1.8",
        "turn_context_words",
    ):
        assert_true(marker in source, marker)


def main() -> int:
    sidecar = load_sidecar()
    test_turn_context_merge(sidecar)
    test_continuous_turn_window(sidecar)
    test_japanese_search_policy(sidecar)
    test_parent_turn_handoff_contract()
    print("ORT v8.9.9 R2 F2 long-turn/Japanese context regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
