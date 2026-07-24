"""Replay OCR/Overlay comparison helper for ORT Translation v8.7.9.

This tool compares exported observations from one or more runtime runs against a
manually labelled ground-truth JSON created from the same video frames. It does
not fabricate cross-version evidence: feed each version's exported results.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from difflib import SequenceMatcher

def _norm(text:str)->str:
    return " ".join(str(text or "").strip().split())

def cer(ref:str, hyp:str)->float:
    ref,hyp=_norm(ref),_norm(hyp)
    if not ref: return 0.0 if not hyp else 1.0
    # Levenshtein characters
    prev=list(range(len(hyp)+1))
    for i,a in enumerate(ref,1):
        cur=[i]
        for j,b in enumerate(hyp,1):
            cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(a!=b)))
        prev=cur
    return round(prev[-1]/max(1,len(ref)),4)

def wer(ref:str,hyp:str)->float:
    r=_norm(ref).split(); h=_norm(hyp).split()
    if not r: return 0.0 if not h else 1.0
    prev=list(range(len(h)+1))
    for i,a in enumerate(r,1):
        cur=[i]
        for j,b in enumerate(h,1):
            cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(a.lower()!=b.lower())))
        prev=cur
    return round(prev[-1]/max(1,len(r)),4)

def load_rows(path:Path):
    text=path.read_text(encoding="utf-8-sig",errors="ignore").strip()
    if path.suffix.lower()==".jsonl":
        return [json.loads(x) for x in text.splitlines() if x.strip()]
    raw=json.loads(text)
    return raw.get("samples",raw) if isinstance(raw,dict) else raw

def compare(truth_path:Path, result_paths:list[Path], out_path:Path):
    truth={str(x["id"]):x for x in load_rows(truth_path)}
    report={"tool":"ORT v8.7.9 Replay OCR & Overlay Benchmark","ground_truth":str(truth_path),"runs":[]}
    for result_path in result_paths:
        rows=load_rows(result_path); by_id={str(x["id"]):x for x in rows}
        metrics=[]; speaker_hits=false_speakers=stale=0
        for sid,gt in truth.items():
            pred=by_id.get(sid,{})
            ref=_norm(gt.get("body","")); hyp=_norm(pred.get("ocr_body",pred.get("body","")))
            gt_sp=_norm(gt.get("speaker","")); pr_sp=_norm(pred.get("speaker",""))
            speaker_hits += int(bool(gt_sp) and gt_sp.casefold()==pr_sp.casefold())
            false_speakers += int(not gt_sp and bool(pr_sp))
            stale += int(bool(pred.get("stale_overlay",False)))
            metrics.append({"id":sid,"cer":cer(ref,hyp),"wer":wer(ref,hyp),"speaker_expected":gt_sp,"speaker_predicted":pr_sp})
        n=max(1,len(metrics))
        report["runs"].append({"file":str(result_path),"samples":len(metrics),"mean_cer":round(sum(x["cer"] for x in metrics)/n,4),"mean_wer":round(sum(x["wer"] for x in metrics)/n,4),"speaker_label_hit_rate":round(speaker_hits/n,4),"false_speaker_count":false_speakers,"stale_overlay_count":stale,"semantic_hallucination_count":sum(int(bool(by_id.get(sid,{}).get("semantic_blocked",False) or by_id.get(sid,{}).get("faithfulness_allowed") is False)) for sid in truth),"qur_quarantine_count":sum(int(bool(by_id.get(sid,{}).get("qur_quarantine"))) for sid in truth),"strict_ct2_hold_count":sum(int(str(by_id.get(sid,{}).get("hold_reason", "")).startswith("strict_ct2")) for sid in truth),"cache_rejected_count":sum(int(by_id.get(sid,{}).get("cache_allowed_after_gate") is False) for sid in truth),"omission_suspected_count":sum(int(bool(by_id.get(sid,{}).get("omission_suspected",False))) for sid in truth),"details":metrics})
    out_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def main():
    ap=argparse.ArgumentParser(description="Compare identical labelled video frames across ORT runtime exports.")
    ap.add_argument("--truth",required=True,help="JSON samples: id, speaker, body")
    ap.add_argument("--results",required=True,nargs="+",help="One or more JSON/JSONL results with matching id and ocr_body/body/speaker")
    ap.add_argument("--out",default="status/v8_7_9_replay_benchmark.json")
    a=ap.parse_args()
    report=compare(Path(a.truth),[Path(x) for x in a.results],Path(a.out))
    print(f"Replay benchmark written: {a.out} | runs={len(report['runs'])}")
    return 0
if __name__=="__main__": raise SystemExit(main())
