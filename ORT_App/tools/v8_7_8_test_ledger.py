"""Create v8.7.8 safety/test ledger from recent session event logs.

Recent-log limits keep the tool responsive on long-lived projects. Raise
--max-files explicitly for archival audits.
"""
from __future__ import annotations
import argparse
import json
import time
from collections import Counter
from pathlib import Path


def build(base_dir: str | Path = ".", *, max_files: int = 30, max_lines_per_file: int = 500_000) -> dict:
    base = Path(base_dir).resolve()
    files = list((base / "logs").glob("session_*_events.jsonl")) if (base / "logs").exists() else []
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    files = files[:max(1, max_files)]
    rows = []
    for path in files:
        c = Counter(); engines = Counter(); speakers = Counter(); reasons = Counter(); line_count = 0
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line_count, line in enumerate(fh, start=1):
                if line_count > max_lines_per_file:
                    break
                try:
                    obj = json.loads(line); typ = str(obj.get("type", "")); pl = obj.get("payload", {}) if isinstance(obj.get("payload", {}), dict) else {}
                except Exception:
                    continue
                c[typ] += 1
                if typ == "TRANSLATION_RESULT":
                    engines[str(pl.get("engine", "unknown"))] += 1
                    reasons[str(pl.get("faithfulness_reason", "safe"))] += 1
                if typ == "FINAL_OVERLAY" and pl.get("speaker"):
                    speakers[str(pl["speaker"])] += 1
        rows.append({
            "session": path.name, "lines_scanned": min(line_count, max_lines_per_file), "events": sum(c.values()),
            "engines": dict(engines), "speakers": dict(speakers), "faithfulness_reasons": dict(reasons),
            "semantic_blocked": c["SEMANTIC_HALLUCINATION_BLOCKED"], "semantic_cache_rejected": c["SEMANTIC_CACHE_REJECTED"],
            "qur_repaired": c["OCR_QUR_CORRUPTION_REPAIRED"], "qur_quarantined": c["QUR_CORRUPTION_QUARANTINED"],
            "strict_ct2_held": c["STRICT_CT2_STORY_HELD"], "argos_suppressed": c["STRICT_CT2_STORY_FALLBACK_SUPPRESSED"],
            "preview_held": c["PREVIEW_HELD_INCOMPLETE"], "omission_suspected": c["OMISSION_SUSPECTED"],
            "training_blocked": c["TRAINING_SAMPLE_BLOCKED_BY_SAFETY_GATE"], "ct2_job_fallback": c["CT2_JOB_FALLBACK"],
            "quality_lock_held": c["IDN_QUALITY_LOCK_HELD"], "ocr_rescue": c["OCR_READABILITY_RESCUE"],
            "false_speaker_blocked": c["FALSE_SPEAKER_BLOCKED"],
        })
    return {"version": "v8.7.8", "generated_at": time.time(), "policy": "Recent session ledger; increase --max-files only for archival audit.", "max_files": max_files, "max_lines_per_file": max_lines_per_file, "session_count": len(rows), "sessions": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--max-files", type=int, default=30)
    ap.add_argument("--max-lines-per-file", type=int, default=500_000)
    args = ap.parse_args()
    base = Path(args.base_dir).resolve()
    data = build(base, max_files=args.max_files, max_lines_per_file=args.max_lines_per_file)
    out = base / "logs" / f"v8_7_8_test_ledger_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Test ledger: {out} | sessions={data['session_count']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
