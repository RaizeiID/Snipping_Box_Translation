"""ORT v9.0.7 R20 -- remember which combinations the player actually keeps.

`user_intent` reads the goal of ONE combination. This records them over time, so
the app can tell a habit from a one-off experiment.

The distinction that matters is **kept vs abandoned**. Picking a combination
says almost nothing -- people try things. Running it for four minutes and not
touching the knobs says a great deal. So every session stores its combination
together with how long it lasted and how it actually behaved (stale drops,
strict-CT2 holds, backend latency), and a habit is only claimed once the same
goal has been *kept* several times.

Deliberately local and boring: one JSON file, capped length, no profiling of
content. It stores which knobs were used and how the pipeline performed -- never
dialogue text, never anything about what was being translated.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

HISTORY_NAME = "intent_history.json"
MAX_ENTRIES = 200
# Below this a session is an experiment, not a preference.
KEPT_MIN_SECONDS = 90
# How many kept sessions before we are willing to call something a habit.
HABIT_MIN_SESSIONS = 3


def history_path(base_dir=None) -> Path:
    root = Path(base_dir or Path(__file__).resolve().parents[2])
    return root / "ORT" / "status" / HISTORY_NAME


@dataclass
class HabitReport:
    total_sessions: int = 0
    kept_sessions: int = 0
    dominant_goal: str = ""
    dominant_share: float = 0.0
    favourite_core: str = ""
    favourite_ladder: str = ""
    confident: bool = False
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "kept_sessions": self.kept_sessions,
            "dominant_goal": self.dominant_goal,
            "dominant_share": round(self.dominant_share, 3),
            "favourite_core": self.favourite_core,
            "favourite_ladder": self.favourite_ladder,
            "confident": self.confident,
            "notes": list(self.notes),
        }


def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
    except Exception:
        pass
    return []


def _save(path: Path, rows: List[Dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(rows[-MAX_ENTRIES:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def record_session(
    *,
    goal: str,
    core: str,
    ladder: str,
    device_resource: str,
    duration_sec: float = 0.0,
    stats: Optional[Dict[str, Any]] = None,
    started_at: float = 0.0,
    base_dir=None,
) -> Dict[str, Any]:
    """Append one finished session.

    `started_at` is passed in rather than read from the clock so a caller can
    record a session that has already ended without the timestamp drifting.
    """
    path = history_path(base_dir)
    rows = _load(path)
    stats = stats or {}
    entry = {
        "goal": str(goal or ""),
        "core": str(core or ""),
        "ladder": str(ladder or ""),
        "device_resource": str(device_resource or ""),
        "duration_sec": round(float(duration_sec or 0.0), 1),
        "kept": float(duration_sec or 0.0) >= KEPT_MIN_SECONDS,
        "started_at": float(started_at or 0.0),
        # A small, fixed set of pipeline health numbers -- never content.
        "stale_dropped": int(stats.get("stale_results_dropped", 0) or 0),
        "strict_holds": int(stats.get("strict_ct2_holds", 0) or 0),
        "overlay_committed": int(stats.get("overlay_committed", 0) or 0),
        "backend_avg_ms": int(stats.get("backend_avg_ms", 0) or 0),
    }
    rows.append(entry)
    _save(path, rows)
    return entry


def summarize(base_dir=None, rows: Optional[List[Dict[str, Any]]] = None) -> HabitReport:
    rows = rows if rows is not None else _load(history_path(base_dir))
    report = HabitReport(total_sessions=len(rows))
    kept = [r for r in rows if r.get("kept")]
    report.kept_sessions = len(kept)
    if not kept:
        report.notes.append(
            "Belum ada sesi yang dipakai cukup lama untuk dianggap kebiasaan."
        )
        return report

    def _top(field_name: str) -> tuple[str, int]:
        counts: Dict[str, int] = {}
        for row in kept:
            key = str(row.get(field_name) or "")
            if key:
                counts[key] = counts.get(key, 0) + 1
        if not counts:
            return "", 0
        best = max(counts.items(), key=lambda kv: kv[1])
        return best[0], best[1]

    goal, goal_n = _top("goal")
    report.dominant_goal = goal
    report.dominant_share = goal_n / max(1, len(kept))
    report.favourite_core = _top("core")[0]
    report.favourite_ladder = _top("ladder")[0]
    report.confident = len(kept) >= HABIT_MIN_SESSIONS and report.dominant_share >= 0.6

    # Only surface an observation when the numbers actually support it.
    if report.confident:
        report.notes.append(
            f"{goal_n} dari {len(kept)} sesi yang bertahan memakai tujuan yang sama."
        )
    else:
        report.notes.append(
            f"Baru {len(kept)} sesi bertahan; pola belum cukup kuat untuk disimpulkan."
        )

    stale = [r.get("stale_dropped", 0) for r in kept]
    holds = [r.get("strict_holds", 0) for r in kept]
    if stale and sum(stale) / len(stale) >= 40:
        report.notes.append(
            "Rata-rata banyak hasil terjemahan terbuang; kombinasi ini menuntut lebih "
            "dari yang bisa dikejar perangkat."
        )
    if holds and sum(holds) / len(holds) >= 40 and goal in ("accuracy_first", "accuracy_light"):
        report.notes.append(
            "Banyak potongan kalimat ditahan — konsisten dengan tujuan akurasi yang dipilih."
        )
    return report


def record_from_env(duration_sec: float, stats=None, environ=None, base_dir=None) -> Optional[Dict[str, Any]]:
    """Convenience wrapper for the runtime, which knows the env but not the UI."""
    env = environ if environ is not None else os.environ
    goal = env.get("ORT_INTENT_GOAL", "")
    if not goal:
        return None
    core = f"{env.get('ORT_MODEL_GROUP', '')}/{env.get('ORT_MODEL_KEY', '')}".strip("/")
    ladder = f"{env.get('ORT_RESOURCE_MODE', '')}:{env.get('ORT_RESOURCE_LEVEL', '')}".strip(":")
    return record_session(
        goal=goal,
        core=core,
        ladder=ladder,
        device_resource=env.get("ORT_DEVICE_RESOURCE", ""),
        duration_sec=duration_sec,
        stats=stats,
        base_dir=base_dir,
    )
