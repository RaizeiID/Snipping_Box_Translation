#!/usr/bin/env python3
from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr.text_roi_change_gate import TextROIChangeGate
from app.runtime.overlay_commit_gate import OverlayCommitGate
from app.runtime.turn_state_machine import TurnStateMachine
from app.telemetry.atomic_jsonl import append_jsonl
from build_info import APP_VERSION_TAG


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _jsonl_worker(path: str, worker_id: int, count: int) -> None:
    for index in range(count):
        ok = append_jsonl(path, {"worker": worker_id, "index": index, "text": "uji aman ✓"})
        if not ok:
            raise RuntimeError(f"append failed: worker={worker_id} index={index}")


class _SyntheticGate(TextROIChangeGate):
    def __init__(self, signatures):
        super().__init__(threshold=0.10, max_hold_ms=15000, min_run_gap_ms=0, confirm_delay_ms=100)
        self.signatures = iter(signatures)

    def _signature(self, frame_rgb):
        import numpy as np

        return np.array(next(self.signatures), dtype="uint8")


def test_version_truth() -> None:
    assert_true(APP_VERSION_TAG.startswith(("v8.9.2", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6")), f"unexpected build version: {APP_VERSION_TAG}")
    for name in ("ORTCORE_VERSION.txt", "TITANCORE_VERSION.txt"):
        value = (ROOT / name).read_text(encoding="utf-8").strip()
        assert_true(value == APP_VERSION_TAG, f"{name} mismatch: {value}")
    project_version = (ROOT.parents[1] / "VERSION.txt").read_text(encoding="utf-8").strip()
    assert_true(project_version == APP_VERSION_TAG, f"root VERSION mismatch: {project_version}")


def test_text_roi_gate() -> None:
    gate = _SyntheticGate([
        [[0, 0], [0, 0]],
        [[0, 0], [0, 0]],
        [[0, 0], [0, 0]],
        [[1, 1], [1, 1]],
    ])
    first = gate.should_run(None)
    gate._last_run_ts -= 0.2
    confirm = gate.should_run(None)
    static = gate.should_run(None)
    changed = gate.should_run(None)
    assert_true(first.run and first.reason == "first_text_roi", f"first gate failed: {first}")
    assert_true(confirm.run and confirm.reason == "text_stability_confirm", f"confirm gate failed: {confirm}")
    assert_true(not static.run and static.reason == "static_text_roi", f"static gate failed: {static}")
    assert_true(changed.run and changed.reason == "text_roi_changed", f"changed gate failed: {changed}")


def test_turn_generation_state() -> None:
    state = TurnStateMachine(new_turn_similarity=0.52, absence_misses=2, absence_min_ms=0)
    first = state.observe("We will")
    progressive = state.observe("We will return home.")
    duplicate = state.observe("We will return home.")
    assert_true(first.is_new_turn, f"initial turn missing: {first}")
    assert_true(progressive.turn_id == first.turn_id, f"progressive text split turn: {progressive}")
    assert_true(progressive.generation_id > first.generation_id, "generation did not advance")
    assert_true(not state.is_current(first.turn_id, first.generation_id), "stale token accepted")
    assert_true(duplicate.generation_id == progressive.generation_id, "duplicate advanced generation")
    second = state.observe("The mission is over.")
    assert_true(second.is_new_turn and second.turn_id != first.turn_id, f"new turn not detected: {second}")
    assert_true(not state.observe_absence().should_clear, "clear ignored debounce")
    clear = state.observe_absence()
    assert_true(clear.should_clear and clear.previous_turn_id == second.turn_id, f"explicit clear failed: {clear}")
    assert_true(state.is_generation_current(clear.generation_id), "clear generation is not current")


def test_transactional_overlay() -> None:
    gate = OverlayCommitGate(min_visible_ms=0, min_token_gain=2)
    preview = gate.decide(
        speaker_html="<b>A</b>",
        dialog_html="<span>Kita akan</span>",
        plain_translation="Kita akan",
        source_text="We will",
        turn_id="turn-a",
        generation_id=1,
        final=True,
        source_stable=False,
    )
    assert_true(preview.commit and not preview.final, f"preview classification failed: {preview}")
    gate.mark_committed(speaker_html="<b>A</b>", dialog_html="<span>Kita akan</span>", plain_translation="Kita akan", source_text="We will", turn_id="turn-a", generation_id=1, signature=preview.signature, state=preview.state, final=preview.final)

    final = gate.decide(
        speaker_html="<b>A</b>",
        dialog_html="<span>Kita akan pulang.</span>",
        plain_translation="Kita akan pulang.",
        source_text="We will return home.",
        turn_id="turn-a",
        generation_id=2,
        final=True,
        source_stable=True,
        force_complete=True,
    )
    assert_true(final.commit and final.final, f"final commit failed: {final}")
    gate.mark_committed(speaker_html="<b>A</b>", dialog_html="<span>Kita akan pulang.</span>", plain_translation="Kita akan pulang.", source_text="We will return home.", turn_id="turn-a", generation_id=2, signature=final.signature, state=final.state, final=final.final)

    repeated_final = gate.decide(
        speaker_html="<b>A</b>",
        dialog_html="<span>Kita benar-benar akan pulang.</span>",
        plain_translation="Kita benar-benar akan pulang.",
        source_text="We really will return home.",
        turn_id="turn-a",
        generation_id=3,
        final=True,
        source_stable=True,
        force_complete=True,
    )
    assert_true(not repeated_final.commit and repeated_final.state == "FINAL_LOCKED", f"multi-final was not blocked: {repeated_final}")
    assert_true(gate.final_commit_counts.get("turn-a") == 1, f"final count invalid: {gate.final_commit_counts}")


def test_atomic_jsonl() -> None:
    with tempfile.TemporaryDirectory(prefix="ort_v892_jsonl_") as temp_dir:
        path = str(Path(temp_dir) / "events.jsonl")
        workers = [mp.Process(target=_jsonl_worker, args=(path, worker_id, 80)) for worker_id in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(20)
            assert_true(worker.exitcode == 0, f"JSONL worker failed: {worker.exitcode}")
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        assert_true(len(lines) == 320, f"JSONL line count mismatch: {len(lines)}")
        items = [json.loads(line) for line in lines]
        identities = {(item["worker"], item["index"]) for item in items}
        assert_true(len(identities) == 320, f"JSONL duplicate/lost events: {len(identities)}")


def test_runtime_wiring() -> None:
    titan = (ROOT / "TITANMAIN.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    assert_true("STALE_OVERLAY_CLEARED_ON_NEW_TURN" not in titan, "new-turn clear event still active")
    assert_true(titan.count('"FINAL_OVERLAY"') == 1, "FINAL_OVERLAY must only be emitted after accepted commit")
    assert_true('"ORT_IMAGE_HASH_GATE": "0"' not in launcher, "Auto still disables the OCR change gate")
    assert_true('"ORT_TEXT_ROI_MAX_HOLD_MS": "15000"' in launcher, "Auto static hold is not configured")
    assert_true('os.environ.setdefault("ORT_OVERLAY_SHOW_ID_WAITING_PREVIEW", "0")' in launcher, "placeholder preview default changed")


def main() -> None:
    test_version_truth()
    test_text_roi_gate()
    test_turn_generation_state()
    test_transactional_overlay()
    test_atomic_jsonl()
    test_runtime_wiring()
    print(f"{APP_VERSION_TAG} core regression PASS")


if __name__ == "__main__":
    main()
