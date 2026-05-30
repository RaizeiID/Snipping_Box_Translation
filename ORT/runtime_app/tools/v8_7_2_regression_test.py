from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_text_repair():
    from app.ocr.ocr_noise_normalizer import normalize_ocr_noise
    from app.translation.name_alias_normalizer import apply_name_aliases
    check("KSVK is unable" in apply_name_aliases("KSVKis unable", "GFL2_EXILIUM"), "KSVKis repair failed")
    check("DP-12's voice" in apply_name_aliases("DP-125 voice", "GFL2_EXILIUM"), "DP-125 possessive repair failed")
    repaired = normalize_ocr_noise("DP-12 Ifshe really isan enemy, Iike we apologles and recelved it")
    for expected in ["If she", "is an", "like", "apologies", "received"]:
        check(expected.lower() in repaired.lower(), f"missing OCR repair: {expected} in {repaired}")


def test_cache_and_idn_export():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ.update({
            "ORT_GAME_PROFILE": "GFL2_EXILIUM", "ORT_MODEL_KEY": "idn_v3", "ORT_MODEL_GROUP": "idn",
            "ORT_STABLE_FINAL_CACHE_V2": "1", "ORT_CURRENT_DIALOG_MEMO": "1", "ORT_UI_REQUESTED_MODE": "auto",
            "ORT_BOOT_MODE": "auto", "ORT_CACHE_PROGRESSIVE_GUARD": "1", "ORT_FUZZY_CACHE_KEY": "1",
            "ORT_ENABLE_LEGACY_VAULT": "0", "ORT_NATURALIZED_CACHE": "0", "ORT_IDN_EVAL_EXPORT": "1",
            "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "lite_light", "ORT_IDN_NATURALIZER": "0",
        })
        import translation_engine as te
        te._ENGINE = None
        engine = te.TranslationEngine(tmp, offline_argos=lambda s: "TERJEMAHAN: " + s, logger=lambda *a, **k: None)
        src = "DP-12 This is a complete stable dialogue sentence."
        out1, m1 = engine.translate(src)
        check(m1.get("cache") == "MISS", "first stable line must miss")
        check(m1.get("cache_store") == "SKIP_PROGRESSIVE_PENDING_FINAL", "Auto first line must wait for final confirmation")
        out2, m2 = engine.translate(src)
        check(m2.get("cache") == "DUPLICATE_OCR_SUPPRESSED", f"duplicate memo not used: {m2}")
        out3, m3 = engine.translate(src)
        check(m3.get("cache") == "HIT_STABLE_FINAL", f"stable final cache did not hit: {m3}")
        eval_file = Path(tmp) / "logs" / "idn_evaluation_v8_7_8.jsonl"
        check(eval_file.exists(), "IDN evaluation export not created")
        data = json.loads(eval_file.read_text(encoding="utf-8").splitlines()[0])
        check("source_normalized" in data and "backend_output" in data and "final_idn_output" in data, "evaluation fields missing")


def test_gfl2_speaker_roi():
    import numpy as np
    from app.ocr.gfl2_speaker_roi import GFL2SpeakerTracker
    class Reader:
        def __init__(self): self.calls = 0
        def readtext(self, img, detail=1, paragraph=False, allowlist=None):
            self.calls += 1
            if self.calls == 1:
                return [([[0,0],[40,0],[40,12],[0,12]], "KSVK", 0.95)]
            return []
    tracker = GFL2SpeakerTracker(["DP-12", "KSVK"])
    img = np.zeros((80, 420), dtype="uint8")
    first = tracker.process(Reader(), img, "is unable to accept")
    check(first.speaker == "KSVK" and not first.text.startswith("KSVK "), "KSVK ROI metadata should not be injected into body text")
    class Empty:
        def readtext(self, *a, **k): return []
    second = tracker.process(Empty(), img, "is unable to accept the state")
    check(second.speaker == "KSVK" and second.temporal_hold, "temporal label hold failed")


def test_profile_flags():
    from v7_system_profile import env_from_settings
    env = env_from_settings("GFL2_EXILIUM", model_key="idn_v3")
    for flag in ["ORT_GFL2_SPEAKER_ROI", "ORT_STABLE_FINAL_CACHE_V2", "ORT_CURRENT_DIALOG_MEMO", "ORT_IDN_EVAL_EXPORT", "ORT_IDN_WARMUP"]:
        check(env.get(flag) == "1", f"flag not active: {flag}")


def main():
    test_text_repair()
    test_cache_and_idn_export()
    test_gfl2_speaker_roi()
    test_profile_flags()
    print("v8.7.2 compatibility regression PASS under v8.7.5: cache final/memo, metadata-only GFL2 ROI, text repair, IDN export, and profile flags verified.")

if __name__ == "__main__":
    main()
