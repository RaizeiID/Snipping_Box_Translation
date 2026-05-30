"""Migrate legacy translation_memory.json into v8.0 scoped cache files.

Usage:
    python tools/migrate_legacy_cache.py

By default this migrates root translation_memory.json into cache/translation_memory_custom_normal_legacy.json,
filters OCR/UI noise, then writes a backup marker. It does not delete the old file automatically.
"""
from __future__ import annotations
import json, time, shutil
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cache_store import ScopedCacheStore, should_cache_text
from status_manager import write_status

def main():
    legacy = ROOT / 'translation_memory.json'
    if not legacy.exists():
        rep={'version':'v8.0','state':'NO_LEGACY_FILE','legacy':str(legacy)}
        write_status('cache_migration',rep,ROOT); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0
    raw=json.loads(legacy.read_text(encoding='utf-8-sig'))
    if not isinstance(raw, dict): raw={}
    cache=ScopedCacheStore(ROOT, game='custom', model_key='legacy', family='normal')
    imported=skipped=0
    for k,v in raw.items():
        if not isinstance(k,str) or not isinstance(v,str): skipped+=1; continue
        ok,_=should_cache_text(k,v)
        if not ok: skipped+=1; continue
        if cache.set(k,v): imported+=1
    cache.flush(force=True)
    backup = ROOT / '_legacy_data_not_included' / f'translation_memory_migrated_{int(time.time())}.json.bak.note'
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(f'Migrated from {legacy} at {time.ctime()} | imported={imported} skipped={skipped}\n', encoding='utf-8')
    rep={'version':'v8.0','state':'MIGRATED','legacy':str(legacy),'cache_file':str(cache.path),'imported':imported,'skipped':skipped,'note':str(backup)}
    write_status('cache_migration',rep,ROOT); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
