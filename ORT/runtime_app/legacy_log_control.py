"""ORT Translation v7.9 legacy root log control.

Legacy training_log.jsonl is OFF by default to prevent root log bloat. Use
ORT_WRITE_LEGACY_TRAINING_LOG=1 only for manual debugging.
"""
from __future__ import annotations
import os

def legacy_training_log_enabled() -> bool:
    return os.environ.get("ORT_WRITE_LEGACY_TRAINING_LOG", "0").strip().lower() in {"1", "true", "yes", "on"}
