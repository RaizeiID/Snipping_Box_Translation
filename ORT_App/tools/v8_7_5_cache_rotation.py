"""Dry-run/apply backup rotation for caches unsafe under ORT Translation v8.7.5."""
from __future__ import annotations
import argparse
import re
import shutil
import time
from pathlib import Path

NEW_NAMESPACE = "v8_7_5_verified_exact_entity_safe"
LEGACY_MARKERS = ("v8_7_2", "v8_7_3_identity_guard", "v8_7_4_entity_span_responsive")
CONTAMINATED_RE = re.compile(r"(?:__|_\s*_)\s*ORT|\bORT\s*[_ -]+\s*(?:ENTITY|BKEND|BKED|BEND|BACKEND)\b|Phaedusa|Balthalde|Helena\s+Helen", re.I)


def scan(base: Path):
    rows = []
    cache_dir = base / "cache"
    if not cache_dir.exists():
        return rows
    for path in sorted(cache_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        reasons = []
        if any(marker in path.name or marker in text for marker in LEGACY_MARKERS):
            reasons.append("old_namespace")
        if CONTAMINATED_RE.search(text):
            reasons.append("unsafe_or_malformed_output")
        if reasons:
            rows.append((path, sorted(set(reasons))))
    return rows


def run(base_dir=".", apply=False):
    base = Path(base_dir).resolve()
    rows = scan(base)
    lines = [
        "ORT Translation v8.7.5 Cache Rotation " + ("APPLY" if apply else "DRY-RUN"),
        f"Target namespace baru: {NEW_NAMESPACE}",
        f"File cache lama/tercemar terdeteksi: {len(rows)}",
    ]
    backup = None
    if apply and rows:
        backup = base / "backups" / f"cache_before_v8_7_5_entity_safe_{time.strftime('%Y%m%d_%H%M%S')}"
        backup.mkdir(parents=True, exist_ok=True)
    for path, reasons in rows:
        lines.append(f"- {path.relative_to(base)}: {', '.join(reasons)}")
        if backup:
            shutil.move(str(path), str(backup / path.name))
    if backup:
        lines.append(f"Cache dipindahkan aman ke backup: {backup.relative_to(base)}")
    elif rows:
        lines.append("Jalankan kembali dengan --apply pada folder TEST setelah memeriksa daftar ini.")
    else:
        lines.append("Tidak ada cache lama/tercemar yang perlu dirotasi.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(run(args.base_dir, args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
