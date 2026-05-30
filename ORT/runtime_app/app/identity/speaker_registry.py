"""v8.7.6 trusted speaker registry, verified exact speakers, and compatibility guards.

This module deliberately separates the verified *reference catalog* from the live
*active speaker registry*. A name may be known/protected during translation
without being allowed to become an orange speaker label automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import re
import shutil
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs" / "reference_roster_catalog_v8_7_3.json"
DEFAULTS_PATH = ROOT / "configs" / "speaker_registry_v2.defaults.json"
REGISTRY_PATH = ROOT / "speaker_registry_v2.json"
LEGACY_STORE_PATH = ROOT / "data_processing_store.json"
SCHEMA_VERSION = "v8_7_8_faithfulness_v2_strict_ct2_registry_v6"
INTERNAL_TOKEN_RE = re.compile(
    r"(?:__\s*)?ORT\s*[_ \-]*\s*(?:ENTITY|BKEND|BKED|BEND|BACKEND)"
    r"(?:\s*[_ \-]*\s*\d{0,4})?(?:\s*__)?",
    re.I,
)

CATEGORY_KEYS = (
    "protected_character", "verified_character_speaker_exact", "user_configured", "approved_role_speaker",
    "reviewed_alias", "unsorted_protected", "pending_session_candidate",
    "legacy_untrusted", "special_terms", "blacklist", "original_identity_map",
)
FALSE_LEGACY_KEYS = {
    "dontworry", "hereyes", "asimple", "noticing", "dp", "dp", "griffins",
    "tillthe", "sensing", "betterto", "decommission", "another", "her",
    "dont", "finally", "gazing", "reasons", "pretty", "feeling", "foreven",
}
DISTINCT_CANONICAL_PAIRS = {frozenset(("helen", "helena"))}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).strip("\"'`.,:;!?()[]{}<>|")


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _clean(text).casefold())


def _read(path: Path, default):
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return data
    except Exception:
        pass
    return default


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_catalog() -> dict:
    return _read(CATALOG_PATH, {"games": {}, "schema_version": SCHEMA_VERSION})


def _entity(name: str, category: str, *, source: str = "seed", aliases: Iterable[str] = (), faction: str = "", origin_view: str = "detail", spoiler: bool = False) -> dict:
    return {
        "canonical_id": _key(name),
        "display_name": _clean(name),
        "category": category,
        "aliases": [_clean(a) for a in aliases if _clean(a)],
        "source": source,
        "origin_view": origin_view,
        "faction": faction,
        "spoiler": bool(spoiler),
    }


def _dedupe_entities(items: Iterable[dict]) -> list[dict]:
    out, seen = [], set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("display_name", ""))
        if not name or _key(name) in seen:
            continue
        item = dict(item)
        item["display_name"] = name
        item.setdefault("canonical_id", _key(name))
        item.setdefault("aliases", [])
        item.setdefault("source", "unknown")
        item.setdefault("origin_view", "detail")
        seen.add(_key(name))
        out.append(item)
    return out


def _blank_bucket() -> dict:
    return {
        "protected_character": [], "verified_character_speaker_exact": [], "user_configured": [], "approved_role_speaker": [],
        "reviewed_alias": [], "unsorted_protected": [], "pending_session_candidate": [],
        "legacy_untrusted": [], "special_terms": [], "blacklist": [],
        "original_identity_map": {}, "spoiler_story_catalog_enabled": False,
    }


def _defaults_registry() -> dict:
    data = _read(DEFAULTS_PATH, {})
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("created_at", int(time.time()))
    data.setdefault("games", {})
    for game in ("GFL2_EXILIUM", "GFL", "WUWA", "CUSTOM"):
        base = _blank_bucket()
        base.update(data["games"].get(game, {}))
        data["games"][game] = base
    return data


def _migrate_legacy(registry: dict) -> dict:
    legacy = _read(LEGACY_STORE_PATH, {})
    catalog = load_catalog().get("games", {})
    for game, old in (legacy.items() if isinstance(legacy, dict) else []):
        if game not in registry["games"] or not isinstance(old, dict):
            continue
        bucket = registry["games"][game]
        catalog_bucket = catalog.get(game, {}) if isinstance(catalog.get(game, {}), dict) else {}
        catalog_values = list(catalog_bucket.get("reference_names", []) or [])
        catalog_values += [str(e.get("display_name", "")) for e in catalog_bucket.get("entries", []) if isinstance(e, dict)]
        catalog_keys = {_key(n) for n in catalog_values if _clean(n)}
        existing = {_key(x.get("display_name")) for cat in ("protected_character", "verified_character_speaker_exact", "user_configured", "approved_role_speaker", "unsorted_protected", "legacy_untrusted") for x in bucket.get(cat, []) if isinstance(x, dict)}
        for name in old.get("names", []) or []:
            name = _clean(name)
            if not name or _key(name) in existing:
                continue
            if _key(name) in FALSE_LEGACY_KEYS:
                bucket["legacy_untrusted"].append(_entity(name, "legacy_untrusted", source="legacy_migration"))
            elif _key(name) in catalog_keys:
                bucket["verified_character_speaker_exact"].append(_entity(name, "verified_character_speaker_exact", source="verified_catalog_migration"))
            else:
                bucket["legacy_untrusted"].append(_entity(name, "legacy_untrusted", source="legacy_review_required"))
            existing.add(_key(name))
        bucket["special_terms"] = sorted({_clean(x) for x in (bucket.get("special_terms", []) + old.get("special_words", [])) if _clean(x)}, key=str.casefold)
        bucket["blacklist"] = sorted({_clean(x) for x in (bucket.get("blacklist", []) + old.get("blacklist", [])) if _clean(x)}, key=str.casefold)
        if game == "GFL2_EXILIUM":
            bucket["original_identity_map"].update(old.get("original_names", {}) or {})
    return registry


def load_registry(*, migrate_legacy: bool = True) -> dict:
    if REGISTRY_PATH.exists():
        data = _read(REGISTRY_PATH, _defaults_registry())
    else:
        data = _defaults_registry()
        if migrate_legacy:
            data = _migrate_legacy(data)
            _write(REGISTRY_PATH, data)
    for bucket in data.get("games", {}).values():
        for cat in ("protected_character", "verified_character_speaker_exact", "user_configured", "approved_role_speaker", "unsorted_protected", "legacy_untrusted"):
            bucket[cat] = _dedupe_entities(bucket.get(cat, []))
    return data


def save_registry(data: dict) -> None:
    _write(REGISTRY_PATH, data)
    invalidate_matcher_cache()


def game_bucket(game: str) -> dict:
    data = load_registry()
    key = str(game or "CUSTOM").upper()
    return data.get("games", {}).get(key, _blank_bucket())


def active_entities(game: str, include_unsorted: bool = True) -> list[dict]:
    bucket = game_bucket(game)
    entities = bucket.get("protected_character", []) + bucket.get("user_configured", []) + bucket.get("approved_role_speaker", [])
    if include_unsorted:
        entities = entities + bucket.get("unsorted_protected", [])
    return _dedupe_entities(entities)


def trusted_speaker_names(game: str) -> list[str]:
    """Active speakers allowed to use aliases/reviewed fuzzy matching."""
    return sorted([e["display_name"] for e in active_entities(game)], key=len, reverse=True)


def verified_character_speaker_names(game: str) -> list[str]:
    """Official character names eligible for exact-only speaker labeling.

    GFL2 is enabled first because the tested story label regression occurred
    there. This does not activate fuzzy matching, candidate learning, or role
    speakers from narrative text.
    """
    game_key = str(game or "CUSTOM").upper()
    bucket = game_bucket(game_key)
    stored = [e.get("display_name", "") for e in bucket.get("verified_character_speaker_exact", []) if isinstance(e, dict)]
    if game_key == "GFL2_EXILIUM":
        stored += reference_names(game_key)
    return sorted({_clean(n) for n in stored if _clean(n)}, key=len, reverse=True)


def speaker_exact_names(game: str) -> list[str]:
    """Names safe for exact Name ROI / exact-prefix speaker detection."""
    return sorted(set(trusted_speaker_names(game)) | set(verified_character_speaker_names(game)), key=len, reverse=True)


def trusted_alias_map(game: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entity in active_entities(game):
        canonical = entity["display_name"]
        for alias in entity.get("aliases", []) or []:
            mapping[_key(alias)] = canonical
    for row in game_bucket(game).get("reviewed_alias", []) or []:
        if isinstance(row, dict) and row.get("ocr_form") and row.get("canonical_name"):
            mapping[_key(row["ocr_form"])] = _clean(row["canonical_name"])
    return mapping


def reference_names(game: str) -> list[str]:
    bucket = load_catalog().get("games", {}).get(str(game or "CUSTOM").upper(), {})
    values = list(bucket.get("reference_names", []))
    values += [str(e.get("display_name", "")) for e in bucket.get("entries", []) if isinstance(e, dict)]
    return sorted({_clean(v) for v in values if _clean(v)}, key=len, reverse=True)


@lru_cache(maxsize=12)
def _cached_protected_terms(game_key: str) -> tuple[str, ...]:
    bucket = game_bucket(game_key)
    names = reference_names(game_key) + trusted_speaker_names(game_key)
    terms = bucket.get("special_terms", []) or []
    return tuple(sorted({_clean(x) for x in names + terms if _clean(x)}, key=len, reverse=True))


def protected_terms(game: str) -> list[str]:
    return list(_cached_protected_terms(str(game or "CUSTOM").upper()))


@lru_cache(maxsize=12)
def _compiled_protected_matcher(game_key: str):
    terms = _cached_protected_terms(game_key)
    if not terms:
        return None, {}
    canonical = {name.casefold(): name for name in terms}
    parts = [re.escape(name) for name in terms]
    pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(parts) + r")(?![A-Za-z0-9])", re.I)
    return pattern, canonical


def invalidate_matcher_cache() -> None:
    _cached_protected_terms.cache_clear()
    _compiled_protected_matcher.cache_clear()


def find_protected_entities(text: str, game: str):
    pattern, canonical = _compiled_protected_matcher(str(game or "CUSTOM").upper())
    if pattern is None:
        return []
    out = []
    for match in pattern.finditer(str(text or "")):
        name = canonical.get(match.group(1).casefold(), match.group(1))
        out.append((match.start(), match.end(), name))
    return out


def has_internal_entity_token(text: str) -> bool:
    """Block any internal ORT marker, including backend-mutated variants.

    v8.7.4 caught ENTITY/BKEND but allowed Argos mutations such as BEND/BKED.
    The additional broad form intentionally favours safe fallback over ever
    showing or caching an internal implementation token.
    """
    source = str(text or "")
    generic = re.search(r"(?:__|_\s*_)\s*ORT\b|\bORT\s*[_ \-]+\s*(?:ENTITY|BKEND|BKED|BEND|BACKEND)\b", source, flags=re.I)
    return bool(INTERNAL_TOKEN_RE.search(source) or generic)


def is_distinct_conflict(a: str, b: str) -> bool:
    return frozenset((_clean(a).casefold(), _clean(b).casefold())) in DISTINCT_CANONICAL_PAIRS


def strip_matching_speaker_prefix(text: str, speaker: str, game: str = "GFL2_EXILIUM") -> tuple[str, bool]:
    """Remove duplicated speaker prefixes from body OCR.

    v8.8.2 handles uncertain/visual speaker forms such as:
    - Phaetusa(?) Stop calling me...
    - Phaetusa (?) Stop calling me...
    - [Phaetusa(?)] Stop calling me...
    while keeping the speaker label itself available for the overlay header.
    """
    body = str(text or "").strip()
    speaker = _clean(speaker)
    if not body or not speaker:
        return body, False
    uncertainty = r"(?:\s*(?:\(\s*[?？]\s*\)|[?？]))?"
    # Separator may be a colon/dash/space or just a closed uncertain marker.
    prefix = (
        r"^\s*[\[({<]?\s*" + re.escape(speaker) + uncertainty +
        r"\s*[\])}>]?\s*(?:[:：\-–—]\s*|\s+|$)"
    )
    if re.match(prefix, body, flags=re.I):
        stripped = re.sub(prefix, "", body, count=1, flags=re.I).strip()
        return stripped, True
    # Exact compact check for OCR aliases that were reviewed for the Name ROI.
    canon_key = _key(speaker)
    for alias_key, canon in trusted_alias_map(game).items():
        if _key(canon) != canon_key or not alias_key:
            continue
        alias_pattern = r"^\s*" + re.escape(alias_key) + r"(?:\s+|[:：]\s*|$)"
        compact = re.sub(r"[^A-Za-z0-9]", "", body).casefold()
        if compact.startswith(alias_key):
            # Do not destructively slice compact text; aliases are only a fallback signal.
            break
    return body, False


def add_simple_view_name(game: str, name: str) -> dict:
    data = load_registry()
    bucket = data["games"][str(game or "CUSTOM").upper()]
    name = _clean(name)
    if not name:
        return bucket
    all_keys = {_key(e["display_name"]) for e in active_entities(game)}
    if _key(name) not in all_keys:
        bucket["unsorted_protected"].append(_entity(name, "unsorted_protected", source="user_added", origin_view="simple"))
        bucket["unsorted_protected"] = _dedupe_entities(bucket["unsorted_protected"])
        save_registry(data)
    return bucket


def delete_entity(game: str, name: str) -> bool:
    data = load_registry()
    bucket = data["games"][str(game or "CUSTOM").upper()]
    k = _key(name)
    changed = False
    for cat in ("protected_character", "user_configured", "approved_role_speaker", "unsorted_protected"):
        before = len(bucket.get(cat, []))
        bucket[cat] = [e for e in bucket.get(cat, []) if _key(e.get("display_name", "")) != k]
        changed |= before != len(bucket[cat])
    if changed:
        save_registry(data)
    return changed


def migrate_unsorted_entity(game: str, name: str, target_category: str, *, faction: str = "") -> bool:
    allowed = {"protected_character", "user_configured", "approved_role_speaker"}
    if target_category not in allowed:
        return False
    data = load_registry()
    bucket = data["games"][str(game or "CUSTOM").upper()]
    k = _key(name)
    found = None
    remaining = []
    for entity in bucket.get("unsorted_protected", []):
        if _key(entity.get("display_name", "")) == k and found is None:
            found = entity
        else:
            remaining.append(entity)
    if not found:
        return False
    found = dict(found)
    found["category"] = target_category
    found["origin_view"] = "migrated_from_simple"
    found["faction"] = faction or found.get("faction", "")
    bucket["unsorted_protected"] = remaining
    bucket[target_category].append(found)
    bucket[target_category] = _dedupe_entities(bucket[target_category])
    save_registry(data)
    return True


def add_sorted_entity(game: str, name: str, category: str, *, faction: str = "") -> dict:
    if category not in {"protected_character", "user_configured", "approved_role_speaker"}:
        category = "protected_character"
    data = load_registry()
    bucket = data["games"][str(game or "CUSTOM").upper()]
    bucket[category].append(_entity(name, category, source="user_added", origin_view="detail", faction=faction))
    bucket[category] = _dedupe_entities(bucket[category])
    save_registry(data)
    return bucket


@dataclass
class ProtectedText:
    source: str
    mapping: dict[str, str]


def protect_named_entities(text: str, game: str) -> ProtectedText:
    """Protect canonical entities only for the backend round-trip.

    v8.7.4 never sends these backend tokens through IDN/QA processing. The
    compiled matcher is cached per game to avoid rebuilding hundreds of regexes
    on every progressive dialogue frame.
    """
    source = str(text or "")
    mapping: dict[str, str] = {}
    matches = find_protected_entities(source, game)
    if not matches:
        return ProtectedText(source=source, mapping=mapping)
    chunks: list[str] = []
    cursor = 0
    for idx, (start, end, name) in enumerate(matches):
        chunks.append(source[cursor:start])
        token = f"__ORT_BKEND_{idx:03d}__"
        mapping[token] = name
        chunks.append(token)
        cursor = end
    chunks.append(source[cursor:])
    return ProtectedText(source="".join(chunks), mapping=mapping)


def restore_named_entities(text: str, protected: ProtectedText | None) -> str:
    """Restore backend-only tokens, tolerating harmless separator spacing."""
    out = str(text or "")
    if not protected:
        return out
    for token, name in protected.mapping.items():
        out = out.replace(token, name)
    # Backend may insert spaces or drop one underscore; match a whole numeric
    # token id so item 000 cannot partially consume item 001.
    malformed = re.compile(r"_?\s*_?\s*ORT\s*[_ -]*\s*BKEND\s*[_ -]*\s*(\d{1,3})\s*_?\s*_?", re.I)
    def repl(match: re.Match[str]) -> str:
        key = f"__ORT_BKEND_{int(match.group(1)):03d}__"
        return protected.mapping.get(key, match.group(0))
    return malformed.sub(repl, out)
