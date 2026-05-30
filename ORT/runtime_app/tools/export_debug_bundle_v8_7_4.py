"""Export one support bundle for ORT v8.7.4 analysis."""
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import time

def export_bundle(base_dir=None):
    base=Path(base_dir or Path(__file__).resolve().parents[1])
    out=base/'logs'/f'ORT_DEBUG_BUNDLE_v8_7_4_{time.strftime("%Y%m%d_%H%M%S")}.zip'; out.parent.mkdir(exist_ok=True)
    patterns=['logs/*.txt','logs/*.jsonl','status/*.json','cache/*.json','configs/reference_roster_catalog_v8_7_3.json','configs/speaker_registry_v2.defaults.json','speaker_registry_v2.json','data_processing_settings.json','webui_prefs.json']
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for pat in patterns:
            for p in base.glob(pat):
                if p.is_file() and p != out:
                    z.write(p,p.relative_to(base).as_posix())
        z.writestr('DEBUG_BUNDLE_README.txt','ORT v8.7.4 Debug Bundle: logs, IDN evaluation, entity span/residual events, applied status, cache namespace, identity registry/config.\n')
    return out
if __name__=='__main__': print(export_bundle())
