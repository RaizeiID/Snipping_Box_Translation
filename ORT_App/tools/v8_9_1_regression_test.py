#!/usr/bin/env python3
"""ORT v8.9.1 hotfix regression tests.

Covers:
- Sweeper exact speaker label loaded from current registry.
- Launcher/default registry no longer points to v8_8_8_r2.
- English preview is silenced by default instead of visible placeholder.
- UI filter rejects v8.9.0 recording leakage: Coading Resources, Marionette Repalr, mixed script garbage.
- Contextual OCR repair still fixes common OCR typos.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.runtime.prediction_guard import PredictionGuard
from app.runtime.ui_dialog_filter import UIDialogFilter
from app.runtime.overlay_language_guard import guard_overlay_text
from app.translation.ocr_text_repair import repair_text


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    os.environ.pop("ORT_GFL2_ENTITY_REGISTRY", None)
    os.environ["ORT_PREDICTION_GUARD"] = "1"
    pg = PredictionGuard.from_env()

    res = pg.apply("Sweeper You're right. Sangvis Ferri is no more.")
    assert_true(res.speaker == "Sweeper", f"Sweeper not resolved: {res}")
    assert_true(res.speaker_confidence.lower() == "green", f"Sweeper not green: {res.speaker_confidence}")

    res2 = pg.apply("Klukai intends to stop me.")
    assert_true(res2.speaker == "Klukai", f"Klukai not resolved: {res2}")

    ui = UIDialogFilter.from_env()
    bad_samples = [
        'Coading Resources In the URNC government started project named "Lazarus"',
        '入 Marionette Repalr',
        'Stun Uismay 入 U 本 Marlonette Repalr',
        'NzUtO Ra Rancaman @a 酋 UhDh',
        '27/45 Collect more to claim rewards Heroic Mode Supply Story',
    ]
    for s in bad_samples:
        d = ui.check(s)
        assert_true(not d.process, f"UI leakage not filtered: {s} -> {d}")

    out, hidden, reason = guard_overlay_text(
        "Sweeper You're right. Sangvis Ferri is no more.",
        "Sweeper You're right. Sangvis Ferri is no more.",
        trusted_preview=True,
    )
    assert_true(hidden, "English source preview was not detected")
    assert_true(out == "", f"English preview should be silenced by default, got: {out!r} reason={reason}")

    repaired = repair_text("Qur healin9 Ifnot ook at callyoU must'ye weve")
    text = repaired.text
    for expected in ["our", "healing", "If not", "look at", "call you", "must've", "we've"]:
        assert_true(expected in text, f"repair missing {expected!r}: {text!r}")

    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8", errors="ignore")
    assert_true("gfl2_entity_registry_v8_9_1.json" in launcher, "launcher default registry is not v8_9_1")
    assert_true('gfl2_entity_registry_v8_8_8_r2.json"))' not in launcher, "launcher still defaults to old v8_8_8_r2 registry")

    print("v8.9.1 hotfix regression PASS")


if __name__ == "__main__":
    main()
