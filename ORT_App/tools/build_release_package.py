from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}
VOLATILE_DIRS = {"logs", "reports", "backups"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return True
    return False


def build(out_path: str | os.PathLike[str] | None = None) -> Path:
    out = Path(out_path or ROOT.parent / "ORT_Translation_v8_4_FULL_PROJECT.zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob("*"):
            if should_skip(p) or p == out:
                continue
            if p.is_dir():
                continue
            rel = p.relative_to(ROOT.parent)
            # Volatile dirs are included only with README placeholders.
            if any(part in VOLATILE_DIRS for part in rel.parts) and p.name != "README.txt":
                continue
            z.write(p, rel.as_posix())
    return out


if __name__ == "__main__":
    print(build())
