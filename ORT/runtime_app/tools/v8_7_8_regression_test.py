"""Regression tests for ORT Translation v8.7.8 Faithfulness v2 and strict CT2 story."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
NAMESPACE='v8_7_9_responsive_turn_safe_ct2'
def require(cond,msg):
    if not cond: raise AssertionError(msg)
def main():
    os.environ.update({'ORT_GAME_PROFILE':'GFL2_EXILIUM','ORT_GAME_OVERRIDE':'GFL2_EXILIUM','ORT_IDN_CACHE_VERSION':NAMESPACE,'ORT_SCOPED_CACHE_VERSION':NAMESPACE,'ORT_ENTITY_SPAN_PIPELINE':'1','ORT_SEMANTIC_FAITHFULNESS_GATE':'1','ORT_DIALOGUE_COMPLETENESS_GATE':'1','ORT_QUR_CORRUPTION_QUARANTINE':'1','ORT_STRICT_CT2_STORY':'1','ORT_DISABLE_ARGOS_PROGRESSIVE_WHEN_CT2':'1','ORT_NATURALIZED_CACHE':'0','ORT_IDN_EVAL_EXPORT':'0','ORT_STABLE_FINAL_CACHE_V2':'1','ORT_IDN_WARMUP':'0','ORT_MODEL_KEY':'normal_v1','ORT_MODEL_GROUP':'normal','ORT_FINAL_ONLY_SAFE_COMMIT':'0'})
    from app.translation.faithfulness_gate import assess_translation, quarantine_qur_corruption
    bad=[
      ('tell that we gathered suggests the order comes from above.','Ayat ini mengisyaratkan fakta ilmiah dalam al-Qur \'ân.'),
      ('Thank you for your help.','Orang-orang yang terhadap zakat menunaikannya.'),
      ('a simple promise; like sparks.','Sesungguhnya neraka akan melontarkan bunga api.'),
      ('We will turn it into Qur reality.','Kami mengubahnya menjadi realitas Quran.'),
    ]
    for src,out in bad: require(not assess_translation(src,out).allowed, f'failed to block: {out}')
    require(assess_translation('The Quran contains a verse.','Al-Quran memuat ayat.').allowed,'supported religious source incorrectly blocked')
    require(quarantine_qur_corruption('Will do Qur best').repaired_source=='Will do our best','Qur best not repaired')
    require(quarantine_qur_corruption('Qur division of labor').repaired_source=='Our division of labor','Qur division not repaired')
    require(quarantine_qur_corruption('Qur ownership').quarantined,'ambiguous Qur not quarantined')
    from app.translation.dialogue_completeness_gate import hold_incomplete_source
    require(hold_incomplete_source('This dialogue is still growing without punctuation','new',final_only_accuracy=True).hold,'final-only accuracy did not wait')
    require(not hold_incomplete_source('This dialogue is final.','new',final_only_accuracy=True).hold,'terminal final incorrectly held')
    import model_strategy
    strategy=model_strategy.build_strategy('idn_v5','idn','GFL2_EXILIUM','auto','auto','auto')
    env=strategy.to_env(); require(env['ORT_IDN_OVER_CT2']=='1' and env['ORT_FINAL_ONLY_SAFE_COMMIT']=='1','IDN-over-CT2/final commit flags missing'); require(env['ORT_IDN_CACHE_VERSION']==NAMESPACE,'namespace wrong')
    from translation_engine import TranslationEngine
    with tempfile.TemporaryDirectory() as d:
        eng=TranslationEngine(d, lambda text: 'Ayat ini terdapat pada al-Qur \'ân dan zakat.')
        out,meta=eng.translate('Thank you for your help.')
        require(meta.get('cache_blocked')=='semantic_hallucination','engine did not block faithfulness v2')
        require(meta.get('overlay_hold') and out=='Thank you for your help.','short blocked output did not hold safe source')
    defaults=json.loads((ROOT/'configs'/'speaker_registry_v2.defaults.json').read_text(encoding='utf-8'))['games']['GFL2_EXILIUM']
    approved={x['display_name'] for x in defaults['approved_role_speaker']}
    for name in ['Kalina','Farkas','Client','Berryfield','Cocoon','Carmen','Another Unfamiliar Worker']:
        require(name in approved,f'missing exact-only addition {name}')
    require(not ({'Vilyz','ARVITA ID','ATVITA ID'} & approved),'Commander global exclusion failed')
    for term in ['Satellite City','ODE-01 Municipal Center','URNC','Conglomerate','ODE-01']:
        require(term in defaults['special_terms'],f'missing protected term {term}')
    from tools.v8_7_8_identity_migration import run as migrate
    with tempfile.TemporaryDirectory() as d:
        b=Path(d); (b/'configs').mkdir()
        for rel in ['configs/reference_roster_catalog_v8_7_3.json','configs/speaker_registry_v2.defaults.json','configs/gfl2_observed_candidates_v8_7_8.json']:
            (b/rel).write_bytes((ROOT/rel).read_bytes())
        txt=migrate(b,apply=False); require('Kalina' in txt and 'Zyevnadya' in txt,'migration report incomplete')
        migrate(b,apply=True); saved=json.loads((b/'speaker_registry_v2.json').read_text(encoding='utf-8'))['games']['GFL2_EXILIUM']; names={x['display_name'] for x in saved['approved_role_speaker']}; require('Kalina' in names and 'Vilyz' not in names,'migration apply wrong')
    print('v8.7.8 regression test PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
