"""Create v8.7.7 test ledger with faithfulness/completeness/CT2 reason counters."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from collections import Counter
def build(base_dir='.'):
    base=Path(base_dir).resolve(); sessions=sorted((base/'logs').glob('session_*_events.jsonl')) if (base/'logs').exists() else []
    rows=[]
    for path in sessions:
        c=Counter(); engines=Counter(); speakers=Counter()
        for line in path.read_text(encoding='utf-8',errors='ignore').splitlines():
            try: obj=json.loads(line)
            except Exception: continue
            typ=str(obj.get('type','')); pl=obj.get('payload',{}) if isinstance(obj.get('payload',{}),dict) else {}; c[typ]+=1
            if typ=='TRANSLATION_RESULT': engines[str(pl.get('engine','unknown'))]+=1
            if typ=='FINAL_OVERLAY' and pl.get('speaker'): speakers[str(pl['speaker'])]+=1
        rows.append({'session':path.name,'events':sum(c.values()),'engines':dict(engines),'speakers':dict(speakers),'semantic_blocked':c['SEMANTIC_HALLUCINATION_BLOCKED'],'semantic_cache_rejected':c['SEMANTIC_CACHE_REJECTED'],'preview_held':c['PREVIEW_HELD_INCOMPLETE'],'omission_suspected':c['OMISSION_SUSPECTED'],'ct2_job_fallback':c['CT2_JOB_FALLBACK'],'quality_lock_held':c['IDN_QUALITY_LOCK_HELD'],'ocr_rescue':c['OCR_READABILITY_RESCUE'],'false_speaker_blocked':c['FALSE_SPEAKER_BLOCKED']})
    return {'version':'v8.7.7','generated_at':time.time(),'session_count':len(rows),'sessions':rows}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-dir',default='.'); a=ap.parse_args(); base=Path(a.base_dir).resolve(); out=base/'logs'/f'v8_7_7_test_ledger_{time.strftime("%Y%m%d_%H%M%S")}.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(build(base),ensure_ascii=False,indent=2),encoding='utf-8'); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
