"""Export a bounded ORT v8.7.8 debug bundle for safety/CT2/candidate analysis.

Large session/event logs are represented by tail excerpts so exporting diagnostics
remains practical even after many gameplay runs. A manifest records skipped large
files for optional manual attachment.
"""
from __future__ import annotations
import argparse
import json
import time
import zipfile
from collections import deque
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATIC_PATTERNS = [
    'logs/v8_7_8_test_ledger_*.json', 'reports/v8_7_8_candidate_mining_*.json',
    'status/*.json', 'status/*.txt', 'speaker_registry_v2.json',
    'configs/reference_roster_catalog_v8_7_3.json', 'configs/gfl2_observed_candidates_v8_7_8.json',
    'configs/speaker_registry_v2.defaults.json', 'data_processing_settings.json', 'webui_prefs.json'
]

def _tail_text(path: Path, max_lines: int) -> str:
    rows: deque[str] = deque(maxlen=max_lines)
    with path.open('r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            rows.append(line)
    return ''.join(rows)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-dir', default=str(BASE))
    ap.add_argument('--max-session-files', type=int, default=8)
    ap.add_argument('--tail-lines', type=int, default=40_000)
    ap.add_argument('--max-static-mb', type=int, default=12)
    args = ap.parse_args()
    base = Path(args.base_dir).resolve(); out_dir = base / 'debug_bundles'; out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f'ORT_v8_7_8_DEBUG_BUNDLE_{time.strftime("%Y%m%d_%H%M%S")}.zip'
    session_files = list((base / 'logs').glob('session_*_events.jsonl')) if (base / 'logs').exists() else []
    session_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    session_files = session_files[:max(1, args.max_session_files)]
    log_txt = list((base / 'logs').glob('*.txt')) if (base / 'logs').exists() else []
    log_txt.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    log_txt = log_txt[:max(1, args.max_session_files)]
    manifest = {'version':'v8.7.8','bounded_export':True,'session_limit':args.max_session_files,'tail_lines':args.tail_lines,'included':[],'excerpts':[],'skipped_large':[]}
    added: set[Path] = set()
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('DEBUG_BUNDLE_README.txt', 'ORT v8.7.8 bounded bundle: Faithfulness v2, Qur quarantine, strict CT2 story, IDN-over-CT2, final-only safe commit, candidate mining and gate telemetry. Large session logs are tail excerpts; see manifest.\n')
        for path in session_files + log_txt:
            if not path.is_file() or path in added:
                continue
            excerpt_name = f'excerpts/{path.name}.tail.txt'
            z.writestr(excerpt_name, _tail_text(path, args.tail_lines))
            manifest['excerpts'].append({'source':str(path.relative_to(base)), 'archive':excerpt_name, 'size_bytes':path.stat().st_size})
            added.add(path)
        for pattern in STATIC_PATTERNS + ['cache/*v8_7_8*.json']:
            for path in base.glob(pattern):
                if not path.is_file() or path in added:
                    continue
                if path.stat().st_size > args.max_static_mb * 1024 * 1024:
                    manifest['skipped_large'].append({'path':str(path.relative_to(base)), 'size_bytes':path.stat().st_size, 'reason':'exceeds_static_limit'})
                    continue
                z.write(path, path.relative_to(base).as_posix()); added.add(path); manifest['included'].append(str(path.relative_to(base)))
        z.writestr('DEBUG_BUNDLE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'Debug bundle: {target} | included={len(added)} | excerpts={len(manifest["excerpts"])} | skipped_large={len(manifest["skipped_large"])}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
