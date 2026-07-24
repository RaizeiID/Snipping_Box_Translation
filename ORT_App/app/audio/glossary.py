from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=12)
def load_audio_glossary(game: str) -> dict:
    game_key = str(game or "CUSTOM").strip().upper()
    path = ROOT / "profiles" / "games" / game_key / "audio_glossary.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def apply_audio_glossary(text: str, game: str) -> tuple[str, list[dict]]:
    clean = " ".join(str(text or "").split())
    payload = load_audio_glossary(str(game or "CUSTOM").upper())
    aliases = payload.get("asr_aliases") or {}
    hits: list[dict] = []
    for raw, canonical in aliases.items():
        if not raw or not canonical:
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(str(raw))}(?![A-Za-z0-9])", re.I)
        if pattern.search(clean):
            clean = pattern.sub(str(canonical), clean)
            hits.append({"raw": str(raw), "canonical": str(canonical)})
    return clean, hits

