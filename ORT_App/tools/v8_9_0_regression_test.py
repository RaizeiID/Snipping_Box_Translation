from __future__ import annotations

from pathlib import Path
import sys

RUNTIME_APP_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_APP_ROOT))

from app.runtime.prediction_guard import PredictionGuard
from app.translation.ocr_text_repair import repair_text
from app.runtime.overlay_language_guard import guard_overlay_text, looks_like_english
from app.runtime.ui_dialog_filter import UIDialogFilter
from app.runtime.overlay_commit_gate import OverlayCommitGate
from app.ocr.readability_guard import score_text, rescue_percent


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    pred = PredictionGuard.from_env()
    for name in ["Littara", "Ullrid", "Phaetusa", "Sweeper", "Nyxie", "Kenny", "Raizei"]:
        r = pred.apply(f"{name} test line", raw_text=f"{name} test line")
        assert_true(r.speaker == name, f"{name} must resolve as registered speaker/entity")

    alias = pred.apply("UIlr Of course", raw_text="UIlr Of course")
    assert_true(alias.speaker == "Ullrid", "UIlr must repair to Ullrid as guarded alias")
    assert_true(alias.speaker_confidence in {"Yellow", "Green"}, "Ullrid alias should be confidence-labeled")

    rr = repair_text("Ifnot, ook at the healin9 data. Qur logs say weve seen it and callyoU later.")
    assert_true(rr.changed, "repair must change observed OCR corruptions")
    assert_true("If not" in rr.text, "Ifnot -> If not")
    assert_true("look at" in rr.text, "ook at -> look at")
    assert_true("healing" in rr.text, "healin9 -> healing")
    assert_true("our logs" in rr.text, "Qur -> our")
    assert_true("we've" in rr.text, "weve -> we've")
    assert_true("call you" in rr.text, "callyoU -> call you")

    guarded, hidden, reason = guard_overlay_text(
        "Raizei If not, then why is my head still attached to my neck",
        "Raizei If not, then why is my head still attached to my neck",
        trusted_preview=True,
    )
    assert_true(hidden, "English source preview must be hidden from user overlay")
    assert_true("Menerjemahkan" in guarded, "hidden source preview must become Indonesian waiting preview")
    assert_true(not looks_like_english(guarded), "waiting preview must not look English")

    ui = UIDialogFilter()
    for text in [
        "Toysmith Max Level aX Level",
        "Dammage Stats Confirm",
        "Clickanywhere to exit",
        "End Action 10/10 Marionette Melee",
        "mmander Level 240/240 Formation Platoon",
    ]:
        assert_true(not ui.check(text).process, f"UI text should be filtered: {text}")
    assert_true(ui.check("Sweeper You read our logs").process, "real dialogue with Sweeper must pass")

    a = score_text("healln9 Qur Ifnot ook at", applied_percent=45, min_story_percent=50)
    assert_true(a.needs_rescue, "low-corruption low-OCR text should request readability rescue")
    assert_true(rescue_percent(45, 50, 65) >= 50, "readability rescue should lift low OCR to safe floor")

    gate = OverlayCommitGate(min_visible_ms=620)
    first = gate.decide(speaker_html="A", dialog_html="Terjemahan lama", plain_translation="Terjemahan lama", source_text="old source", turn_id="old", final=True, source_stable=True)
    assert_true(first.commit, "initial overlay commit")
    gate.mark_committed(speaker_html="A", dialog_html="Terjemahan lama", plain_translation="Terjemahan lama", source_text="old source", turn_id="old", signature=first.signature, state=first.state)
    new_turn = gate.decide(speaker_html="B", dialog_html="Menerjemahkan dialog baru…", plain_translation="Menerjemahkan dialog baru…", source_text="new English source", turn_id="new", trusted_preview=True)
    assert_true(new_turn.commit, "new turn ID preview must replace stale old overlay")

    print("v8.9.0 regression PASS")


if __name__ == "__main__":
    main()
