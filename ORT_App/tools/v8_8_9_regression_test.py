from __future__ import annotations

from pathlib import Path
import sys
import time

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.prediction_guard import PredictionGuard
from app.runtime.ui_dialog_filter import UIDialogFilter
from app.runtime.overlay_commit_gate import OverlayCommitGate
from app.runtime.dialogue_stability import DialogueTurnAccumulator
from app.translation.full_output_guard import FullOutputGuard
from app.translation.name_alias_normalizer import apply_name_aliases


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    pred = PredictionGuard.from_env()

    kenny = pred.apply("Kenny Here are the documents", raw_text="Kenny Here are the documents")
    assert_true(kenny.speaker == "Kenny", "Kenny must resolve as exact Green speaker")
    assert_true(kenny.speaker_confidence == "Green", "Kenny must be Green")
    assert_true(not kenny.final_cache_blocked, "Kenny Green exact must not block final cache")

    bath = pred.apply("bathildel should retreat immediately", raw_text="bathildel should retreat immediately")
    assert_true(bath.speaker == "Balthilde", "bathildel prefix must repair to Balthilde alias-family canonical")
    assert_true(bath.speaker_confidence == "Green", "bathildel repair should be Green with registered alias")
    assert_true(any(ev.reason == "registered_alias_prefix_guarded" for ev in bath.events), "alias prefix reason must be visible")

    body = pred.apply("The wounded Bathildel was carried out safely", raw_text="The wounded Bathildel was carried out safely")
    assert_true("Balthilde" in body.text, "Bathildel body alias must be repaired")

    heli = pred.apply("Heli is right here", raw_text="Heli is right here")
    helen = pred.apply("Helen is right here", raw_text="Helen is right here")
    helena = pred.apply("Helena is right here", raw_text="Helena is right here")
    assert_true(heli.speaker == "Heli", "Heli must stay distinct")
    assert_true(helen.speaker == "Helen", "Helen must stay distinct")
    assert_true(helena.speaker == "Helena", "Helena must stay distinct")

    hell = pred.apply("Hell is not a speaker", raw_text="Hell is not a speaker")
    assert_true(any(ev.label == "Red" for ev in hell.events), "Hell fragment must remain Red/blocked")
    assert_true(hell.final_cache_blocked, "Red ambiguity must block final cache")

    assert_true(apply_name_aliases("Keny and bathildel", "GFL2_EXILIUM") == "Kenny and Balthilde", "name alias normalizer v8.8.9")

    ui = UIDialogFilter()
    assert_true(not ui.check("30/54 Collect more to claim rewards Heroic Mode Story Supply").process, "reward UI must be filtered")
    assert_true(not ui.check("enge Mode Part Challenge Mode Part Antiparallel Part Supply 100% Story 68%").process, "fuzzy challenge/progress UI must be filtered")
    assert_true(ui.check("Kenny Here are the documents").process, "Kenny dialog must not be filtered")

    fg = FullOutputGuard()
    src = "Kenny Yes, that has been confirmed. The fact that the third-gen Doll has combat ability as her design priority"
    dec = fg.assess(src, "Ya, itu sudah dikonfirmasi.")
    assert_true(not dec.allow_final, "low coverage output must be caught")
    assert_true(dec.trusted_preview, "low coverage fallback must be visible no-cache preview")
    assert_true("Kenny Yes" in dec.output, "fallback must contain current source, not stale previous subtitle")

    gate = OverlayCommitGate(min_visible_ms=620)
    first = gate.decide(speaker_html="A", dialog_html="old", plain_translation="old translation", source_text="old source", turn_id="old", final=True, source_stable=True)
    assert_true(first.commit, "initial commit")
    gate.mark_committed(speaker_html="A", dialog_html="old", plain_translation="old translation", source_text="old source", turn_id="old", signature=first.signature, state=first.state)
    new_turn = gate.decide(speaker_html="B", dialog_html="new current source preview", plain_translation="new current source preview", source_text="new current source preview", turn_id="new", trusted_preview=True)
    assert_true(new_turn.commit, "new turn meaningful preview must replace stale last-good")

    acc = DialogueTurnAccumulator(interval_stable_ms=999, interval_min_token_gain=5)
    burst = acc.update("Kenny", "Here are the documents you requested from the archive", mode="INTERVAL", turn_id="t1")
    assert_true(burst.process, "manual burst interval dialog should start translation immediately")

    print("v8.8.9 regression PASS")


if __name__ == "__main__":
    main()
