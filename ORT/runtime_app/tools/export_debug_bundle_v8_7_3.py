"""Export one support bundle for ORT v8.7.3 analysis."""
from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from zipfile import ZipFile, ZIP_DEFLATED
import json, time

def export_bundle(base_dir=None):
    base=Path(base_dir or Path(__file__).resolve().parents[1])
    out=base/'logs'/f'ORT_DEBUG_BUNDLE_v8_7_3_{time.strftime("%Y%m%d_%H%M%S")}.zip'; out.parent.mkdir(exist_ok=True)
    patterns=['logs/*.txt','logs/*.jsonl','status/*.json','cache/*.json','configs/reference_roster_catalog_v8_7_3.json','configs/speaker_registry_v2.defaults.json','speaker_registry_v2.json','data_processing_settings.json']
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for pat in patterns:
            for p in base.glob(pat):
                if p.is_file() and p != out:
                    z.write(p,p.relative_to(base).as_posix())
        z.writestr('DEBUG_BUNDLE_README.txt','ORT v8.7.3 Debug Bundle: live/structured log, IDN evaluation, applied status, cache summary, identity registry/config.\n')
    return out
if __name__=='__main__': print(export_bundle())
