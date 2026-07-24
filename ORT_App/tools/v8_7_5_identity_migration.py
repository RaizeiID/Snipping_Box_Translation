"""Dry-run/apply verified exact-speaker migration for ORT Translation v8.7.5."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _key(value: str) -> str:
    return "".join(ch.lower() for ch in _clean(value) if ch.isalnum())


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except Exception:
        return default


def run(base_dir: str | Path = ".", apply: bool = False) -> str:
    base = Path(base_dir).resolve()
    catalog_path = base / "configs" / "reference_roster_catalog_v8_7_3.json"
    registry_path = base / "speaker_registry_v2.json"
    defaults_path = base / "configs" / "speaker_registry_v2.defaults.json"
    catalog = _load(catalog_path, {"games": {}})
    registry = _load(registry_path, _load(defaults_path, {"games": {}}))
    games = registry.setdefault("games", {})
    gfl2 = games.setdefault("GFL2_EXILIUM", {})
    catalog_entries = catalog.get("games", {}).get("GFL2_EXILIUM", {}).get("entries", []) or []
    official_names = [_clean(row.get("display_name", "")) for row in catalog_entries if isinstance(row, dict) and _clean(row.get("display_name", ""))]
    existing_rows = gfl2.setdefault("verified_character_speaker_exact", [])
    existing = {_key(row.get("display_name", "")) for row in existing_rows if isinstance(row, dict)}
    additions = [name for name in official_names if _key(name) not in existing]
    legacy = gfl2.setdefault("legacy_untrusted", [])
    legacy_names = []
    for row in legacy:
        legacy_names.append(_clean(row.get("display_name", "")) if isinstance(row, dict) else _clean(row))
    promoted_from_legacy = [name for name in official_names if _key(name) in {_key(x) for x in legacy_names}]
    lines = [
        "ORT Translation v8.7.5 Verified Character Exact-Speaker Migration " + ("APPLY" if apply else "DRY-RUN"),
        "Policy: karakter resmi GFL2 boleh label speaker hanya melalui exact Name ROI/exact prefix; fuzzy tetap terbatas pada alias/speaker reviewed.",
        f"Katalog resmi GFL2 terbaca dari entries[].display_name: {len(official_names)} nama",
        f"Akan ditambahkan ke verified_character_speaker_exact: {len(additions)} nama",
        f"Akan dikeluarkan dari legacy_untrusted karena resmi: {len(promoted_from_legacy)} nama",
    ]
    priority = ["Zhaohui", "Vector", "Colphne", "Groza", "Ullrid"]
    for name in priority:
        status = "ADD/ENABLE EXACT" if name in additions or _key(name) in {_key(x) for x in official_names} else "NOT FOUND IN CATALOG"
        lines.append(f"- {name}: {status}")
    if not apply:
        lines.append("Gunakan --apply pada folder TEST setelah memeriksa dry-run. Runtime v8.7.5 tetap memakai katalog exact-only walau migrasi belum diterapkan.")
        return "\n".join(lines)
    backup = base / "backups" / f"identity_before_v8_7_5_verified_exact_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    if registry_path.exists():
        shutil.copy2(registry_path, backup / registry_path.name)
    gfl2["verified_character_speaker_exact"] = [
        {"canonical_id": _key(name), "display_name": name, "category": "verified_character_speaker_exact", "aliases": [], "source": "reference_catalog_entries_v8_7_5", "origin_view": "catalog_exact", "faction": "", "spoiler": False}
        for name in sorted(set(official_names), key=str.casefold)
    ]
    official_keys = {_key(name) for name in official_names}
    gfl2["legacy_untrusted"] = [row for row in legacy if _key(row.get("display_name", "") if isinstance(row, dict) else row) not in official_keys]
    registry["schema_version"] = "v8_7_5_verified_exact_registry_v3"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    lines.append(f"Registry dibackup dan diperbarui: {backup.relative_to(base)}")
    lines.append("Legacy noise non-katalog dipertahankan sebagai untrusted; role/title baru tidak diaktifkan otomatis.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(run(args.base_dir, args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
