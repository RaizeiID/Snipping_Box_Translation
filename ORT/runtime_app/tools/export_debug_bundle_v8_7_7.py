"""Export ORT v8.7.7 debug bundle for semantic fidelity, CT2 and identity analysis."""
from __future__ import annotations
import time, zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; OUT=BASE/'debug_bundles'
PATTERNS=['logs/*.txt','logs/*.jsonl','logs/v8_7_7_test_ledger_*.json','status/*.json','status/*.txt','cache/*v8_7_7*.json','speaker_registry_v2.json','configs/reference_roster_catalog_v8_7_3.json','configs/gfl2_observed_candidates_v8_7_7.json','configs/speaker_registry_v2.defaults.json','data_processing_settings.json','webui_prefs.json']
def main():
    OUT.mkdir(parents=True,exist_ok=True); target=OUT/f'ORT_v8_7_7_DEBUG_BUNDLE_{time.strftime("%Y%m%d_%H%M%S")}.zip'; added=set()
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('DEBUG_BUNDLE_README.txt','ORT v8.7.7 bundle: SEMANTIC_HALLUCINATION_BLOCKED, PREVIEW_HELD_INCOMPLETE, CT2_JOB_FALLBACK, IDN_QUALITY_LOCK_HELD, OCR rescue, final overlay, cache namespace, identity/term ledger.\n')
        for pattern in PATTERNS:
            for path in BASE.glob(pattern):
                if path.is_file() and path not in added: z.write(path,path.relative_to(BASE).as_posix()); added.add(path)
    print(target)
if __name__=='__main__': main()
