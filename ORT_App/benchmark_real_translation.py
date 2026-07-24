"""v7.9 real translation benchmark.

Uses installed Argos if available. If Argos packages are missing, it reports fallback readiness without crashing.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from status_manager import write_status
BASE_DIR=Path(__file__).resolve().parent
SAMPLES=["Hello Commander", "Mission start", "We should retreat", "The enemy is nearby", "Thank you for helping me"]

def argos_or_stub(text: str) -> str:
    try:
        import argostranslate.translate
        langs = argostranslate.translate.get_installed_languages()
        src = next((l for l in langs if getattr(l,'code','').startswith('en')), None)
        dst = next((l for l in langs if getattr(l,'code','').startswith('id')), None)
        if src and dst:
            tr = src.get_translation(dst)
            if tr: return tr.translate(text)
    except Exception:
        pass
    return f"[argos-missing] {text}"

def main():
    rows=[]
    for s in SAMPLES:
        t0=time.perf_counter(); out=argos_or_stub(s); dt=round((time.perf_counter()-t0)*1000,2)
        rows.append({"source":s,"translation":out,"ms":dt,"fallback":out.startswith('[argos-missing]')})
    rep={"version":"v7.9","samples":rows,"avg_ms":round(sum(x['ms'] for x in rows)/len(rows),2),"fallback_count":sum(1 for x in rows if x['fallback'])}
    write_status("benchmark_real_translation",rep,BASE_DIR)
    print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
