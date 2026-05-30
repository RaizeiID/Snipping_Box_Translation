# titan_traininglog.py
import os
import json
import time
import threading
from typing import Any, Dict, Optional, Callable


class TrainingLogCore:
    """
    Online/offline 'training' log (bukan training bobot model).
    Menyimpan sample untuk:
    - analisa kualitas
    - fine-tune nanti (offline)
    - kamus/glossary curation

    Output: training_log.jsonl
    """

    def __init__(self, base_dir: str, log_fn: Callable[[str], None], buffer_size: int = 30):
        self.log = log_fn
        self.path = os.path.join(base_dir, "training_log.jsonl")
        self.buffer_size = max(10, int(buffer_size))
        self._lock = threading.RLock()
        self._buf = []

    def record(self, mode: str, src: str, norm: str, out: str, meta: Optional[Dict[str, Any]] = None):
        if not src or not out:
            return
        item = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "src": src,
            "norm": norm,
            "out": out,
            "meta": meta or {},
        }
        with self._lock:
            self._buf.append(item)
            if len(self._buf) >= self.buffer_size:
                self.flush("auto")

    def flush(self, reason="flush"):
        with self._lock:
            if not self._buf:
                return
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    for item in self._buf:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                self._buf.clear()
                self.log(f"[LEARN] training_log flush ({reason})")
            except Exception as e:
                self.log(f"[LEARN] training_log flush failed: {e}")
