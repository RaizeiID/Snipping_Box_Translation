from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


REQUIRED_MODEL_FILE_MIN_BYTES = {
    "config.json": 2,
    "model.bin": 1_000_000,
    "tokenizer.json": 100,
}

OPTIONAL_MODEL_FILE_MIN_BYTES = {
    "preprocessor_config.json": 2,
}


@dataclass(frozen=True)
class ModelInspection:
    model: str
    path: str
    ready: bool
    missing_files: tuple[str, ...]
    invalid_files: tuple[str, ...]
    optional_missing_files: tuple[str, ...]
    optional_invalid_files: tuple[str, ...]
    vocabulary_file: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def canonical_model_dir(model_root: Path | str, model_size: str) -> Path:
    safe_size = str(model_size or "base").strip().lower().replace("/", "-").replace("\\", "-")
    return Path(model_root).expanduser().resolve() / f"faster-whisper-{safe_size}"


def _usable_file(path: Path, minimum_bytes: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= int(minimum_bytes)
    except OSError:
        return False


def _vocabulary_candidates(model_dir: Path) -> Iterable[Path]:
    try:
        yield from sorted(model_dir.glob("vocabulary.*"))
    except OSError:
        return


def inspect_model_dir(model_dir: Path | str, model_size: str) -> ModelInspection:
    directory = Path(model_dir).expanduser().resolve()
    missing = []
    invalid = []
    optional_missing = []
    optional_invalid = []
    for name, minimum_bytes in REQUIRED_MODEL_FILE_MIN_BYTES.items():
        path = directory / name
        if not path.exists():
            missing.append(name)
        elif not _usable_file(path, minimum_bytes):
            invalid.append(name)

    for name, minimum_bytes in OPTIONAL_MODEL_FILE_MIN_BYTES.items():
        path = directory / name
        if not path.exists():
            optional_missing.append(name)
        elif not _usable_file(path, minimum_bytes):
            optional_invalid.append(name)

    vocabulary_file = ""
    vocabulary_paths = list(_vocabulary_candidates(directory))
    if not vocabulary_paths:
        missing.append("vocabulary.*")
    else:
        usable_vocabulary = next((path for path in vocabulary_paths if _usable_file(path, 2)), None)
        if usable_vocabulary is None:
            invalid.append("vocabulary.*")
        else:
            vocabulary_file = usable_vocabulary.name

    return ModelInspection(
        model=str(model_size or "base"),
        path=str(directory),
        ready=not missing and not invalid,
        missing_files=tuple(missing),
        invalid_files=tuple(invalid),
        optional_missing_files=tuple(optional_missing),
        optional_invalid_files=tuple(optional_invalid),
        vocabulary_file=vocabulary_file,
    )


def inspect_local_model(model_root: Path | str, model_size: str) -> ModelInspection:
    return inspect_model_dir(canonical_model_dir(model_root, model_size), model_size)


def model_problem_text(inspection: ModelInspection) -> str:
    parts = []
    if inspection.missing_files:
        parts.append("hilang: " + ", ".join(inspection.missing_files))
    if inspection.invalid_files:
        parts.append("tidak valid: " + ", ".join(inspection.invalid_files))
    return "; ".join(parts) if parts else "lengkap"
