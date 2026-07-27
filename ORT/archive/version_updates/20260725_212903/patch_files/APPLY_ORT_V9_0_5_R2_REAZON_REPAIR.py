from __future__ import annotations
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path

def sha256(p: Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def locate(start: Path)->Path:
    candidates=[start,start.parent]
    for c in candidates:
        if (c/'VERSION.txt').is_file() and (c/'ORT_App').is_dir() and (c/'ORT_Runtime').is_dir(): return c
    raise RuntimeError('Project root ORT tidak ditemukan. Letakkan folder patch di dalam atau tepat di samping root ORT.')

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--project-root'); a=ap.parse_args()
    patch=Path(__file__).resolve().parent; root=Path(a.project_root).resolve() if a.project_root else locate(patch)
    payload=patch/'payload'; backup=root/'ORT'/'backups'/f"v9_0_5_r2_{time.strftime('%Y%m%d_%H%M%S')}"
    copied=[]
    for src in payload.rglob('*'):
        if not src.is_file(): continue
        rel=src.relative_to(payload); dst=root/rel
        if dst.exists():
            b=backup/rel; b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dst,b)
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); copied.append(str(rel))
    active=root/'ORT_App'/'tools'/'setup_v9_0_4_audio_providers.py'
    text=active.read_text(encoding='utf-8')
    checks={
      'version_file': (root/'VERSION.txt').read_text(encoding='utf-8').strip().lstrip('vV')=='9.0.5',
      'direct_manifest': '_download_reazon_static' in text and 'direct_static_manifest' in text,
      'no_reazon_dry_run': 'snapshot_download" not in _download_reazon_static' in text,
      'r2_cuda_variant': 'desired_variant' in text and 'CUDA REPAIR' in text,
      'webui_v905': 'setup_v9_0_5_audio_providers.py' in (root/'ORT_App'/'webui.py').read_text(encoding='utf-8'),
    }
    receipt=root/'ORT'/'status'/'v9_0_5_r2_install_receipt.json'; receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'passed':all(checks.values()),'checks':checks,'files':copied,'backup':str(backup),'active_setup_sha256':sha256(active)},indent=2),encoding='utf-8')
    for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
    if not all(checks.values()): return 8
    print('ORT_V9_0_5_R2_REAZON_REPAIR: PASS'); print('Project root:',root); return 0
if __name__=='__main__': raise SystemExit(main())
