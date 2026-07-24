from __future__ import annotations

from pathlib import Path
import sys

# v8.8.4 R2 hotfix:
# When this file is run as `python tools\v8_8_4_regression_test.py`,
# Python puts `tools/` on sys.path, not the runtime_app root.
# Add runtime_app explicitly so imports like `app.runtime.*` work.
RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.overlay_commit_gate import OverlayCommitGate
from app.runtime.render_signature import visual_signature, similarity
from app.runtime.dialogue_stability import DialogueTurnAccumulator
from app.runtime.recording_telemetry import RecordingTelemetry


def test_final_complete_override():
    gate = OverlayCommitGate(min_visible_ms=9999, min_token_gain=3)
    first = gate.decide(
        speaker_html="", dialog_html="short", plain_translation="Aku menunggu.",
        source_text="I wait", turn_id="t1", trusted_preview=True,
    )
    assert first.commit
    gate.mark_committed(speaker_html="", dialog_html="short", plain_translation="Aku menunggu.", source_text="I wait", turn_id="t1", signature=first.signature, state=first.state)
    second = gate.decide(
        speaker_html="", dialog_html="long", plain_translation="Aku akan menunggu dengan sabar sampai Commander kembali.",
        source_text="I will wait patiently until the Commander comes back.", turn_id="t1",
        trusted_preview=True, source_stable=True, force_complete=True, dialogue_state="AUTO_SMOOTH",
    )
    assert second.commit, second
    assert second.state == "FINAL_COMPLETE"


def test_never_empty_force_visible():
    gate = OverlayCommitGate(min_visible_ms=500, never_empty=True)
    dec = gate.decide(speaker_html="", dialog_html="", plain_translation="", source_text="Berryfield", turn_id="t2")
    assert not dec.commit
    assert dec.force_visible


def test_signature_dedupe():
    a = "Tmstill by yoUr side; Youre not alone"
    b = "I'm still by your side; You're not alone"
    assert similarity(a, b) > 0.70


def test_accumulator_flags_stable():
    acc = DialogueTurnAccumulator(auto_min_ms=80, auto_min_token_gain=2)
    d1 = acc.update("", "The Commander will", mode="AUTO", turn_id="a")
    assert d1.process
    d2 = acc.update("", "The Commander will come back.", mode="AUTO", turn_id="a")
    assert d2.process
    assert d2.source_stable


def test_telemetry_snapshot():
    t = RecordingTelemetry()
    t.inc("overlay_committed", 2)
    t.inc("overlay_committed_final_complete", 1)
    s = t.snapshot()
    assert "final_complete_ratio" in s


if __name__ == "__main__":
    test_final_complete_override()
    test_never_empty_force_visible()
    test_signature_dedupe()
    test_accumulator_flags_stable()
    test_telemetry_snapshot()
    print("v8.8.4 regression PASS")
