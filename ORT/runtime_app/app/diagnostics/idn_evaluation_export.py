"""v8.7.8 opt-in-by-default local evaluation export for IDN quality analysis."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class IDNEvaluationExporter:
    def __init__(self, base_dir: str | os.PathLike[str], enabled: bool | None = None) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.enabled = (os.environ.get("ORT_IDN_EVAL_EXPORT", "1") != "0") if enabled is None else bool(enabled)
        self.path = self.base_dir / "logs" / "idn_evaluation_v8_7_8.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, **payload: Any) -> None:
        if not self.enabled:
            return
        try:
            from app.identity.speaker_registry import has_internal_entity_token
            if has_internal_entity_token(str(payload.get("backend_output", ""))) or has_internal_entity_token(str(payload.get("final_idn_output", ""))):
                return
        except Exception:
            pass
        # v8.7.8: rejected semantic output is retained only as diagnostic telemetry;
        # overlay/cache/training gates remain responsible for preventing reuse.
        item = {"ts": time.time(), "version": "v8.7.8", **payload}
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            return
