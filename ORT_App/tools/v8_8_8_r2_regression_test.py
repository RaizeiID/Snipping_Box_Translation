from __future__ import annotations

from pathlib import Path
import sys
import time

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.prediction_guard import PredictionGuard
from app.runtime.mode_policy_manager import ModePolicyManager
from app.runtime.interval_fast_skip_safety import IntervalFastSkipSafety
from app.runtime.commander_profile_resolver import resolve_commander_token


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    pred = PredictionGuard.from_env()

    unrelated = pred.apply("Raizei How much do you know about the explosion at Lviv", raw_text="Raizei How much do you know about the explosion at Lviv")
    assert_true(unrelated.speaker == "Raizei", "Raizei must resolve as speaker")
    assert_true(unrelated.speaker_confidence == "Green", "Raizei must be Green")
    assert_true(not any(ev.ocr == "Hell" for ev in unrelated.events), "Hell->Heli must not fire on unrelated OCR")

    darture = pred.apply("Darture While I am surprised", raw_text="Darture While I am surprised")
    assert_true(darture.speaker == "Darture", "Darture must resolve as speaker")

    pol = pred.apply("Poludnitsa delivered something", raw_text="Poludnitsa delivered something")
    assert_true(pol.speaker == "Poludnitsa", "Poludnitsa must resolve as entity label")

    anfiya = pred.apply("Anfiya Sharapova leader of the Medical Team", raw_text="Anfiya Sharapova leader of the Medical Team")
    assert_true(anfiya.speaker == "Anfiya Sharapova", "Anfiya Sharapova must resolve")
    assert_true(anfiya.speaker_confidence == "Yellow", "Anfiya Sharapova should be Yellow/review")
    assert_true(anfiya.final_cache_blocked, "Yellow relation candidate must block final cache")

    actual_hell = pred.apply("Hell is not a speaker", raw_text="Hell is not a speaker")
    assert_true(any(ev.ocr == "Hell" and ev.label == "Red" for ev in actual_hell.events), "Hell should be blocked only when present")

    assert_true(resolve_commander_token("Raizei")["kind"] == "main_commander", "Raizei main commander")
    assert_true(resolve_commander_token("ATVITA ID")["kind"] == "alternate_profile_candidate", "ATVITA alternate only")

    mp = ModePolicyManager(False)
    assert_true(mp.policy_for("auto", "STABLE").policy_name == "auto_fast_preview_final", "auto policy")
    assert_true(mp.policy_for("interval", "STABLE").policy_name == "interval_semi_stable", "interval policy")
    assert_true(mp.policy_for("auto", "FREEZE").policy_name == "freeze_final_snapshot", "freeze policy")

    fs = IntervalFastSkipSafety(enabled=True, timeout_ms=10)
    assert_true(not fs.update("turn", "dialog", mode="interval", visible=False).force_commit, "not immediate")
    time.sleep(0.02)
    assert_true(fs.update("turn", "dialog", mode="interval", visible=False).force_commit, "force after timeout")

    print("v8.8.8-r2 regression PASS")


if __name__ == "__main__":
    main()
