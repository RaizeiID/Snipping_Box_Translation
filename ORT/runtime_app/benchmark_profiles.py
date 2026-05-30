"""v7.9 profile comparison helper for GFL2/WUWA/model strategies."""
from __future__ import annotations
import json
from pathlib import Path
from model_strategy import build_strategy
from status_manager import write_status
BASE_DIR = Path(__file__).resolve().parent
CASES = [
    ("v2", "ORTCore V2", "normal", "V2", "GFL2_EXILIUM"),
    ("idn_v5", "ORTCore IDN V5", "idn", "V5", "GFL2_EXILIUM"),
    ("lite_idn_v2", "ORTCore Lite IDN V2", "lite_idn", "V2", "WUWA"),
    ("fast_v1", "ORTCore Fast V1", "fast", "FAST", "WUWA"),
    ("v2", "ORTCore V2", "normal", "V2", "WUWA"),
]

def main() -> int:
    rows = []
    for key, title, group, family, game in CASES:
        st = build_strategy(model_key=key, model_title=title, group=group, family=family, game=game, policy="auto", requested_engine="hybrid", requested_mode="interval")
        rows.append({"case": f"{game}+{title}", "strategy": st.strategy_name, "engine": st.recommended_engine, "interval": st.interval_floor_ms, "ocr": st.ocr_resolution_percent, "queue": st.queue_max, "core_profile": st.core_profile, "online": st.online_policy, "reason": st.reason})
    report = {"version": "v7.9", "profiles": rows}
    write_status("benchmark_profiles", report, BASE_DIR)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
