from __future__ import annotations
import json, time, os
from pathlib import Path
from cache_store import ScopedCacheStore
from status_manager import write_status
BASE_DIR=Path(__file__).resolve().parent

def main():
    os.environ.setdefault('ORT_GAME_PROFILE','BENCH')
    os.environ.setdefault('ORT_MODEL_KEY','bench')
    os.environ.setdefault('ORT_MODEL_GROUP','normal')
    cache=ScopedCacheStore(BASE_DIR, game='BENCH', model_key='bench', family='normal')
    samples=[('Hello','Halo'),('Mission start','Misi dimulai'),('Retreat now','Mundur sekarang')]
    for k,v in samples: cache.set(k,v)
    cache.flush(force=True)
    t0=time.perf_counter(); hits=sum(1 for k,_ in samples if cache.get(k)); dt=round((time.perf_counter()-t0)*1000,3)
    rep={'version':'v7.9','hits':hits,'total':len(samples),'hit_rate':hits/len(samples),'lookup_ms':dt,'cache_file':str(cache.path)}
    write_status('benchmark_cache_hit',rep,BASE_DIR)
    print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
