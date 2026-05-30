"""Dry-run/apply migration helper for v8.7.3 identity registry and contaminated cache."""
from __future__ import annotations
import argparse, json, shutil, time
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTAMINATED = ('Phaedusa','Balthalde','Helena Helen','Helena I Helen','Helena Il Helen')

def scan_cache(base: Path):
    results=[]
    for p in (base/'cache').glob('*.json') if (base/'cache').exists() else []:
        try:
            text=p.read_text(encoding='utf-8-sig')
        except Exception:
            continue
        hits=[token for token in CONTAMINATED if token.casefold() in text.casefold()]
        if hits: results.append((p,hits))
    return results

def run(base_dir=None, apply=False):
    base=Path(base_dir or Path(__file__).resolve().parents[1])
    from app.identity.speaker_registry import load_registry, REGISTRY_PATH
    before=REGISTRY_PATH.exists()
    registry=load_registry(migrate_legacy=True)
    cache_hits=scan_cache(base)
    lines=['ORT v8.7.3 Identity/Data Migration ' + ('APPLY' if apply else 'DRY-RUN'),
           'Helen dan Helena dipertahankan sebagai canonical speaker terpisah.',
           f'Registry path: {REGISTRY_PATH.name} ({"already existed" if before else "will be created from defaults/legacy"})',
           f'Cache files terkontaminasi terdeteksi: {len(cache_hits)}']
    for path,hits in cache_hits:
        lines.append(f'- {path.name}: {", ".join(hits)}')
    if apply and cache_hits:
        backup=base/'backups'/f'cache_before_v8_7_3_identity_guard_{time.strftime("%Y%m%d_%H%M%S")}'
        backup.mkdir(parents=True,exist_ok=True)
        for path,_ in cache_hits:
            shutil.copy2(path, backup/path.name)
            path.unlink(missing_ok=True)
        lines.append(f'Cache terdampak dibackup dan di-invalidasi: {backup}')
    else:
        lines.append('Gunakan --apply untuk membackup lalu menginvalidasi hanya cache yang terdeteksi tercemar.')
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-dir', default=None); ap.add_argument('--apply', action='store_true'); args=ap.parse_args()
    print(run(args.base_dir, args.apply)); return 0
if __name__=='__main__': raise SystemExit(main())
