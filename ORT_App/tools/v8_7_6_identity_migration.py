"""Dry-run/apply official exact-speaker alignment and observed priority metadata for ORT v8.7.6."""
from __future__ import annotations
import argparse, json, shutil, time
from pathlib import Path

def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())

def _key(value: str) -> str:
    return "".join(ch.lower() for ch in _clean(value) if ch.isalnum())

def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    except Exception:
        return default

def run(base_dir: str | Path=".", apply: bool=False) -> str:
    base=Path(base_dir).resolve()
    catalog=_load(base/"configs"/"reference_roster_catalog_v8_7_3.json", {"games":{}})
    observed=_load(base/"configs"/"gfl2_observed_candidates_v8_7_6.json", {})
    registry_path=base/"speaker_registry_v2.json"
    defaults=base/"configs"/"speaker_registry_v2.defaults.json"
    registry=_load(registry_path, _load(defaults, {"games":{}}))
    gfl2=registry.setdefault("games",{}).setdefault("GFL2_EXILIUM",{})
    official=[_clean(x.get("display_name","")) for x in catalog.get("games",{}).get("GFL2_EXILIUM",{}).get("entries",[]) if isinstance(x,dict) and _clean(x.get("display_name",""))]
    official_keys={_key(x) for x in official}
    legacy=gfl2.setdefault("legacy_untrusted",[])
    promoted=[_clean(x.get("display_name","") if isinstance(x,dict) else x) for x in legacy if _key(x.get("display_name","") if isinstance(x,dict) else x) in official_keys]
    already={_key(x.get("display_name","")) for x in gfl2.setdefault("verified_character_speaker_exact",[]) if isinstance(x,dict)}
    additions=[x for x in official if _key(x) not in already]
    observed_map={_key(x.get("display_name","")):x for x in observed.get("observed_official_priority",[]) if isinstance(x,dict)}
    lines=[
      "ORT Translation v8.7.6 Official Exact-Speaker Alignment " + ("APPLY" if apply else "DRY-RUN"),
      "Policy: official GFL2 names are exact-only live speakers; aliases remain ROI-only review; legacy noise is never auto-promoted.",
      f"Official catalog entries: {len(official)}",
      f"Exact-speaker additions/alignment: {len(additions)}",
      f"Official names removed from legacy_untrusted: {len(promoted)}",
      f"Observed/priority metadata rows available: {len(observed_map)}",
    ]
    for name in ["Zhaohui","Vector","Colphne","Groza","Ullrid","Harpsy","Mayling"]:
        status="OFFICIAL EXACT" if _key(name) in official_keys else "NOT FOUND"
        obs=observed_map.get(_key(name),{})
        suffix=f" | observed={obs.get('status','catalog_only')}" if obs else ""
        lines.append(f"- {name}: {status}{suffix}")
    if not apply:
        lines.append("Gunakan --apply hanya pada folder TEST setelah backup diperiksa. Alias candidate tidak diaktifkan otomatis.")
        return "\n".join(lines)
    backup=base/"backups"/f"identity_before_v8_7_6_alignment_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True,exist_ok=True)
    if registry_path.exists():
        shutil.copy2(registry_path,backup/registry_path.name)
    rows=[]
    for name in sorted(set(official), key=str.casefold):
        obs=observed_map.get(_key(name),{})
        rows.append({"canonical_id":_key(name),"display_name":name,"category":"verified_character_speaker_exact","aliases":[],"source":"reference_catalog_entries_v8_7_6","origin_view":"catalog_exact","observed_recent_story":bool(obs),"observed_status":obs.get("status","catalog_only"),"faction":"","spoiler":False})
    gfl2["verified_character_speaker_exact"]=rows
    gfl2["legacy_untrusted"]=[row for row in legacy if _key(row.get("display_name","") if isinstance(row,dict) else row) not in official_keys]
    registry["schema_version"]="v8_7_6_adaptive_ocr_exact_registry_v4"
    registry.setdefault("migration_notes",[]).append({"version":"v8.7.6","ts":time.time(),"change":"official exact-speaker alignment + observed priority metadata; aliases remain review-only"})
    registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding="utf-8")
    lines.append(f"Backup dibuat dan registry diselaraskan: {backup.relative_to(base)}")
    lines.append("Candidate aliases tetap review-only; jalankan pengujian baseline sebelum Mode Responsif.")
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir",default=".")
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    print(run(args.base_dir,args.apply))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
