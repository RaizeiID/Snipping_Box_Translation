from __future__ import annotations

from pathlib import Path
import sys
import time

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.ui_dialog_filter import UIDialogFilter
from app.runtime.prediction_guard import PredictionGuard
from app.runtime.commander_profile_resolver import resolve_commander_token
from app.runtime.dialogue_timeout_safety import DialogueTimeoutSafety
from app.runtime.candidate_extractor import classify_initial_candidate


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    ui = UIDialogFilter.from_env()
    assert_true(not ui.check("99% Loading Resources Sangvis Ferri").process, "loading text must be filtered")
    assert_true(not ui.check("Combat Effectiveness Combat Start Click tile or drag to deploy").process, "battle instruction must be filtered")

    pred = PredictionGuard.from_env()
    r = pred.apply("Nlkketa looks at Balthildes battered frame", raw_text="Nlkketa looks at Balthildes battered frame")
    assert_true("Nikketa" in r.text, "Nlkketa should be guarded-repaired to Nikketa")
    assert_true(r.final_cache_blocked, "yellow prediction must block final cache")

    r2 = pred.apply("angi Security Team Leader Requesting backup", raw_text="angi Security Team Leader Requesting backup")
    assert_true(r2.speaker == "Mangi Security Team Leader", "speaker label must resolve")
    assert_true("Requesting backup" in r2.text, "speaker label should be stripped from body")

    r3 = pred.apply("Hlon says something", raw_text="Hlon says something")
    assert_true(r3.ambiguous or any(ev.label == "Red" for ev in r3.events), "ambiguous fragment must be blocked")

    assert_true(resolve_commander_token("Raizei")["kind"] == "main_commander", "Raizei must be main commander")
    assert_true(resolve_commander_token("ATVITA ID")["kind"] == "alternate_profile_candidate", "ATVITA must not become main commander")

    c = classify_initial_candidate("Loading Resources According to our records")
    assert_true(c.kind == "negative_ui_or_narration", "loading prefix is not a name")
    c2 = classify_initial_candidate("Mangi Security Team Leader Dammit")
    assert_true(c2.kind == "speaker_label", "Mangi Security Team Leader is a speaker label")

    safety = DialogueTimeoutSafety(enabled=True, timeout_ms=20)
    d0 = safety.update(turn_id="t1", source="new dialog", held=True)
    assert_true(not d0.emergency_due, "should not be due immediately")
    time.sleep(0.03)
    d1 = safety.update(turn_id="t1", source="new dialog", held=True)
    assert_true(d1.emergency_due, "emergency commit should be due after timeout")

    print("v8.8.7 regression PASS")


if __name__ == "__main__":
    main()
