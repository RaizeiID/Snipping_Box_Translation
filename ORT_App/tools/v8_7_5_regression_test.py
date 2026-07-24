from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    os.environ.update({
        "ORT_GAME_PROFILE": "GFL2_EXILIUM", "ORT_GAME_OVERRIDE": "GFL2_EXILIUM",
        "ORT_MODEL_KEY": "idn_v3", "ORT_MODEL_GROUP": "idn", "ORT_IDN_EVAL_EXPORT": "0",
        "ORT_NATURALIZED_CACHE": "1", "ORT_STABLE_FINAL_CACHE_V2": "0", "ORT_IDN_WARMUP": "0",
        "ORT_IDN_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
        "ORT_SCOPED_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
        "ORT_ENTITY_SPAN_PIPELINE": "1", "ORT_SPEAKER_TRANSITION_GUARD": "1",
        "ORT_RESPONSIVE_STORY_MODE": "0",
    })
    from app.identity.speaker_registry import (
        trusted_speaker_names, verified_character_speaker_names, speaker_exact_names,
        has_internal_entity_token, trusted_alias_map,
    )
    active = trusted_speaker_names("GFL2_EXILIUM")
    exact = speaker_exact_names("GFL2_EXILIUM")
    verified = verified_character_speaker_names("GFL2_EXILIUM")
    for name in ["Helen", "Helena", "KSVK", "Alya Kujou", "Phaetusa"]:
        require(name in active, f"missing active speaker {name}")
    for name in ["Zhaohui", "Vector", "Colphne", "Groza", "Ullrid"]:
        require(name in verified and name in exact, f"missing verified exact speaker {name}")
    for marker in ["__ORT_ENTITY_001__", "_ _ ORT _ BKEND _ 000 _ _", "_ _ ORT _ BKED _ 000 _ _", "_ ORT _ BEND _ 001 _"]:
        require(has_internal_entity_token(marker), f"unsafe marker missed: {marker}")

    from app.ocr.gfl2_speaker_roi import _canonical
    aliases = trusted_alias_map("GFL2_EXILIUM")
    require(_canonical("Helen", exact, aliases, active)[0] == "Helen", "Helen cross-map")
    require(_canonical("Helena", exact, aliases, active)[0] == "Helena", "Helena cross-map")
    require(_canonical("Zhaohui", exact, aliases, active)[0] == "Zhaohui", "Zhaohui exact rejected")
    require(_canonical("Vector", exact, aliases, active)[0] == "Vector", "Vector exact rejected")
    require(_canonical("Zhohul", exact, aliases, active)[0] == "", "reference roster gained unsafe fuzzy")
    require(_canonical("elanie", exact, aliases, active)[0] == "Melanie", "reviewed alias regression")

    from app.identity.entity_span import translate_entity_safe_source, process_entity_safe, EntitySpan
    backend_seen = []
    def hostile_backend(fragment: str) -> str:
        backend_seen.append(fragment)
        return fragment.replace("meets", "bertemu").replace("calls", "memanggil")
    translated, spans, calls = translate_entity_safe_source("Phaetusa meets Balthilde while Helen calls Helena.", "GFL2_EXILIUM", hostile_backend)
    require(calls >= 1, "text spans were not translated")
    require(all("ORT" not in x for x in backend_seen), "internal marker entered backend")
    require(all(all(name not in x for name in ["Phaetusa", "Balthilde", "Helen", "Helena"]) for x in backend_seen), "entity entered backend")
    require(all(name in translated for name in ["Phaetusa", "Balthilde", "Helen", "Helena"]), "entity lost during backend-safe compose")
    require(sum(isinstance(span, EntitySpan) for span in spans) >= 4, "source entity spans missing")
    rendered, _ = process_entity_safe(translated, "GFL2_EXILIUM", lambda x: x.upper())
    require("Phaetusa" in rendered and "Helen" in rendered, "entity changed during IDN span postprocess")

    from translation_engine import TranslationEngine
    with tempfile.TemporaryDirectory() as tmp:
        engine_seen = []
        class Bridge:
            def post_translate_text(self, src, out, context_tags=None):
                require("ORT" not in out, "internal token entered bridge")
                return out
        def backend(text):
            engine_seen.append(text)
            return text
        eng = TranslationEngine(tmp, backend, logger=lambda *_: None)
        out, meta = eng.translate("Phaetusa meets Balthilde while Helen calls Helena.", bridge=Bridge())
        require(not has_internal_entity_token(out), "engine leaked marker")
        require(all("ORT" not in text for text in engine_seen), "backend saw marker")
        require(meta.get("backend_span_calls", 0) >= 1, "span backend metadata missing")
        from app.translation.naturalized_cache import NaturalizedCache
        cache = NaturalizedCache(tmp, game="GFL2_EXILIUM", model_key="idn_v3", mode="natural", version="v8_7_9_responsive_turn_safe_ct2")
        require("v8_7_9_responsive_turn_safe_ct2" in cache.path.name, "cache namespace wrong")
        cache.set("safe source", "_ ORT _ BEND _ 000 _")
        require(cache.get("safe source") is None, "unsafe cache value stored")

    from launcher_backend import _dialog_scheduler_env
    env = _dialog_scheduler_env("auto", "idn_v3", "GFL2_EXILIUM", True)
    require(env.get("ORT_IDN_CACHE_VERSION") == "v8_7_9_responsive_turn_safe_ct2", "launcher cache version wrong")
    require(env.get("ORT_SPEAKER_TRANSITION_GUARD") == "1", "transition guard env missing")
    require(env.get("ORT_LATEST_FRAME_WINS") == "1", "responsive latest frame missing")

    from tools.v8_7_5_identity_migration import run as migrate
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "configs").mkdir()
        shutil.copy2(ROOT / "configs" / "reference_roster_catalog_v8_7_3.json", base / "configs" / "reference_roster_catalog_v8_7_3.json")
        shutil.copy2(ROOT / "configs" / "speaker_registry_v2.defaults.json", base / "configs" / "speaker_registry_v2.defaults.json")
        shutil.copy2(ROOT / "speaker_registry_v2.json", base / "speaker_registry_v2.json")
        dry = migrate(base, apply=False)
        require("entries[].display_name" in dry and "Zhaohui: ADD/ENABLE EXACT" in dry, "migration schema/priority output absent")
        migrate(base, apply=True)
        saved = json.loads((base / "speaker_registry_v2.json").read_text(encoding="utf-8"))
        exact_saved = {row["display_name"] for row in saved["games"]["GFL2_EXILIUM"]["verified_character_speaker_exact"]}
        require("Zhaohui" in exact_saved and "Vector" in exact_saved, "verified exact migration apply failed")

    source = (ROOT / "TITANMAIN.py").read_text(encoding="utf-8")
    require("OVERLAY_STALE_SPEAKER_DROPPED" in source and "SPEAKER_TRANSITION_DETECTED" in source, "stale overlay guard absent")
    print("v8.7.5 regression test PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
