from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.identity.speaker_registry import strip_matching_speaker_prefix
from app.runtime.dialogue_stability import DialogueTurnAccumulator
from launcher_backend import _dialog_scheduler_env


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_speaker_prefix_v3():
    body, stripped = strip_matching_speaker_prefix("Phaetusa(?) Stop calling me that stupid name", "Phaetusa", "GFL2_EXILIUM")
    assert_true(stripped and body.startswith("Stop calling"), body)
    body, stripped = strip_matching_speaker_prefix("[Phaetusa(?)] Swap hair accessories?", "Phaetusa", "GFL2_EXILIUM")
    assert_true(stripped and body.startswith("Swap hair"), body)
    body, stripped = strip_matching_speaker_prefix("Phaetusa: Stop calling me that", "Phaetusa", "GFL2_EXILIUM")
    assert_true(stripped and body.startswith("Stop calling"), body)


def test_dialogue_accumulator_no_downgrade():
    acc = DialogueTurnAccumulator(auto_min_ms=80, auto_min_token_gain=3, interval_stable_ms=160)
    d1 = acc.update("Helena", "The pendant's cover springs open, revealing the weathered photo inside.", mode="STABLE", turn_id="t1")
    assert_true(d1.process, d1)
    d2 = acc.update("Helena", "revealing the weathered", mode="STABLE", turn_id="t1")
    assert_true(not d2.process or len(d2.text) > len("revealing the weathered"), d2)
    assert_true("pendant" in d2.text and "photo" in d2.text, d2.text)


def test_mode_policy_env():
    freeze = _dialog_scheduler_env("freeze", "lite_v2", "GFL2_EXILIUM", True)
    assert_true(freeze.get("ORT_FREEZE_OCR_OVERRIDE") == "1", freeze)
    assert_true(int(freeze.get("ORT_FREEZE_OCR_PERCENT", "0")) >= 100, freeze)
    auto = _dialog_scheduler_env("auto", "fast_v1", "GFL2_EXILIUM", True)
    assert_true(auto.get("ORT_AUTO_SMOOTH_MODE") == "1", auto)
    assert_true(int(auto.get("ORT_DIALOG_PROGRESSIVE_MIN_DELTA", "0")) >= 8, auto)
    interval = _dialog_scheduler_env("interval", "lite_v2", "GFL2_EXILIUM", True)
    assert_true(interval.get("ORT_INTERVAL_STORY_AWARE") == "1", interval)
    assert_true(int(interval.get("ORT_INTERVAL_STABLE_MS", "0")) >= 400, interval)


if __name__ == "__main__":
    test_speaker_prefix_v3()
    test_dialogue_accumulator_no_downgrade()
    test_mode_policy_env()
    print("v8.8.2 regression PASS")
