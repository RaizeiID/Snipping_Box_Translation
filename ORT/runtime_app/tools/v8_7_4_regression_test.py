from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

def require(cond,msg):
    if not cond: raise AssertionError(msg)

def main():
    os.environ.update({'ORT_GAME_PROFILE':'GFL2_EXILIUM','ORT_GAME_OVERRIDE':'GFL2_EXILIUM','ORT_MODEL_KEY':'idn_v3','ORT_MODEL_GROUP':'idn','ORT_IDN_EVAL_EXPORT':'0','ORT_NATURALIZED_CACHE':'1','ORT_STABLE_FINAL_CACHE_V2':'0','ORT_IDN_WARMUP':'0','ORT_IDN_CACHE_VERSION':'v8_7_9_responsive_turn_safe_ct2','ORT_SCOPED_CACHE_VERSION':'v8_7_9_responsive_turn_safe_ct2','ORT_ENTITY_SPAN_PIPELINE':'1','ORT_RESPONSIVE_STORY_MODE':'0'})
    from app.identity.speaker_registry import trusted_speaker_names, protect_named_entities, restore_named_entities, has_internal_entity_token
    from app.identity.entity_span import split_entity_spans, process_entity_safe, EntitySpan
    names=trusted_speaker_names('GFL2_EXILIUM')
    for n in ['Helen','Helena','KSVK','Alya Kujou','Melanie','Balthilde','Phaetusa']:
        require(n in names, f'missing protected name {n}')
    p=protect_named_entities('Phaetusa meets Balthilde while Helen calls Helena.', 'GFL2_EXILIUM')
    require('__ORT_BKEND_' in p.source and 'Phaetusa' not in p.source, 'backend-only protection absent')
    restored=restore_named_entities(p.source,p)
    require('Phaetusa' in restored and 'Helen' in restored and not has_internal_entity_token(restored),'backend token restore failed')
    spans=split_entity_spans('Phaetusa meets Helen and Helena.', 'GFL2_EXILIUM')
    require(sum(isinstance(x,EntitySpan) for x in spans)>=3,'entity spans missing')
    seen=[]
    rendered,_=process_entity_safe('Phaetusa meets Helen.', 'GFL2_EXILIUM', lambda t: seen.append(t) or t.upper())
    require('Phaetusa' in rendered and 'Helen' in rendered,'entity changed by text processor')
    require(all('Phaetusa' not in t and 'Helen' not in t for t in seen),'entity entered text processor')
    require(has_internal_entity_token('bad _ _ ORT _ ENTITY _ 018 _ _'),'residual marker not detected')

    from app.ocr.gfl2_speaker_roi import _canonical
    from app.identity.speaker_registry import trusted_alias_map
    aliases=trusted_alias_map('GFL2_EXILIUM')
    require(_canonical('Helen',names,aliases)[0]=='Helen','Helen cross-map')
    require(_canonical('Helena',names,aliases)[0]=='Helena','Helena cross-map')
    require(_canonical('elanie',names,aliases)[0]=='Melanie','Melanie alias')

    class HostileBridge:
        def __init__(self): self.seen=[]
        def post_translate_text(self, src, out, context_tags=None):
            self.seen.append(out)
            return out.replace(' meets ', ' bertemu ')
    from translation_engine import TranslationEngine
    with tempfile.TemporaryDirectory() as d:
        bridge=HostileBridge()
        eng=TranslationEngine(d, lambda text:text, logger=lambda *_:None)
        out,meta=eng.translate('Phaetusa meets Balthilde while Helen calls Helena.',bridge=bridge)
        require('Phaetusa' in out and 'Balthilde' in out and 'Helen' in out and 'Helena' in out,'canonical entity missing in final')
        require(not has_internal_entity_token(out),'internal marker leaked final')
        require(all('ORT_' not in x for x in bridge.seen),'token entered IDN/bridge processor')
        require(bool(meta.get('entity_span_pipeline')),'entity span metadata absent')
        from app.translation.naturalized_cache import NaturalizedCache
        c=NaturalizedCache(d,game='GFL2_EXILIUM',model_key='idn_v3',mode='natural',version='v8_7_9_responsive_turn_safe_ct2')
        require('v8_7_9_responsive_turn_safe_ct2' in c.path.name,'cache file namespace incorrect')
        c.set('X','__ORT_ENTITY_001__')
        require(c.get('X') is None,'residual token cached')

    from launcher_backend import _dialog_scheduler_env
    env=_dialog_scheduler_env('auto','idn_v3','GFL2_EXILIUM',True)
    require(env.get('ORT_RESPONSIVE_STORY_MODE')=='1' and env.get('ORT_LATEST_FRAME_WINS')=='1','responsive env missing')
    require(env.get('ORT_IDN_CACHE_VERSION')=='v8_7_9_responsive_turn_safe_ct2','launcher cache version wrong')
    require(int(env.get('ORT_DIALOG_PROGRESSIVE_MIN_DELTA','0'))>=10,'responsive coalescing not aggressive')
    from launcher_backend import save_prefs, load_prefs
    with tempfile.TemporaryDirectory() as _ignore:
        pass
    print('v8.7.4 compatibility regression PASS under v8.7.6')
    return 0
if __name__=='__main__': raise SystemExit(main())
