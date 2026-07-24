"""Regression tests for reconstructed ORT Translation v8.7.9 patch."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
NAMESPACE="v8_7_9_responsive_turn_safe_ct2"
def require(value, message):
    if not value: raise AssertionError(message)
def main():
    os.environ.update({'ORT_GAME_PROFILE':'GFL2_EXILIUM','ORT_GAME_OVERRIDE':'GFL2_EXILIUM','ORT_IDN_CACHE_VERSION':NAMESPACE,'ORT_SCOPED_CACHE_VERSION':NAMESPACE,'ORT_ENTITY_SPAN_PIPELINE':'1','ORT_SEMANTIC_FAITHFULNESS_GATE':'1','ORT_DIALOGUE_COMPLETENESS_GATE':'1','ORT_QUR_CORRUPTION_QUARANTINE':'1','ORT_STRICT_CT2_STORY':'1','ORT_HARD_STRICT_CT2_STORY':'1','ORT_FORCE_TRUSTED_PREVIEW':'1','ORT_RESPONSIVE_STORY_MODE':'1','ORT_LATEST_FRAME_WINS':'1','ORT_TURN_SAFE_OVERLAY':'1','ORT_SCENE_EXIT_GUARD':'1','ORT_SEMANTIC_FIDELITY_GUARD':'1','ORT_NATURALIZED_CACHE':'0','ORT_IDN_EVAL_EXPORT':'0','ORT_STABLE_FINAL_CACHE_V2':'1','ORT_IDN_WARMUP':'0','ORT_MODEL_KEY':'normal_v1','ORT_MODEL_GROUP':'normal','ORT_FINAL_ONLY_SAFE_COMMIT':'0'})
    from app.runtime.turn_safe_overlay import TurnSafeOverlayController, is_scene_exit_text
    require(is_scene_exit_text('Collect more to claim rewards Normal Hard'), 'Scene exit guard failed')
    ctl=TurnSafeOverlayController(); first=ctl.evaluate('DP-12','The timid girl begins to speak.'); growing=ctl.evaluate('DP-12','The timid girl begins to speak softly.'); next_turn=ctl.evaluate('','Okay!')
    require(not first.clear_overlay and not growing.clear_overlay and next_turn.clear_overlay, 'Turn-safe progressive/new-turn behavior failed')
    from app.translation.semantic_fidelity_guard import assess_semantic_fidelity
    drift=assess_semantic_fidelity('I will not believe any news of the Commander death until I see his body myself.','Aku percaya berita itu.','Aku tidak akan percaya berita kematian Commander sampai melihat jasadnya sendiri.')
    require(not drift.allowed and 'negation_lost' in drift.flags, 'Semantic fidelity negation detection failed')
    action=assess_semantic_fidelity('DP-12 bows slightly, ending the conversation.','DP-12 mengakhiri percakapan.','DP-12 membungkuk sedikit, mengakhiri percakapan.')
    require(not action.allowed and any('action_lost' in f for f in action.flags), 'Semantic fidelity action detection failed')
    import model_strategy
    env=model_strategy.build_strategy('idn_v5','idn','GFL2_EXILIUM','auto','auto','auto').to_env()
    require(env['ORT_IDN_CACHE_VERSION']==NAMESPACE and env['ORT_HARD_STRICT_CT2_STORY']=='1' and env['ORT_FORCE_TRUSTED_PREVIEW']=='1', 'v8.7.9 env flags missing')
    from translation_engine import TranslationEngine
    class PreviewCT2:
        def translate(self, text): return 'Pratinjau aman bergerak cepat'
    with tempfile.TemporaryDirectory() as d:
        os.environ['ORT_FINAL_ONLY_SAFE_COMMIT']='1'
        eng=TranslationEngine(d, lambda text: 'ARGOS SHOULD NOT RUN')
        eng.ct2=PreviewCT2()
        preview, pmeta=eng.translate('This dialogue is still growing without punctuation')
        require(pmeta.get('trusted_preview') and pmeta.get('engine')=='ct2_trusted_preview' and pmeta.get('cache_blocked')=='trusted_preview_not_final', 'Trusted Preview CT2-only lane failed')
    class IdentityCT2:
        def translate(self, text): return text
    called=[]
    with tempfile.TemporaryDirectory() as d:
        os.environ['ORT_FINAL_ONLY_SAFE_COMMIT']='0'
        eng=TranslationEngine(d, lambda text: called.append(text) or 'ARGOS FALLBACK')
        eng.ct2=IdentityCT2()
        held, hmeta=eng.translate('This dialogue is final.')
        require(hmeta.get('overlay_hold') and hmeta.get('hold_reason')=='hard_strict_ct2_no_argos_story' and not called, 'Hard Strict CT2 allowed Argos story fallback')
    defaults=json.loads((ROOT/'configs'/'speaker_registry_v2.defaults.json').read_text(encoding='utf-8'))['games']['GFL2_EXILIUM']
    approved={x['display_name'] for x in defaults['approved_role_speaker']}
    require({'Berryfield','Cocoon','Carmen','Another Unfamiliar Worker','Kalina','Farkas','Client'}.issubset(approved), 'Safe exact names lost')
    require(not ({'Vilyz','ARVITA ID','ATVITA ID'} & approved), 'Commander exclusion failed')
    require({'Port Vest','Collapse Epiphyllum','Boojum','NOMFA','Satellite City'}.issubset(set(defaults['special_terms'])), 'Special term update missing')
    from tools.v8_7_9_identity_migration import run as migrate
    with tempfile.TemporaryDirectory() as d:
        b=Path(d); (b/'configs').mkdir()
        for rel in ['configs/reference_roster_catalog_v8_7_3.json','configs/speaker_registry_v2.defaults.json','configs/gfl2_observed_candidates_v8_7_9.json']:
            (b/rel).write_bytes((ROOT/rel).read_bytes())
        report=migrate(b, apply=False)
        require('Kalina' in report and 'Vilyz' in report, 'Migration dry-run incomplete')
    print('v8.7.9 reconstructed regression PASS')
if __name__=='__main__': main()
