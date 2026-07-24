from __future__ import annotations

from pathlib import Path
import sys

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.overlay_commit_gate import OverlayCommitGate
from app.runtime.render_signature import visual_signature, similarity, repair_ocr_text, ocr_corruption_score
from app.runtime.dialogue_stability import DialogueTurnAccumulator
from app.runtime.recording_telemetry import RecordingTelemetry
from app.runtime.ocr_churn_rescue import OCRChurnRescue
from app.runtime.turn_finalizer import TurnFinalizer
from app.runtime.bad_cache_shield import BadCacheShield


def test_source_longer_must_win():
    gate = OverlayCommitGate(min_visible_ms=9999, min_token_gain=3)
    first = gate.decide(speaker_html="", dialog_html="short", plain_translation="Aku menunggu.", source_text="I wait", turn_id="t1", trusted_preview=True)
    assert first.commit
    gate.mark_committed(speaker_html="", dialog_html="short", plain_translation="Aku menunggu.", source_text="I wait", turn_id="t1", signature=first.signature, state=first.state)
    second = gate.decide(
        speaker_html="", dialog_html="long", plain_translation="Aku akan menunggu dengan sabar sampai Commander kembali.",
        source_text="I will wait patiently until the Commander comes back", turn_id="t1",
        trusted_preview=True, source_stable=False, force_complete=False, dialogue_state="AUTO_SMOOTH",
    )
    assert second.commit, second
    assert second.state == "FINAL_COMPLETE"


def test_new_turn_wait_does_not_churn():
    gate = OverlayCommitGate(min_visible_ms=800)
    d = gate.decide(speaker_html="", dialog_html="old", plain_translation="Teks lama tetap terlihat.", source_text="Old text", turn_id="a", trusted_preview=True)
    assert d.commit
    gate.mark_committed(speaker_html="", dialog_html="old", plain_translation="Teks lama tetap terlihat.", source_text="Old text", turn_id="a", signature=d.signature, state=d.state)
    n = gate.decide(speaker_html="", dialog_html="new", plain_translation="And was thinking", source_text="And was thinking", turn_id="b", trusted_preview=True)
    assert not n.commit
    assert n.force_visible


def test_ocr_churn_repair_and_bad_cache():
    rescue = OCRChurnRescue(low_ocr_threshold=50)
    d = rescue.analyze("Berryflold Im not the only one Who proflted from thls", ocr_percent=40, mode="AUTO")
    assert d.repaired
    assert "Berryfield" in d.text
    shield = BadCacheShield(threshold=0.20)
    bc = shield.check("SCCTOpp3a Gernrlelo s Hcc IUqh CsCaoe hCrUO5", cache_label="HIT_STABLE_FINAL", ocr_percent=40)
    assert not bc.allow


def test_accumulator_final_ready():
    acc = DialogueTurnAccumulator(auto_min_ms=80, auto_min_token_gain=2, finalizer_wait_ms=80)
    d1 = acc.update("", "The Commander will", mode="AUTO", turn_id="a")
    assert d1.process
    d2 = acc.update("", "The Commander will come back", mode="AUTO", turn_id="a")
    assert d2.process
    assert d2.state in {"FINAL_READY", "AUTO_SMOOTH"}


def test_turn_finalizer_forces_final():
    tf = TurnFinalizer(final_wait_ms=0)
    dec = tf.update(turn_id="x", source="The Commander will come back", translation="Commander akan kembali", source_stable=True, final_payload=True, mode="AUTO")
    assert dec.force_final


def test_telemetry_snapshot():
    t = RecordingTelemetry()
    t.inc("overlay_committed", 3)
    t.inc("overlay_committed_final_complete", 2)
    t.inc("turn_finalizer_forced")
    s = t.snapshot()
    assert s["final_complete_ratio"] >= 0.6
    assert "turn_finalizer_forced" in s


if __name__ == "__main__":
    test_source_longer_must_win()
    test_new_turn_wait_does_not_churn()
    test_ocr_churn_repair_and_bad_cache()
    test_accumulator_final_ready()
    test_turn_finalizer_forces_final()
    test_telemetry_snapshot()
    print("v8.8.5 regression PASS")
