from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

NOISE_RE = re.compile(r"(?:[川州讦让舒岛叭贸]{1,}|\b[A-Z]*\d{2,}[A-Z0-9]*\b|[~`@#$%^*_+=]{1,}|\bLT(?:S|F)[A-Z0-9]{2,}\b)")


GFL2_SEEDED = {"DP-12", "KSVK"}
GFL2_FALSE_SPEAKERS = {"still", "feeling", "foreven", "late", "noticing", "betterto", "haha", "reasons", "allow", "pretty", "sensing", "every", "hereyes", "her", "tillthe", "ah", "ail", "ohnoare", "another", "decommisslon", "asimple", "yeah", "ten", "soshes", "dontworry", "decommission", "analarm", "don't", "finally", "gazing", "griffin's"}

def looks_like_learning_noise(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    if os.environ.get("ORT_GFL2_SPEAKER_GATE", "0") == "1":
        if s.upper() in GFL2_SEEDED:
            return False
        if s.lower() in GFL2_FALSE_SPEAKERS:
            return True
    try:
        if os.environ.get("ORT_GFL_SPEAKER_ROI", "0") == "1":
            from app.games.gfl_profile import is_non_dialog_text, is_seeded_speaker
            if is_seeded_speaker(s):
                return False
            if is_non_dialog_text(s) or s.lower() in {"familiar", "shortly", "facing", "conference", "official", "character", "programming", "sunborn", "video", "team"}:
                return True
    except Exception:
        pass
    if NOISE_RE.search(s):
        return True
    letters = re.findall(r"[A-Za-z]", s)
    if letters and len(re.findall(r"[0-9]", s)) / max(1, len(letters)) > 0.35:
        return True
    if len(s) <= 3 and not s.isalpha():
        return True
    return False


def record_quarantine(base_dir: str | Path, kind: str, value: str, reason: str = "", context: str = "") -> Dict[str, Any]:
    base = Path(base_dir)
    path = base / "status" / "learning_quarantine.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {"items": {}}
        if not isinstance(data, dict):
            data = {"items": {}}
    except Exception:
        data = {"items": {}}
    items = data.setdefault("items", {})
    key = f"{kind}:{value}"[:180]
    item = items.get(key, {"kind": kind, "value": value, "hits": 0, "contexts": []})
    item["hits"] = int(item.get("hits", 0)) + 1
    item["reason"] = reason
    item["last_seen"] = time.time()
    if context and len(item.get("contexts", [])) < 4:
        item.setdefault("contexts", []).append(context[:180])
    items[key] = item
    data["version"] = "v8.7.2"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def should_promote_learning(base_dir: str | Path, kind: str, value: str, *, min_hits: int = 2, context: str = "") -> tuple[bool, str]:
    if looks_like_learning_noise(value):
        record_quarantine(base_dir, kind, value, "noise_shape", context)
        return False, "learning_quarantine_noise"
    item = record_quarantine(base_dir, kind, value, "candidate", context)
    if int(item.get("hits", 0)) < int(min_hits):
        return False, f"learning_quarantine_wait_hits:{item.get('hits', 0)}/{min_hits}"
    return True, "ok"
