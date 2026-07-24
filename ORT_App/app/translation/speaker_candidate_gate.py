from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path

# v8.1: stronger gate to avoid OCR noise becoming permanent NPC names.
STOP = {
    "the", "a", "an", "their", "there", "this", "that", "these", "those", "your", "you", "i", "we",
    "rashly", "along", "once", "again", "after", "before", "because", "while", "with", "without",
    "clack", "paradeus", "helens", "helen's", "tothat", "click", "system", "warning", "loading",
    "contrary", "seemingly", "unsure", "seeing", "suddenly", "however", "meanwhile",
    "after", "before", "while", "though", "although", "because", "perhaps", "maybe",
    "voice", "big", "ahem", "thanks", "cold", "heartless", "rest", "place",
    "rows", "alvaand", "chiloveigs", "chiloveig's", "thearmor", "vaymastina", "housekeeper", "young", "max", "level", "loading",
    "familiar", "shortly", "afaint", "ablade", "arasping", "facing", "conference", "official",
    "character", "girls", "programming", "team", "video", "sunborn", "designer", "audio",
    # v8.7.1 false-speaker forms seen in GFL2 IDN sessions.
    "still", "feeling", "foreven", "late", "noticing", "betterto", "haha", "reasons", "allow",
    "pretty", "sensing", "every", "hereyes", "her", "tillthe", "ah", "ail", "ohnoare",
    "another", "decommisslon", "asimple", "yeah", "ten", "soshes", "dontworry",
    "decommission", "analarm", "don't", "finally", "gazing", "griffin's",
}
ROLE_ALLOW = {"Narrator", "Operator", "Presenter", "Announcer", "System"}
GFL2_SEEDED = {"DP-12", "KSVK"}
NARRATIVE_STARTERS = {"Contrary", "Seemingly", "Unsure", "Seeing", "Suddenly", "However", "Meanwhile", "After", "Before", "While", "Though", "Although", "Because", "Perhaps", "Maybe"}
NOISE_RE = re.compile(r"[|川州讦让舒岛叭贸]{1,}|\d{2,}|[@#$%^*_+=~`]|LT(?:S|F)[A-Z0-9]{2,}")


def _clean_name(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_\-' ]", "", str(name or "")).strip()
    n = re.sub(r"\s{2,}", " ", n)
    return n


def is_valid_speaker_candidate(name: str) -> tuple[bool, str]:
    import os
    strictness = os.environ.get("ORT_SPEAKER_GATE_STRICTNESS", "normal").lower()
    n = _clean_name(name)
    low = n.lower()
    if n.upper() in GFL2_SEEDED:
        return True, "gfl2_seeded_speaker"
    try:
        if os.environ.get("ORT_GFL_SPEAKER_ROI", "0") == "1":
            from app.games.gfl_profile import is_seeded_speaker
            if is_seeded_speaker(n):
                return True, "gfl_seeded_speaker"
    except Exception:
        pass
    if len(n) < 2:
        return False, "too_short"
    if low in STOP:
        return False, "blocked_common_or_noise"
    if n in NARRATIVE_STARTERS:
        return False, "narrative_starter_not_speaker"
    if NOISE_RE.search(n):
        return False, "symbol_or_digit_noise"
    parts = n.split()
    if strictness == "strict" and len(parts) > 1 and n not in ROLE_ALLOW and not any(p in {"Young", "Little", "Miss", "Mr"} for p in parts[:1]):
        return False, "strict_multiword_candidate"
    if len(parts) > 2 and n not in ROLE_ALLOW:
        return False, "too_many_words"
    if n.endswith("'s") or low.endswith("s'") or "'s" in low:
        return False, "possessive_not_speaker"
    if len(n) <= 3 and n.upper() == n and n not in {"UMP", "AR", "AK"}:
        return False, "short_upper_noise"
    if len(parts) == 1 and low.endswith(("ly", "ing", "ed")) and n not in ROLE_ALLOW:
        return False, "ordinary_word_shape"
    if not n[:1].isupper() and not n.isupper():
        return False, "not_name_case"
    letters = re.findall(r"[A-Za-z]", n)
    if letters and not re.search(r"[aeiouAEIOU]", "".join(letters)) and n not in ROLE_ALLOW:
        return False, "no_vowel_noise"
    return True, "ok"


def record_candidate(base_dir: str | Path, name: str, context: str = "") -> dict:
    base = Path(base_dir)
    p = base / "runtime_name_candidates.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    ok, reason = is_valid_speaker_candidate(name)
    key = _clean_name(name)
    try:
        from app.learning.learning_quarantine import looks_like_learning_noise
        if looks_like_learning_noise(key):
            ok, reason = False, "learning_quarantine_noise"
    except Exception:
        pass
    item = data.get(key, {"name": key, "hits": 0, "contexts": [], "valid_hint": ok, "reason": reason})
    item["hits"] = int(item.get("hits", 0)) + 1
    item["last_seen"] = time.time()
    item["valid_hint"] = ok
    item["reason"] = reason
    if context and len(item.get("contexts", [])) < 5:
        item.setdefault("contexts", []).append(context[:160])
    if key:
        data[key] = item
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return item
