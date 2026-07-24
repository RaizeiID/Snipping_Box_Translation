"""Dry-run/apply backup rotation for contaminated pre-v8.7.4 caches."""
from __future__ import annotations
import argparse
import re
import shutil
import time
from pathlib import Path

LEGACY_MARKERS = ("v8_7_2", "v8_7_3_identity_guard")
CONTAMINATED_RE = re.compile(r"ORT\s*_?\s*ENTITY|_\s*_\s*ORT\s*_?\s*ENTITY|Phaedusa|Balthalde|Helena\s+Helen", re.I)

def scan(base: Path):
    rows=[]
    cache_dir=base/'cache'
    if not cache_dir.exists(): return rows
    for p in sorted(cache_dir.glob('*.json')):
        try: text=p.read_text(encoding='utf-8-sig', errors='replace')
        except Exception: continue
        reasons=[]
        if any(m in p.name or m in text for m in LEGACY_MARKERS): reasons.append('legacy_namespace')
        if CONTAMINATED_RE.search(text): reasons.append('contaminated_translation')
        if reasons: rows.append((p, sorted(set(reasons))))
    return rows

def run(base_dir='.', apply=False):
    base=Path(base_dir).resolve(); rows=scan(base)
    lines=['ORT Translation v8.7.4 Cache Rotation ' + ('APPLY' if apply else 'DRY-RUN'),
           'Target namespace baru: v8_7_4_entity_span_responsive',
           f'File cache lama/tercemar terdeteksi: {len(rows)}']
    backup=None
    if apply and rows:
        backup=base/'backups'/f'cache_before_v8_7_4_entity_span_{time.strftime("%Y%m%d_%H%M%S")}'
        backup.mkdir(parents=True, exist_ok=True)
    for p, reasons in rows:
        lines.append(f'- {p.relative_to(base)}: {", ".join(reasons)}')
        if backup:
            shutil.move(str(p), str(backup/p.name))
    if backup:
        lines.append(f'Cache dipindahkan aman ke backup: {backup.relative_to(base)}')
    elif rows:
        lines.append('Jalankan kembali dengan --apply setelah memeriksa daftar ini.')
    else:
        lines.append('Tidak ada cache lama/tercemar yang perlu dirotasi.')
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-dir',default='.'); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
    print(run(a.base_dir,a.apply)); return 0
if __name__=='__main__': raise SystemExit(main())
