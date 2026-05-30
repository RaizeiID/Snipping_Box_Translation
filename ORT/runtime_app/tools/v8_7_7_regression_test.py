"""Regression tests for ORT Translation v8.7.7 semantic fidelity, completeness and CT2 binding."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
NAMESPACE='v8_7_9_responsive_turn_safe_ct2'
def require(cond,msg):
    if not cond: raise AssertionError(msg)
def main():
    os.environ.update({'ORT_GAME_PROFILE':'GFL2_EXILIUM','ORT_GAME_OVERRIDE':'GFL2_EXILIUM','ORT_IDN_CACHE_VERSION':NAMESPACE,'ORT_SCOPED_CACHE_VERSION':NAMESPACE,'ORT_ENTITY_SPAN_PIPELINE':'1','ORT_SEMANTIC_FAITHFULNESS_GATE':'1','ORT_DIALOGUE_COMPLETENESS_GATE':'1','ORT_NATURALIZED_CACHE':'0','ORT_IDN_EVAL_EXPORT':'0','ORT_STABLE_FINAL_CACHE_V2':'1','ORT_IDN_WARMUP':'0','ORT_MODEL_KEY':'normal_v1','ORT_MODEL_GROUP':'normal'})
    from app.translation.faithfulness_gate import assess_translation
    require(not assess_translation('and chose the latter.','Dan mereka adalah para nabi dan para malaikat.').allowed,'religious injection not blocked')
    require(not assess_translation('We will turn it into Qur reality.','Kami mengubahnya menjadi realitas Quran.').allowed,'OCR-triggered Quran injection not blocked')
    require(assess_translation('The prophet reached Mecca.','Nabi tiba di Mekah.').allowed,'legitimate supported concept blocked')
    from app.translation.dialogue_completeness_gate import hold_incomplete_source
    require(hold_incomplete_source('and chose the latter','progressive').hold,'short connective progressive not held')
    require(not hold_incomplete_source('This is a complete sentence.','new').hold,'complete punctuation source incorrectly held')
    from translation_engine import TranslationEngine
    with tempfile.TemporaryDirectory() as d:
        eng=TranslationEngine(d, lambda text: 'Dan mereka adalah para nabi dan para malaikat.')
        out,meta=eng.translate('and chose the latter.')
        require(meta.get('cache_blocked')=='semantic_hallucination','engine did not block semantic hallucination')
        require(meta.get('overlay_hold') and out == 'and chose the latter.','short hallucination should hold safe overlay')
    defaults=json.loads((ROOT/'configs'/'speaker_registry_v2.defaults.json').read_text(encoding='utf-8'))['games']['GFL2_EXILIUM']
    approved={x['display_name'] for x in defaults['approved_role_speaker']}
    for name in ['Berryfield','Cocoon','Carmen','Another Unfamiliar Worker']:
        require(name in approved,f'missing approved exact CT2-live name {name}')
    forbidden={'Vilyz','ARVITA ID','ATVITA ID'}
    require(not (approved & forbidden),'Commander profile name incorrectly enabled globally')
    for term in ['URNC','Conglomerate','Green Zone','Yellow Zone','Odesa','ELID','ELIDs','ODE-01','Griffin','Griffin & Kryuger','Blusphere']:
        require(term in defaults['special_terms'],f'missing special term {term}')
    from launcher_backend import _dialog_scheduler_env
    env=_dialog_scheduler_env('auto','lite_idn_v2','GFL2_EXILIUM',False)
    require(env['ORT_IDN_CACHE_VERSION']==NAMESPACE,'launcher namespace wrong')
    require(env['ORT_SEMANTIC_FAITHFULNESS_GATE']=='1' and env['ORT_DIALOGUE_COMPLETENESS_GATE']=='1','launcher semantic/completeness flags missing')
    launch_src=(ROOT/'launcher_backend.py').read_text(encoding='utf-8')
    for key in ['TITAN_SPM_EN_ID_DIR','ORT_LITE_CT2_MODEL_DIR','Repair / Rebind CT2 Model & SPM Path']:
        require(key in launch_src,f'CT2 permanent rebind missing: {key}')
    from tools.v8_7_7_identity_migration import run as migrate
    with tempfile.TemporaryDirectory() as d:
        b=Path(d); (b/'configs').mkdir();
        for rel in ['configs/reference_roster_catalog_v8_7_3.json','configs/speaker_registry_v2.defaults.json','configs/gfl2_observed_candidates_v8_7_7.json']:
            (b/rel).write_bytes((ROOT/rel).read_bytes())
        txt=migrate(b,apply=False); require('Berryfield' in txt and 'ARVITA ID' in txt,'migration report lacks additions/exclusions')
        migrate(b,apply=True); saved=json.loads((b/'speaker_registry_v2.json').read_text(encoding='utf-8'))['games']['GFL2_EXILIUM']
        names={x['display_name'] for x in saved['approved_role_speaker']}
        require('Berryfield' in names and not (names & forbidden),'migration activation/exclusion wrong')
    print('v8.7.7 regression test PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
