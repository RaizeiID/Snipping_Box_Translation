"""ORT Translation v7.9 OCR metrics helpers."""
from __future__ import annotations
import time
from contextlib import contextmanager
from typing import Dict

@contextmanager
def timer_ms():
    start = time.perf_counter()
    box = {"ms": 0.0}
    try:
        yield box
    finally:
        box["ms"] = round((time.perf_counter() - start) * 1000.0, 3)

def normalize_ocr_metrics(**values) -> Dict[str, float | int | str]:
    out = {}
    for k, v in values.items():
        try:
            out[k] = round(float(v), 3)
        except Exception:
            out[k] = v
    return out
