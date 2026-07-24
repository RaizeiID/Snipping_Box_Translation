from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.temporal_ocr_consensus import TemporalOCRConsensus
from app.runtime.mode_buffer_policy import ModeBufferPolicy
from app.runtime.turn_finalizer import TurnFinalizer
from app.runtime.bad_cache_shield import BadCacheShield
from app.runtime.overlay_commit_gate import OverlayCommitGate


def main():
    c = TemporalOCRConsensus(window=3, min_frames=2, stable_ms=0)
    d1 = c.update(turn_id="1", text="Nlkketa came to find Dushevnaya")
    d2 = c.update(turn_id="1", text="Nikketa came to find Dushevnaya.")
    assert d2.ready, d2
    mb = ModeBufferPolicy(enabled=False)
    assert mb.update(turn_id="1").final_delay_due
    mb2 = ModeBufferPolicy(enabled=True, buffer_ms=1)
    assert not mb2.update(turn_id="1").final_delay_due
    tf = TurnFinalizer(final_wait_ms=0, hard_deadline_ms=0)
    tfd = tf.update(turn_id="a", source="Griffin's disbandment is one thing, but what she finds unacceptable is the idea.", translation="x", final_payload=True, consensus_ready=True, buffer_due=True)
    assert tfd.force_final and tfd.mandatory, tfd
    bc = BadCacheShield(threshold=0.2, min_words=3)
    assert not bc.check("SCCTOpp3a Gernrlelo s Hcc IUqh CsCaoe hCrUO5", cache_label="HIT_STABLE_FINAL", ocr_percent=40).allow
    gate = OverlayCommitGate(min_visible_ms=999)
    dec = gate.decide(speaker_html="", dialog_html="<span>final</span>", plain_translation="final full text", source_text="This is final full text.", final=True, force_complete=True)
    assert dec.commit and dec.state == "FINAL_COMPLETE", dec
    print("v8.8.6 regression PASS")

if __name__ == "__main__":
    main()
