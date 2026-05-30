"""Build a compact v8.7.6 test ledger from structured session events."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from collections import Counter

def build(base_dir="."):
    base=Path(base_dir).resolve(); logdir=base/"logs"
    sessions=sorted(logdir.glob("session_*_events.jsonl")) if logdir.exists() else []
    rows=[]
    for path in sessions:
        counts=Counter(); speakers=Counter(); rescue=blocked=0; engine=Counter(); ocr_runtime=[]
        for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
            try: obj=json.loads(line)
            except Exception: continue
            typ=str(obj.get("type","")); payload=obj.get("payload",{}) if isinstance(obj.get("payload",{}),dict) else {}
            counts[typ]+=1
            if typ=="FINAL_OVERLAY" and payload.get("speaker"): speakers[str(payload["speaker"])]+=1
            if typ=="OCR_READABILITY_RESCUE": rescue+=1; ocr_runtime.append(payload.get("selected_percent"))
            if typ=="FALSE_SPEAKER_BLOCKED": blocked+=1
            if typ=="TRANSLATION_RESULT": engine[str(payload.get("engine","unknown"))]+=1
        rows.append({"session":path.name,"events":sum(counts.values()),"translation_results":counts.get("TRANSLATION_RESULT",0),"ocr_rescue_events":rescue,"false_speaker_blocked":blocked,"runtime_rescue_ocr_percent":ocr_runtime,"top_speakers":speakers.most_common(12),"engines":engine.most_common()})
    data={"version":"v8.7.6","generated_at":time.time(),"required_review_fields":["video/log file","model","preset/requested/applied/runtime-rescue OCR","backend actual","crop/scene","speaker hit/false label","latency","verdict","roadmap decision"],"sessions":rows}
    status=base/"status"; status.mkdir(exist_ok=True)
    (status/"V8_7_6_TEST_LEDGER.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# ORT v8.7.6 Test Ledger","","Setiap sesi baru wajib dilengkapi video/log/model/OCR/backend/verdict sebelum keputusan update berikutnya.","", "| Session | Results | Rescue | False Speaker Blocked | Top Speakers |","|---|---:|---:|---:|---|"]
    for row in rows:
        md.append(f"| {row['session']} | {row['translation_results']} | {row['ocr_rescue_events']} | {row['false_speaker_blocked']} | {', '.join(x[0] for x in row['top_speakers'][:5])} |")
    (status/"V8_7_6_TEST_LEDGER.md").write_text("\n".join(md),encoding="utf-8")
    return data
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base-dir",default="."); a=ap.parse_args(); data=build(a.base_dir); print(f"Ledger dibuat: sessions={len(data['sessions'])}"); return 0
if __name__=="__main__": raise SystemExit(main())
