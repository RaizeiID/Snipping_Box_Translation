from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json

def detect_conflicts(state: Dict[str, Any] | None = None) -> List[str]:
    s = state or {}
    game = str(s.get("game", "")).upper()
    engine = str(s.get("engine") or s.get("active_engine") or "").lower()
    group = str(s.get("model_group") or s.get("group") or "").lower()
    fast = str(s.get("fast_engine_status") or "").upper()
    online = bool(s.get("online_assist"))
    out: List[str] = []
    if game in {"WUWA", "WUTHERING_WAVES"} and engine in {"gpu", "hybrid"} and "lite" not in group:
        out.append("WUWA + GPU/Hybrid non-Lite dapat menekan VRAM. Rekomendasi: CPU + Lite/Lite IDN.")
    if online and game in {"WUWA", "WUTHERING_WAVES"}:
        out.append("Online Assist aktif pada game berat. Rekomendasi: OFF kecuali user sengaja manual.")
    if "FAST" in group.upper() and fast and "ACTIVE" not in fast:
        out.append("Fast model dipilih tetapi Fast Engine belum ACTIVE; runtime fallback Argos.")
    return out

def detect_conflicts_text(base_dir: str | Path | None = None) -> str:
    base = Path(base_dir or Path(__file__).resolve().parents[2])
    state = {}
    for rel in ["configs/app_state.json", "status/strategy.json", "status/fast_engine.json", "status/online_assist.json"]:
        try:
            p = base / rel
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict): state.update(data)
        except Exception:
            pass
    conflicts = detect_conflicts(state)
    if not conflicts:
        return "Conflict Detector v8.1\nStatus: tidak ada konflik besar terdeteksi."
    return "Conflict Detector v8.1\nStatus: perlu perhatian\n\n" + "\n".join(f"- {x}" for x in conflicts)
