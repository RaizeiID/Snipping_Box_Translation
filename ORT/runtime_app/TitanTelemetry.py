# -*- coding: utf-8 -*-
"""TitanTelemetry.py

Version : 1.0.2
Updated : 2026-01-06

- Menyimpan: launches, last_used, ms_samples (cap 500), avg.
- record_translation_ms() menerima argumen optional `source` dan kwargs (compat).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


@dataclass
class ModelStats:
    launches: int = 0
    last_used: str = ""
    ms_samples: List[int] = None

    def __post_init__(self) -> None:
        if self.ms_samples is None:
            self.ms_samples = []


class Telemetry:
    def __init__(self, path: str | Path = "titan_usage_stats.json") -> None:
        self.path = Path(path)
        self.data: Dict[str, Any] = {"models": {}, "global": {}}
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.data = {"models": {}, "global": {}}

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _get_model(self, key: str) -> Dict[str, Any]:
        models = self.data.setdefault("models", {})
        if key not in models:
            models[key] = asdict(ModelStats())
            models[key]["ms_samples"] = []
        return models[key]

    def record_launch(self, model_key: str) -> None:
        m = self._get_model(model_key)
        m["launches"] = int(m.get("launches", 0)) + 1
        m["last_used"] = _now_iso()
        g = self.data.setdefault("global", {})
        g["last_model"] = model_key
        g["last_used"] = m["last_used"]
        self.save()

    def record_translation_ms(self, ms: int, model_key: str, source: str = "unknown", **kwargs: Any) -> None:
        try:
            m = self._get_model(model_key)
            ms_list = list(m.get("ms_samples") or [])
            ms_list.append(int(ms))
            if len(ms_list) > 500:
                ms_list = ms_list[-500:]
            m["ms_samples"] = ms_list
            m["last_ms_source"] = str(source)
            self.save()
        except Exception:
            pass

    def avg_for(self, model_key: str) -> Optional[float]:
        m = (self.data.get("models") or {}).get(model_key)
        if not m:
            return None
        ms = m.get("ms_samples") or []
        if not ms:
            return None
        try:
            return sum(ms) / max(1, len(ms))
        except Exception:
            return None

    def summarize(self) -> Dict[str, Any]:
        models = self.data.get("models") or {}
        last_model = (self.data.get("global") or {}).get("last_model")
        most_used = None
        most_n = -1
        for k, v in models.items():
            n = int(v.get("launches", 0))
            if n > most_n:
                most_used, most_n = k, n
        return {
            "last_model": last_model,
            "last_used": (self.data.get("global") or {}).get("last_used", ""),
            "most_used": most_used,
            "most_used_launches": most_n if most_n >= 0 else 0,
        }

    def stats_rows(self):
        rows = []
        for k, v in (self.data.get("models") or {}).items():
            ms = v.get("ms_samples") or []
            avg = (sum(ms) / max(1, len(ms))) if ms else None
            rows.append({
                "key": k,
                "launches": int(v.get("launches", 0)),
                "last_used": str(v.get("last_used", "")),
                "avg_ms": avg,
                "samples": len(ms),
            })
        rows.sort(key=lambda r: (-r["launches"], r["key"]))
        return rows
