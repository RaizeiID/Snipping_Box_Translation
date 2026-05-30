from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "ORT_Translation_v8_8_1_GITHUB_SOURCE.zip"

EXCLUDE_PARTS = {
    "_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD",
    "cache",
    "logs",
    "backups",
    "debug_bundles",
    "__pycache__",
    ".venv",
    "ORT_Runtime",
    "_runtime",
    "models",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}

# Keep docs placeholder folders under ORT/cache/logs/etc only if they contain .gitkeep.
def should_exclude(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = set(rel.parts)
    if path.name == OUT.name:
        return True
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        # allow .gitkeep placeholders outside local runtime folder
        if path.name == ".gitkeep" and "_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD" not in rel.parts:
            return False
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False

if OUT.exists():
    OUT.unlink()

files = [p for p in ROOT.rglob("*") if p.is_file() and not should_exclude(p)]
with ZipFile(OUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        z.write(p, p.relative_to(ROOT.parent))

print(f"GitHub source ZIP dibuat: {OUT}")
print(f"Jumlah file: {len(files)}")
