from __future__ import annotations
import hashlib, time

def make_correlation_id(text: str = "", prefix: str = "evt") -> str:
    bucket = int(time.time() * 1000)
    h = hashlib.sha1((str(text)[:160] + str(bucket // 250)).encode("utf-8", "ignore")).hexdigest()[:10]
    return f"{prefix}-{bucket}-{h}"
