from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

def main():
    from model_registry import list_models
    bad = [(m.title, m.default_mode) for m in list_models() if m.default_mode != "auto"]
    check(not bad, f"Non-auto built-in model defaults remain: {bad}")

    from app.translation.name_alias_normalizer import apply_name_aliases
    check(apply_name_aliases("Dp-12 Please wait", "GFL2_EXILIUM").startswith("DP-12"), "DP-12 alias failed")
    check("KSVK and" in apply_name_aliases("KSVKand me", "GFL2_EXILIUM"), "KSVK join repair failed")

    os.environ["ORT_GFL2_SPEAKER_GATE"] = "1"
    from app.translation.speaker_candidate_gate import is_valid_speaker_candidate
    check(is_valid_speaker_candidate("DP-12")[0], "DP-12 seeded speaker rejected")
    check(is_valid_speaker_candidate("KSVK")[0], "KSVK seeded speaker rejected")
    check(not is_valid_speaker_candidate("Hereyes")[0], "Narrative false speaker accepted")

    from v7_system_profile import env_from_settings
    env = env_from_settings("GFL2_EXILIUM", model_key="idn_v3")
    check(env.get("ORT_GFL2_SPEAKER_GATE") == "1", "GFL2 gate not activated")
    check(env.get("ORT_ENABLE_LEGACY_VAULT") == "0", "Legacy vault not isolated by default")
    check(env.get("ORT_CACHE_PROGRESSIVE_GUARD") == "1", "Progressive cache guard inactive")

    from cache_store import should_cache_text
    old = os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD")
    os.environ["ORT_CACHE_PROGRESSIVE_GUARD"] = "1"
    try:
        ok, reason = should_cache_text("DP-12 Thi", "x")
        check(not ok and reason == "progressive_short_prefix", f"Short prefix not blocked: {ok}, {reason}")
    finally:
        if old is None: os.environ.pop("ORT_CACHE_PROGRESSIVE_GUARD", None)
        else: os.environ["ORT_CACHE_PROGRESSIVE_GUARD"] = old

    from data_processing_backend import SEED_GFL2_NAMES
    check("DP-12" in SEED_GFL2_NAMES and "KSVK" in SEED_GFL2_NAMES, "Seeded GFL2 glossary names missing")
    print("v8.7.1 regression test PASS: Auto defaults, GFL2 names, clean-vault/cache/speaker guards verified.")

if __name__ == "__main__":
    main()
