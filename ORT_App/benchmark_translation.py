"""Safe v7.9 translation pipeline benchmark using an offline stub fallback."""
from __future__ import annotations
import json, time
from pathlib import Path
from status_manager import write_status
BASE_DIR = Path(__file__).resolve().parent
SAMPLES = ["Hello Commander", "Mission start", "We need to move quickly", "Thank you", "This area is dangerous"]
def offline_stub(text: str) -> str: return f"[stub-id] {text}"
def main() -> int:
    from translation_engine import get_engine
    eng = get_engine(BASE_DIR, offline_stub, logger=lambda *_: None)
    rows = []
    for sample in SAMPLES:
        t0 = time.perf_counter(); out, meta = eng.translate(sample)
        rows.append({"source": sample, "out": out, "ms": round((time.perf_counter()-t0)*1000,2), "meta": meta})
    report = {"version": "v7.9", "samples": rows, "avg_ms": round(sum(r["ms"] for r in rows)/max(1,len(rows)),2)}
    write_status("benchmark_translation", report, BASE_DIR)
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
