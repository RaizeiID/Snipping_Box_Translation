from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))


def require(cond, msg):
    if not cond: raise AssertionError(msg)

def main():
    from app.identity.speaker_registry import trusted_speaker_names, protect_named_entities, restore_named_entities
    names=trusted_speaker_names('GFL2_EXILIUM')
    for n in ['Helen','Helena','KSVK','Alya Kujou','Melanie','Balthilde','Phaetusa']:
        require(n in names, f'missing protected name {n}')
    p=protect_named_entities('Phaetusa meets Balthilde while Helen calls Helena and Alya Kujou.', 'GFL2_EXILIUM')
    require('Phaetusa' not in p.source and 'Helen' not in p.source, 'protected names not masked')
    require(restore_named_entities(p.source,p).startswith('Phaetusa meets Balthilde'), 'named entity restore failed')

    from app.ocr.gfl2_speaker_roi import _canonical
    from app.identity.speaker_registry import trusted_alias_map
    aliases=trusted_alias_map('GFL2_EXILIUM')
    require(_canonical('Helen',names,aliases)[0]=='Helen', 'Helen mapped incorrectly')
    require(_canonical('Helena',names,aliases)[0]=='Helena', 'Helena mapped incorrectly')
    require(_canonical('elanie',names,aliases)[0]=='Melanie', 'Melanie alias not restored')
    require(_canonical('Phaedusa',names,aliases)[0]=='Phaetusa', 'Phaetusa alias not restored')

    from app.translation.critical_token_guard import can_commit_final
    require(not can_commit_final('Attacks on Level Il')[0], 'ambiguous Level Il should not commit')
    require(can_commit_final('Attacks on Level II')[0], 'Level II should commit')

    from data_processing_backend import add_identity_name, identity_action_choices, migrate_identity_choice, delete_identity_choice, load_settings, render_reference_catalog_html, identity_detail_categories
    marker='Unit Test Role Speaker'
    add_identity_name('CUSTOM', marker, True)
    orange=next(x for x in identity_action_choices('CUSTOM') if marker in x)
    require(orange.startswith('🟠'), 'simple-added item must be orange/migratable')
    migrate_identity_choice('CUSTOM',orange,'approved_role_speaker')
    green=next(x for x in identity_action_choices('CUSTOM') if marker in x)
    require(green.startswith('🟢'), 'migrated item must be sorted/green')
    try:
        migrate_identity_choice('CUSTOM',green,'protected_character')
        raise AssertionError('green item should not allow simple migration')
    except ValueError:
        pass
    delete_identity_choice('CUSTOM', green, False)
    require(all(marker not in x for x in identity_action_choices('CUSTOM')), 'click-delete failed')
    require(load_settings().get('simple_view_enabled', True) is True or isinstance(load_settings().get('simple_view_enabled'), bool), 'simple setting invalid')
    require('Phaetusa' in render_reference_catalog_html('GFL2_EXILIUM'), 'GFL2 catalog missing Phaetusa')
    require('Jinhsi' in render_reference_catalog_html('WUWA'), 'WUWA roster missing Jinhsi')
    gfl_hidden=render_reference_catalog_html('GFL', False); gfl_shown=render_reference_catalog_html('GFL', True)
    require('Morridow' not in gfl_hidden and 'Morridow' in gfl_shown, 'GFL spoiler faction toggle failed')
    require(any('Paradeus' in label for _,label in identity_detail_categories('GFL')), 'GFL Paradeus migration category missing')

    os.environ.update({'ORT_GAME_PROFILE':'GFL2_EXILIUM','ORT_GAME_OVERRIDE':'GFL2_EXILIUM','ORT_MODEL_KEY':'idn_v3','ORT_MODEL_GROUP':'idn','ORT_IDN_EVAL_EXPORT':'0','ORT_NATURALIZED_CACHE':'0','ORT_STABLE_FINAL_CACHE_V2':'0','ORT_IDN_WARMUP':'0'})
    from translation_engine import TranslationEngine
    with tempfile.TemporaryDirectory() as d:
        def hostile_backend(text):
            return text.replace('Phaetusa','Phaedusa').replace('Balthilde','Balthalde')
        eng=TranslationEngine(d, hostile_backend, logger=lambda *_: None)
        out, meta=eng.translate('Phaetusa reports to Balthilde.')
        require('Phaetusa' in out and 'Balthilde' in out, 'backend corrupted protected entity')
        require('Phaedusa' not in out and 'Balthalde' not in out, 'wrong entity leaked')
    print('v8.7.3 regression test PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
