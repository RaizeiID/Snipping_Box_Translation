"""Mine fresh speaker/term candidates from recent session events without auto-promotion.

The miner deliberately produces a review queue only. It scans the most recent log
files by default so an accumulated project archive cannot freeze diagnostics; the
limits can be raised explicitly for offline audits.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

PREFIX = re.compile(r"^\s*([A-Z][A-Za-z0-9' -]{1,32}?)(?:\s{2,}|[:：]\s+|\s+(?=[A-Z][a-z]{2,}\b))")
COMMANDER_EXCLUSIONS = {"vilyz", "villyz", "vilyz", "viz", "viyz", "viiyz", "viilyz", "arvita id", "atvita id"}
STOP_NOISE = {"the", "she", "he", "you", "news", "another", "asfor", "too many", "late at night", "thats right"}


def _known_names(base: Path) -> set[str]:
    known: set[str] = set()
    try:
        cat = json.loads((base / "configs/reference_roster_catalog_v8_7_3.json").read_text(encoding="utf-8"))
        known |= {str(x.get("display_name", "")).casefold() for x in cat["games"]["GFL2_EXILIUM"]["entries"]}
    except Exception:
        pass
    try:
        defaults = json.loads((base / "configs/speaker_registry_v2.defaults.json").read_text(encoding="utf-8"))
        game = defaults.get("games", {}).get("GFL2_EXILIUM", {})
        for bucket in ("protected_character", "approved_role_speaker", "user_configured"):
            for row in game.get(bucket, []):
                known.add(str(row.get("display_name", "")).casefold())
    except Exception:
        pass
    return known


def _recent_logs(base: Path, max_files: int) -> list[Path]:
    files = list((base / "logs").glob("session_*_events.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files[:max(1, max_files)]


def mine(base_dir: str | Path = ".", *, max_files: int = 30, max_lines_per_file: int = 250_000, min_hits: int = 3) -> dict:
    base = Path(base_dir).resolve()
    known = _known_names(base)
    counts: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}
    files = _recent_logs(base, max_files)
    parsed_lines = 0
    for path in files:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines_per_file:
                    break
                parsed_lines += 1
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                # Only use the purpose-built rejected Name ROI evidence. Mining body/source
                # text yields narrative fragments rather than candidate speaker names.
                if obj.get("type") != "GFL2_NAME_ROI_REJECTED":
                    continue
                payload = obj.get("payload") or {}
                candidate = " ".join(str(payload.get("raw_name_roi", "")).strip().split())
                key = candidate.casefold()
                if not candidate or key in known or key in COMMANDER_EXCLUSIONS or key in STOP_NOISE:
                    continue
                if len(candidate) > 38 or any(ch in candidate for ch in ".,!?;:"):
                    continue
                counts[candidate] += 1
                sources.setdefault(candidate, set()).add(path.name)
    rows = [
        {"candidate": name, "hits": hits, "sessions": sorted(sources[name]), "status": "pending_manual_review", "auto_live": False}
        for name, hits in counts.most_common() if hits >= min_hits
    ]
    return {
        "version": "v8.7.9",
        "generated_at": time.time(),
        "policy": "Rejected Name ROI mining only; no auto-promotion to speaker/term; Commander profile names excluded globally.",
        "scan": {"source_event": "GFL2_NAME_ROI_REJECTED", "max_files": max_files, "max_lines_per_file": max_lines_per_file, "files_scanned": len(files), "lines_parsed": parsed_lines},
        "candidates": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Mine recent OCR speaker candidates into a review-only report.")
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--max-files", type=int, default=30)
    ap.add_argument("--max-lines-per-file", type=int, default=250_000)
    ap.add_argument("--min-hits", type=int, default=3)
    args = ap.parse_args()
    base = Path(args.base_dir).resolve()
    data = mine(base, max_files=args.max_files, max_lines_per_file=args.max_lines_per_file, min_hits=args.min_hits)
    out = base / "reports" / f"v8_7_9_candidate_mining_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Candidate mining report: {out}")
    print(f"Files scanned: {data['scan']['files_scanned']} | Lines parsed: {data['scan']['lines_parsed']} | Candidates: {len(data['candidates'])}")
    for row in data["candidates"][:20]:
        print(f"- {row['candidate']}: {row['hits']} (review-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
