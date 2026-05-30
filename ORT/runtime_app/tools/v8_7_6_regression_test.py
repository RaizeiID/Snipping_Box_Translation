"""Regression tests for ORT Translation v8.7.6 adaptive OCR, exact fallback, and ledger features."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
NAMESPACE="v8_7_9_responsive_turn_safe_ct2"
def require(cond,msg):
    if not cond: raise AssertionError(msg)
def main():
    os.environ.update({"ORT_GAME_PROFILE":"GFL2_EXILIUM","ORT_GAME_OVERRIDE":"GFL2_EXILIUM","ORT_IDN_CACHE_VERSION":NAMESPACE,"ORT_SCOPED_CACHE_VERSION":NAMESPACE,"ORT_ENTITY_SPAN_PIPELINE":"1"})
    from model_strategy import build_strategy
    low=build_strategy("lite_idn_v2","ORTCore Lite IDN V2","lite_idn","V2","GFL2_EXILIUM",requested_ocr_resolution=None)
    require(low.ocr_resolution_percent==45,"V2 preset identity changed unexpectedly")
    overridden=build_strategy("lite_idn_v2","ORTCore Lite IDN V2","lite_idn","V2","GFL2_EXILIUM",requested_ocr_resolution=55,normal_override=True)
    require(overridden.ocr_resolution_percent==55,"manual Lite OCR override was silently capped")
    require(overridden.to_env().get("ORT_ADAPTIVE_READABILITY_GUARD")=="1","adaptive OCR env missing")
    require(overridden.to_env().get("ORT_GFL2_EXACT_FALLBACK_ONLY")=="1","exact fallback env missing")
    require(overridden.to_env().get("ORT_IDN_CACHE_VERSION")==NAMESPACE,"new cache namespace missing")
    from app.ocr.readability_guard import score_text, rescue_percent, select_better_text
    noisy="Hlno Pretty COMIIIAIOeT DKRIN Collepse radatlon seenls"
    clean="Helena Pretty Commander Collapse radiation seems to have no effect"
    assessment=score_text(noisy,40,50)
    require(assessment.needs_rescue,"corrupted low OCR should request rescue")
    require(rescue_percent(40,50)==50 and rescue_percent(45,50)>=50,"rescue target wrong")
    chosen,_,_,use=select_better_text(noisy,clean,40,50,50)
    require(use and chosen==clean,"readability guard did not prefer clear retry")
    from app.identity.speaker_registry import verified_character_speaker_names, speaker_exact_names
    official=verified_character_speaker_names("GFL2_EXILIUM")
    require(len(official)==69,"official GFL2 exact speaker catalog coverage changed")
    for name in ["Zhaohui","Vector","Colphne","Groza","Ullrid","Harpsy","Mayling"]:
        require(name in speaker_exact_names("GFL2_EXILIUM"),f"missing exact speaker {name}")
    src=(ROOT/"TITANMAIN.py").read_text(encoding="utf-8")
    for marker in ["GFL2_FALLBACK_SPEAKER_REJECTED","FALSE_SPEAKER_BLOCKED","ORT_GFL2_EXACT_FALLBACK_ONLY","OCR_READABILITY_RESCUE"]:
        require(marker in src,f"runtime feature missing: {marker}")
    require("if ORT_GFL2_SPEAKER_GATE and ORT_GFL2_EXACT_FALLBACK_ONLY" in src,"GFL2 exact-only parser gate absent")
    observed=json.loads((ROOT/"configs"/"gfl2_observed_candidates_v8_7_6.json").read_text(encoding="utf-8"))
    official_set=set(official)
    require(all(row["display_name"] in official_set for row in observed["observed_official_priority"]),"observed official duplicated outside catalog")
    require(any(row["ocr_form"]=="Perl" and row["canonical"]=="Peri" for row in observed["reviewed_alias_candidates"]),"alias review evidence absent")
    from launcher_backend import _dialog_scheduler_env
    env=_dialog_scheduler_env("auto","lite_idn_v2","GFL2_EXILIUM",False)
    require(env["ORT_ADAPTIVE_READABILITY_GUARD"]=="1" and env["ORT_GFL2_EXACT_FALLBACK_ONLY"]=="1","launcher adaptive/exact env absent")
    require(env["ORT_IDN_CACHE_VERSION"]==NAMESPACE,"launcher cache namespace wrong")
    from tools.v8_7_6_identity_migration import run as migrate
    with tempfile.TemporaryDirectory() as d:
        base=Path(d); (base/"configs").mkdir()
        for rel in ["configs/reference_roster_catalog_v8_7_3.json","configs/speaker_registry_v2.defaults.json","configs/gfl2_observed_candidates_v8_7_6.json","speaker_registry_v2.json"]:
            target=base/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes((ROOT/rel).read_bytes())
        text=migrate(base,apply=False)
        require("Official catalog entries: 69" in text and "Observed/priority metadata" in text,"migration dry-run incomplete")
        migrate(base,apply=True)
        saved=json.loads((base/"speaker_registry_v2.json").read_text(encoding="utf-8"))
        exact=saved["games"]["GFL2_EXILIUM"]["verified_character_speaker_exact"]
        require(len(exact)==69 and any(x.get("observed_recent_story") for x in exact),"migration official/observed alignment failed")
    print("v8.7.6 compatibility-on-v8.7.7 PASS")
    return 0
if __name__=="__main__": raise SystemExit(main())
