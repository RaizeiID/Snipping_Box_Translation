from __future__ import annotations

"""ORT v8.8.8 Long Session Analyzer.

Convenience wrapper around offline_replay_benchmark_v8_8_8.py that writes
Markdown recommendations for long story sessions.
"""

from pathlib import Path
import json
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/long_session_analyzer_v8_8_8.py <log1.txt> [log2.txt ...]")
        raise SystemExit(2)
    out_json = Path("reports/replay_analysis/session_summary_v8_8_8.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, "tools/offline_replay_benchmark_v8_8_8.py", *sys.argv[1:], "--out", str(out_json)])
    data = json.loads(out_json.read_text(encoding="utf-8"))
    md = ["# ORT v8.8.8 Long Session Analyzer", "", "This report is generated from logs and is used to find patterns, not memorize story lines.", ""]
    for report in data["reports"]:
        md.append(f"## {report['file']}")
        md.append("")
        md.append("### Metrics")
        for k, v in sorted(report["metrics"].items()):
            md.append(f"- {k}: {v}")
        md.append("")
        md.append("### Latency")
        for k, v in report.get("latency", {}).items():
            md.append(f"- {k}: {v}")
        md.append("")
        md.append("### Recommendations")
        for rec in report.get("recommendations", []) or ["No major replay recommendation generated."]:
            md.append(f"- {rec}")
        md.append("")
    out_md = Path("reports/replay_analysis/recommendations_v8_8_8.md")
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"v8.8.8 long session analyzer complete: {out_md}")


if __name__ == "__main__":
    main()
