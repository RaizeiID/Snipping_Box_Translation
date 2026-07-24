from __future__ import annotations

from pathlib import Path
import sys
import json
import tempfile
import subprocess

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.prediction_guard import PredictionGuard
from app.runtime.commander_profile_resolver import resolve_commander_token
from app.runtime.mode_policy_manager import ModePolicyManager
from app.runtime.interval_fast_skip_safety import IntervalFastSkipSafety
from app.runtime.candidate_extractor import classify_initial_candidate


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    pred = PredictionGuard.from_env()
    assert_true("Heli" in pred.characters, "Heli must be in registry")
    assert_true("Helen" in pred.characters and "Helena" in pred.characters, "Helen/Helena retained")
    assert_true("Anfiya Sharapova" in pred.characters, "Anfiya Sharapova must be registered")
    assert_true("Mangi Security Team Leader" in pred.speaker_labels, "Mangi Security Team Leader speaker label")
    assert_true("Shadow Figure" in pred.speaker_labels, "Shadow Figure speaker label")

    r = pred.apply("angi Security Team Leader Requesting backup", raw_text="angi Security Team Leader Requesting backup")
    assert_true(r.speaker == "Mangi Security Team Leader", "Mangi Security Team Leader resolves")

    r2 = pred.apply("Alya Sharapova", raw_text="Alya Sharapova")
    assert_true(r2.final_cache_blocked, "Wrong prior read must not be final-cached")

    assert_true(resolve_commander_token("Raizei")["kind"] == "main_commander", "Raizei main commander")
    assert_true(resolve_commander_token("ATVITA ID")["kind"] == "alternate_profile_candidate", "ATVITA alternate only")

    auto = ModePolicyManager(False).policy_for("auto", "STABLE")
    interval = ModePolicyManager(False).policy_for("interval", "STABLE")
    freeze = ModePolicyManager(False).policy_for("auto", "FREEZE")
    assert_true(auto.policy_name == "auto_fast_preview_final", "auto policy")
    assert_true(interval.policy_name == "interval_semi_stable", "interval policy")
    assert_true(freeze.policy_name == "freeze_final_snapshot", "freeze policy")

    c = classify_initial_candidate("Shadow Figure ...")
    assert_true(c.kind in {"masked_speaker_label", "review_candidate"}, "Shadow Figure classified")

    safety = IntervalFastSkipSafety(enabled=True, timeout_ms=0)
    d = safety.update("t1", "dialog text", mode="interval", visible=False)
    assert_true(d.force_commit, "interval fast skip can force commit")

    sample = Path(tempfile.mkdtemp()) / "sample.log"
    sample.write_text(
        "[12:00:00] [OCR] Loading Resources test\\n"
        "[12:00:01] [PIPE] cache=MISS | 123ms | engine=ct2_fast\\n"
        "[12:00:02] [COMMIT v8.8.8] repaint_last_good | reason=test\\n",
        encoding="utf-8",
    )
    out = sample.with_suffix(".json")
    subprocess.check_call([sys.executable, "tools/offline_replay_benchmark_v8_8_8.py", str(sample), "--out", str(out)], cwd=str(RUNTIME_APP_ROOT))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert_true(data["reports"][0]["metrics"]["ui_leakage_candidates"] >= 1, "replay benchmark detects UI leakage")
    print("v8.8.8 regression PASS")


if __name__ == "__main__":
    main()
