"""Export one v8.7.6 support bundle including OCR rescue, false-speaker and ledger evidence."""
from __future__ import annotations
import time, zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; OUT=BASE/"debug_bundles"
PATTERNS=["logs/*.txt","logs/*.jsonl","status/*.json","status/*.txt","cache/*v8_7_6*.json","speaker_registry_v2.json","configs/reference_roster_catalog_v8_7_3.json","configs/gfl2_observed_candidates_v8_7_6.json","data_processing_settings.json","webui_prefs.json"]
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/f"ORT_v8_7_6_DEBUG_BUNDLE_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    added=set()
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("DEBUG_BUNDLE_README.txt","ORT v8.7.6 bundle: raw/session OCR events, OCR_READABILITY_RESCUE, rejected/blocked speaker events, final overlay, requested/applied/runtime OCR status, cache namespace, identity registry, observed candidate ledger.\n")
        for pattern in PATTERNS:
            for path in BASE.glob(pattern):
                if path.is_file() and path not in added:
                    z.write(path,path.relative_to(BASE).as_posix()); added.add(path)
    print(target); return 0
if __name__=="__main__": raise SystemExit(main())
