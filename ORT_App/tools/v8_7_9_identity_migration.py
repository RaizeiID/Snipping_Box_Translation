"""Dry-run/apply v8.7.9 identity, term and observed-ledger alignment safely."""
from __future__ import annotations
import argparse, json, shutil, time
from pathlib import Path
BLOCKED_GLOBAL={'vilyz','arvitaid','atvitaid'}
def clean(v): return ' '.join(str(v or '').strip().split())
def key(v): return ''.join(c.lower() for c in clean(v) if c.isalnum())
def load(p, default):
    try: return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else default
    except Exception: return default
def dedupe(rows):
    out=[]; seen=set()
    for row in rows:
        name=clean(row.get('display_name','') if isinstance(row,dict) else row)
        if not name or key(name) in seen or key(name) in BLOCKED_GLOBAL: continue
        seen.add(key(name)); out.append(row if isinstance(row,dict) else {'canonical_id':key(name),'display_name':name,'category':'approved_role_speaker','aliases':[]})
    return out
def run(base_dir='.', apply=False):
    base=Path(base_dir).resolve(); configs=base/'configs'
    catalog=load(configs/'reference_roster_catalog_v8_7_3.json', {'games':{}})
    ledger=load(configs/'gfl2_observed_candidates_v8_7_9.json', {})
    defaults=load(configs/'speaker_registry_v2.defaults.json', {'games':{}})
    registry_path=base/'speaker_registry_v2.json'; registry=load(registry_path, defaults)
    g=registry.setdefault('games',{}).setdefault('GFL2_EXILIUM',{})
    dg=defaults.get('games',{}).get('GFL2_EXILIUM',{})
    official=[clean(x.get('display_name','')) for x in catalog.get('games',{}).get('GFL2_EXILIUM',{}).get('entries',[]) if isinstance(x,dict) and clean(x.get('display_name',''))]
    official_keys={key(x) for x in official}
    approved=[x for x in dg.get('approved_role_speaker',[]) if isinstance(x,dict) and key(x.get('display_name','')) not in BLOCKED_GLOBAL]
    approved_names=[clean(x.get('display_name','')) for x in approved]
    additions=[clean(x.get('display_name','')) for x in ledger.get('approved_exact_additions_v8_7_9',[]) if isinstance(x,dict)]
    terms=[clean(x) for x in dg.get('special_terms',[]) if clean(x)]
    aliases=[x for x in dg.get('reviewed_alias',[]) if isinstance(x,dict) and key(x.get('canonical_name','')) not in BLOCKED_GLOBAL]
    legacy=g.setdefault('legacy_untrusted',[])
    promoted=[clean(x.get('display_name','') if isinstance(x,dict) else x) for x in legacy if key(x.get('display_name','') if isinstance(x,dict) else x) in official_keys]
    lines=['ORT Translation v8.7.9 Identity & Terms Migration '+('APPLY' if apply else 'DRY-RUN'), 'Policy: official catalog exact-only; fresh verified names/roles exact-only; aliases ROI-only; Commander names never global.', f'Official exact-speaker entries: {len(official)}', f'Official removed from legacy_untrusted: {len(promoted)}', f'Approved exact/role available: {", ".join(approved_names) or "-"}', f'Fresh v8.7.9 additions: {", ".join(additions) or "-"}', f'Special terms total from defaults: {len(terms)}', 'Excluded global commander names: Vilyz, ARVITA ID, ATVITA ID', 'Pending review not auto-live: Chief of Odesa, Municipal Broadcast, Zyevnadya/Yyevnadya, Blondie, DKRIN, NOMFA, Perslcarla, Beepy, Warrant Officer']
    if not apply:
        lines.append('Gunakan --apply pada folder TEST setelah backup. Candidate mining tidak pernah auto-promote.')
        return '\n'.join(lines)
    backup=base/'backups'/f'identity_before_v8_7_9_{time.strftime("%Y%m%d_%H%M%S")}'; backup.mkdir(parents=True,exist_ok=True)
    if registry_path.exists(): shutil.copy2(registry_path, backup/registry_path.name)
    observed={key(x.get('display_name','')):x for x in ledger.get('observed_recent_story_v8_7_7',[]) if isinstance(x,dict)}
    g['verified_character_speaker_exact']=[{'canonical_id':key(n),'display_name':n,'category':'verified_character_speaker_exact','aliases':[],'source':'reference_catalog_entries_v8_7_9','origin_view':'catalog_exact','observed_recent_story':key(n) in observed,'observed_status':'observed_recent_story_v8_7_7' if key(n) in observed else 'catalog_only','faction':'','spoiler':False} for n in sorted(set(official),key=str.casefold)]
    g['approved_role_speaker']=dedupe(list(g.get('approved_role_speaker',[]))+approved)
    current_alias=list(g.get('reviewed_alias',[])); akeys={(str(x.get('ocr_form','')).casefold(), key(x.get('canonical_name',''))) for x in current_alias if isinstance(x,dict)}
    for row in aliases:
        pair=(str(row.get('ocr_form','')).casefold(),key(row.get('canonical_name','')))
        if pair not in akeys: current_alias.append(row); akeys.add(pair)
    g['reviewed_alias']=current_alias
    g['special_terms']=sorted({*map(clean,g.get('special_terms',[])),*terms}, key=str.casefold)
    g['legacy_untrusted']=[x for x in legacy if key(x.get('display_name','') if isinstance(x,dict) else x) not in official_keys]
    g['pending_session_candidate']=sorted(set(g.get('pending_session_candidate',[])+['Chief of Odesa','Municipal Broadcast','Zyevnadya / Yyevnadya','Blondie','DKRIN','NOMFA','Perslcarla','Beepy','Warrant Officer']),key=str.casefold)
    registry['schema_version']='v8_7_9_faithfulness_v2_strict_ct2_registry_v6'
    registry.setdefault('migration_notes',[]).append({'version':'v8.7.9','ts':time.time(),'change':'Fresh exact names/roles + observed ledger + terms; pending ambiguous candidates; commander excluded globally'})
    registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
    lines.append(f'Backup dibuat dan registry diterapkan: {backup.relative_to(base)}')
    return '\n'.join(lines)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-dir',default='.'); ap.add_argument('--apply',action='store_true'); a=ap.parse_args(); print(run(a.base_dir,a.apply)); return 0
if __name__=='__main__': raise SystemExit(main())
