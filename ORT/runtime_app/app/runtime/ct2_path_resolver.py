"""ORT v8.8.3 CT2 path resolver.

The v8.8.1 structure refactor intentionally keeps large model folders out of
GitHub/source ZIPs.  In local installs those folders may exist beside the root
project (``models/``), inside ``ORT/runtime_app/models/``, or inside a grouped
local runtime folder.  This helper resolves the first valid CTranslate2 EN->ID
model directory without requiring users to create manual junctions.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, List, Dict, Any

MODEL_DIR_NAMES = ("ct2_opus_mt_en_id", "ct2_en_id", "opus_mt_en_id_ct2", "en-id-ct2")
ENV_KEYS = ("ORT_CT2_EN_ID_DIR", "TITAN_CT2_EN_ID_DIR", "ORT_FAST_CT2_MODEL_DIR", "ORT_LITE_CT2_MODEL_DIR")

@dataclass(frozen=True)
class CT2ResolveResult:
    path: Path
    likely_valid: bool
    reason: str
    candidates: List[Dict[str, Any]]


def _project_root_from(base_dir: Path) -> Path:
    base_dir = Path(base_dir).resolve()
    # If base_dir is ORT/runtime_app, project root is two levels up.
    if base_dir.name.lower() == "runtime_app" and base_dir.parent.name.upper() == "ORT":
        return base_dir.parent.parent
    if base_dir.name.upper() == "ORT":
        return base_dir.parent
    return base_dir


def validate_ct2_dir(path: Path) -> Dict[str, Any]:
    p = Path(path).expanduser()
    try:
        files = sorted(x.name for x in p.iterdir() if x.is_file()) if p.exists() else []
    except Exception:
        files = []
    has_model = "model.bin" in files or "model.bin.index.json" in files
    has_spm = ("source.spm" in files and "target.spm" in files) or "shared_vocabulary.json" in files
    likely_valid = bool(files and has_model and has_spm)
    missing = []
    if not has_model:
        missing.append("model.bin atau model.bin.index.json")
    if not has_spm:
        missing.append("source.spm + target.spm atau shared_vocabulary.json")
    return {
        "path": str(p),
        "exists": p.exists(),
        "has_files": bool(files),
        "files": files[:80],
        "likely_valid": likely_valid,
        "missing": missing,
    }


def candidate_ct2_dirs(base_dir: str | os.PathLike[str] | None = None) -> List[Path]:
    base = Path(base_dir or Path(__file__).resolve().parents[2]).resolve()
    project_root = _project_root_from(base)
    ort_root = project_root / "ORT"
    runtime_app = ort_root / "runtime_app"
    candidates: List[Path] = []
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value).expanduser())
    parents = [
        runtime_app / "models",
        project_root / "models",
        ort_root / "_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD" / "models",
        project_root / "_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD" / "models",
        base / "models",
        base / "_runtime" / "models",
        base,
    ]
    for parent in parents:
        for name in MODEL_DIR_NAMES:
            candidates.append(parent / name)
    out: List[Path] = []
    seen = set()
    for p in candidates:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def resolve_ct2_model_dir(base_dir: str | os.PathLike[str] | None = None) -> CT2ResolveResult:
    candidates = []
    fallback = None
    for p in candidate_ct2_dirs(base_dir):
        v = validate_ct2_dir(p)
        candidates.append(v)
        if v["likely_valid"]:
            resolved = Path(v["path"]).resolve()
            try:
                os.environ["ORT_CT2_MODEL_DIR_USED"] = str(resolved)
                os.environ["ORT_CT2_SPM_DIR_USED"] = str(resolved)
                os.environ.setdefault("TITAN_CT2_EN_ID_DIR", str(resolved))
                os.environ.setdefault("ORT_FAST_CT2_MODEL_DIR", str(resolved))
                os.environ.setdefault("ORT_LITE_CT2_MODEL_DIR", str(resolved))
            except Exception:
                pass
            return CT2ResolveResult(resolved, True, "valid_ct2_model_found", candidates)
        if v["has_files"] and fallback is None:
            fallback = Path(v["path"])
    if fallback is None:
        base = Path(base_dir or Path(__file__).resolve().parents[2]).resolve()
        fallback = _project_root_from(base) / "models" / "ct2_opus_mt_en_id"
    return CT2ResolveResult(fallback, False, "no_valid_ct2_model_found", candidates)
