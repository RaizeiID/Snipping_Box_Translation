# TITAN_LEARN.py
# ==============================================================================
# TITAN LEARN - Apply Feedback -> Translation Memory (Persistent Learning)
#
# What it does:
# - Reads feedback_log.json (from FeedbackCollectorCore) if exists
# - Applies user corrections into translation_memory.json (TITAN cache)
# - Appends samples into training_log.jsonl for later analysis
# - Marks entries as "applied" (keeps history, does not delete)
#
# Usage:
#   python TITAN_LEARN.py
#   python TITAN_LEARN.py --dry-run
# ==============================================================================

import os
import sys
import json
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_log.json")
MEM_FILE = os.path.join(BASE_DIR, "translation_memory.json")
TRAIN_LOG_FILE = os.path.join(BASE_DIR, "training_log.jsonl")

def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg: str):
    print(f"[{ts()}] {msg}", flush=True)

def _safe_read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log(f"[WARN] read failed: {os.path.basename(path)} | {e}")
    return default

def _safe_write_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"[ERR] write failed: {os.path.basename(path)} | {e}")
        return False

def _append_jsonl(path: str, item: dict):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:
        pass

def main():
    dry = "--dry-run" in [a.lower() for a in sys.argv[1:]]
    fb = _safe_read_json(FEEDBACK_FILE, {"pending_reviews": [], "applied": []})
    pending = fb.get("pending_reviews", []) or []

    if not pending:
        log("[LEARN] No pending feedback found. (feedback_log.json empty)")
        return 0

    mem = _safe_read_json(MEM_FILE, {})
    if not isinstance(mem, dict):
        mem = {}

    applied_count = 0
    skipped = 0

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for entry in pending:
        try:
            original = (entry.get("original") or "").strip()
            corr = (entry.get("user_correction") or "").strip()
            wrong = (entry.get("wrong_translation") or "").strip()

            if not original or not corr:
                skipped += 1
                continue

            # Apply correction to translation memory
            if mem.get(original) != corr:
                if not dry:
                    mem[original] = corr
                applied_count += 1

            # Write training sample line (jsonl)
            sample = {
                "ts": now_str,
                "mode": "FEEDBACK",
                "src": original,
                "out": corr,
                "meta": {
                    "wrong": wrong,
                    "source": "feedback_log"
                }
            }
            if not dry:
                _append_jsonl(TRAIN_LOG_FILE, sample)

            # Mark entry as applied (keep full history)
            entry["applied_ts"] = now_str
            entry["applied"] = True

        except Exception:
            skipped += 1

    if not dry:
        # move all pending to applied history
        fb.setdefault("applied", [])
        fb["applied"].extend(pending)
        fb["pending_reviews"] = []
        _safe_write_json(MEM_FILE, mem)
        _safe_write_json(FEEDBACK_FILE, fb)

    log(f"[LEARN] {'DRY-RUN ' if dry else ''}Applied: {applied_count} | Skipped: {skipped}")
    log(f"[LEARN] Memory: {os.path.basename(MEM_FILE)} | Training: {os.path.basename(TRAIN_LOG_FILE)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
