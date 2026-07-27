from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent / "data" / "gfl2_exilium_registry.json"


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _alias_rows() -> list[tuple[str, str, str, str]]:
    registry = load_registry()
    rows: list[tuple[str, str, str, str]] = []
    for group_name in ("characters", "unique_terms"):
        entity_type = "character" if group_name == "characters" else "unique_term"
        for item in registry[group_name]:
            canonical = str(item["canonical"])
            role = str(item.get("role") or item.get("type") or "")
            rows.append((canonical, canonical, entity_type, role))
            for alias in item.get("aliases", []):
                rows.append((str(alias), canonical, entity_type, role))
    rows.sort(key=lambda row: len(row[0]), reverse=True)
    return rows


def _replace_alias(text: str, alias: str, canonical: str) -> tuple[str, int]:
    escaped = re.escape(alias)
    if re.fullmatch(r"[A-Za-z0-9 .'-]+", alias):
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    else:
        pattern = escaped
    return re.subn(pattern, canonical, text, flags=re.IGNORECASE)


def normalize_domain_text(value: Any) -> tuple[str, list[dict[str, str]]]:
    text = " ".join(str(value or "").strip().split())
    matches: list[dict[str, str]] = []
    if not text:
        return text, matches

    seen: set[tuple[str, str]] = set()
    for alias, canonical, entity_type, role in _alias_rows():
        updated, count = _replace_alias(text, alias, canonical)
        if count:
            text = updated
            key = (canonical, entity_type)
            if key not in seen:
                seen.add(key)
                matches.append({
                    "canonical": canonical,
                    "type": entity_type,
                    "role": role,
                    "matched_alias": alias,
                })
    return text, matches


def normalize_asr_text(value: Any) -> tuple[str, list[dict[str, str]]]:
    return normalize_domain_text(value)


def normalize_ocr_text(value: Any) -> tuple[str, list[dict[str, str]]]:
    return normalize_domain_text(value)


def protected_terms() -> set[str]:
    registry = load_registry()
    return {
        str(item["canonical"])
        for item in registry["unique_terms"]
        if item.get("translate") is False
    }
