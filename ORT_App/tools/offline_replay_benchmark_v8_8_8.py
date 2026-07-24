from __future__ import annotations

"""ORT v8.8.8 Offline Replay Benchmark.

Reads ORT text logs and produces summary metrics. It does not memorize story
sentences; it extracts failure patterns for future rule candidates.
"""

from pathlib import Path
import argparse
import json
import re
from collections import Counter, defaultdict
from statistics import median


UI_PATTERNS = [
    "Loading Resources", "Combat Effectiveness", "Combat Start", "Clickanywhere",
    "Click anywhere", "Collect", "Heroic Mode", "Story Supply"
]


def parse_latency(line: str) -> int | None:
    m = re.search(r"\|\s*(\d+)ms\s*\|", line)
    return int(m.group(1)) if m else None


def analyze_log(path: Path) -> dict:
    metrics = Counter()
    latencies = []
    ocr_samples = []
    problem_segments = []
    prediction = Counter()

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    last_ocr = ""
    for idx, line in enumerate(lines):
        if "[OCR]" in line:
            metrics["ocr_lines"] += 1
            last_ocr = line.split("[OCR]", 1)[-1].strip()
            if len(ocr_samples) < 30:
                ocr_samples.append(last_ocr)
            if any(p.lower() in last_ocr.lower() for p in UI_PATTERNS):
                metrics["ui_leakage_candidates"] += 1
                problem_segments.append({"line": idx + 1, "type": "ui_leakage_candidate", "text": last_ocr[:200]})
            if re.search(r"\b(repaint_last_good|defer_clear)\b", line):
                metrics["ocr_with_repaint_marker"] += 1

        if "[PIPE]" in line:
            metrics["pipe_lines"] += 1
            latency = parse_latency(line)
            if latency is not None:
                latencies.append(latency)
                if latency >= 1000:
                    metrics["slow_pipe_over_1000ms"] += 1
                    problem_segments.append({"line": idx + 1, "type": "slow_pipe", "latency_ms": latency, "context": last_ocr[:180]})
            if "hold=" in line:
                metrics["holds"] += 1
            if "output_coverage_too_low" in line:
                metrics["output_coverage_too_low"] += 1
            if "HIT_STABLE_FINAL" in line or "naturalized_cache" in line:
                metrics["cache_hits"] += 1

        if "[COMMIT" in line:
            metrics["commit_lines"] += 1
            if "repaint_last_good" in line:
                metrics["repaint_last_good"] += 1
            if "defer_clear" in line:
                metrics["defer_clear"] += 1
            if "suppress" in line:
                metrics["commit_suppress"] += 1

        if "[PREDICT" in line:
            metrics["prediction_lines"] += 1
            if "Hell -> Heli" in line:
                metrics["false_prediction_spam"] += 1
                problem_segments.append({"line": idx + 1, "type": "false_prediction_spam", "context": line[:220]})
            if "label=Green" in line:
                prediction["green"] += 1
            elif "label=Yellow" in line:
                prediction["yellow"] += 1
            elif "label=Red" in line:
                prediction["red"] += 1

        if "[FILTER" in line:
            metrics["ui_filtered_before_translate"] += 1
        if "[TIMEOUT" in line and "emergency_commit" in line:
            metrics["emergency_commit_used"] += 1

    latency_stats = {}
    if latencies:
        sorted_l = sorted(latencies)
        latency_stats = {
            "count": len(latencies),
            "median_ms": median(sorted_l),
            "p95_ms": sorted_l[int(0.95 * (len(sorted_l) - 1))],
            "max_ms": max(sorted_l),
        }

    derived = {
        "repaint_per_commit": (metrics["repaint_last_good"] / metrics["commit_lines"]) if metrics["commit_lines"] else 0.0,
        "ui_leakage_rate": (metrics["ui_leakage_candidates"] / metrics["ocr_lines"]) if metrics["ocr_lines"] else 0.0,
        "hold_rate": (metrics["holds"] / metrics["pipe_lines"]) if metrics["pipe_lines"] else 0.0,
    }

    recommendations = []
    if metrics["ui_leakage_candidates"] > metrics["ui_filtered_before_translate"]:
        recommendations.append("Strengthen UI/Loading/Battle Text Filter before translate/cache.")
    if derived["repaint_per_commit"] > 0.35:
        recommendations.append("Stale Last-Good Limit may still be too permissive.")
    if metrics["output_coverage_too_low"]:
        recommendations.append("Review output coverage gate and emergency commit thresholds.")
    if metrics["slow_pipe_over_1000ms"]:
        recommendations.append("Investigate slow non-dialog or heavy cache misses around listed timestamps.")
    if metrics["false_prediction_spam"]:
        recommendations.append("Fix prediction guard false positives; alias should only fire when OCR text contains it.")

    return {
        "file": str(path),
        "metrics": dict(metrics),
        "latency": latency_stats,
        "prediction": dict(prediction),
        "derived": derived,
        "sample_ocr": ocr_samples,
        "problem_segments": problem_segments[:80],
        "recommendations": recommendations,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", help="ORT text log files")
    ap.add_argument("--out", default="replay_analysis_v8_8_8.json")
    args = ap.parse_args()

    reports = [analyze_log(Path(x)) for x in args.logs]
    merged = {
        "version": "v8.8.8",
        "note": "Offline replay benchmark extracts failure patterns, not memorized story lines.",
        "reports": reports,
    }
    Path(args.out).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"v8.8.8 offline replay benchmark complete: {args.out}")


if __name__ == "__main__":
    main()
