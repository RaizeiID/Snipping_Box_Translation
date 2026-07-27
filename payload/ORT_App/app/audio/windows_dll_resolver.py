from __future__ import annotations

import os
import site
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_DLL_HANDLES: list[object] = []
_REGISTERED: set[str] = set()


@dataclass(frozen=True)
class DllResolutionReport:
    registered_paths: tuple[str, ...]
    found: dict[str, str]
    missing: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "registered_paths": list(self.registered_paths),
            "found": dict(self.found),
            "missing": list(self.missing),
        }


def _unique_existing(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        try:
            path = raw.expanduser().resolve(strict=False)
        except Exception:
            continue
        key = str(path).lower()
        if key in seen or not path.is_dir():
            continue
        seen.add(key)
        result.append(path)
    return result


def _site_packages() -> list[Path]:
    paths: list[Path] = []
    try:
        paths.extend(Path(item) for item in site.getsitepackages())
    except Exception:
        pass
    try:
        paths.append(Path(site.getusersitepackages()))
    except Exception:
        pass
    paths.extend(Path(item) for item in sys.path if item and "site-packages" in item.lower())
    return _unique_existing(paths)


def candidate_dll_directories() -> list[Path]:
    candidates: list[Path] = []

    for name, value in os.environ.items():
        upper = name.upper()
        if upper == "CUDA_PATH" or upper.startswith("CUDA_PATH_V"):
            root = Path(value)
            candidates.extend((root / "bin", root / "lib" / "x64", root))

    for token in os.environ.get("PATH", "").split(os.pathsep):
        if token.strip():
            candidates.append(Path(token.strip().strip('"')))

    prefix = Path(sys.prefix)
    candidates.extend((prefix / "Library" / "bin", prefix / "DLLs", prefix / "Scripts"))

    for package_root in _site_packages():
        candidates.append(package_root / "torch" / "lib")
        nvidia_root = package_root / "nvidia"
        if nvidia_root.is_dir():
            for child in nvidia_root.iterdir():
                if child.is_dir():
                    candidates.extend((child / "bin", child / "lib", child / "lib" / "x64"))
        # Support both current and older NVIDIA wheel layouts.
        for pattern in (
            "nvidia_*\\bin", "nvidia_*\\lib", "nvidia_*\\lib\\x64",
            "nvidia/*/bin", "nvidia/*/lib", "nvidia/*/lib/x64",
        ):
            candidates.extend(package_root.glob(pattern))

    # ORT bundles may place CUDA components beside the virtual environments.
    runtime_root = prefix.parent.parent if prefix.name.lower() in {".venv", "venv"} else prefix.parent
    candidates.extend((
        runtime_root / "cuda" / "bin",
        runtime_root / "cuda" / "lib" / "x64",
        runtime_root / "cudnn" / "bin",
        runtime_root / "onnxruntime" / "bin",
    ))

    return _unique_existing(candidates)


def register_windows_dll_directories(extra: Iterable[str | os.PathLike[str]] = ()) -> tuple[str, ...]:
    if os.name != "nt":
        return ()

    directories = candidate_dll_directories() + _unique_existing(Path(item) for item in extra)
    registered: list[str] = []
    for path in directories:
        key = str(path).lower()
        if key in _REGISTERED:
            registered.append(str(path))
            continue
        try:
            handle = os.add_dll_directory(str(path))
        except (AttributeError, FileNotFoundError, OSError):
            handle = None
        if handle is not None:
            _DLL_HANDLES.append(handle)
        _REGISTERED.add(key)
        registered.append(str(path))

    current = [token for token in os.environ.get("PATH", "").split(os.pathsep) if token]
    current_keys = {token.lower() for token in current}
    prepend = [path for path in registered if path.lower() not in current_keys]
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + current)
    return tuple(registered)


def locate_dlls(names: Iterable[str], directories: Iterable[Path] | None = None) -> dict[str, str]:
    search = list(directories or candidate_dll_directories())
    result: dict[str, str] = {}
    for name in names:
        lower = name.lower()
        for directory in search:
            candidate = directory / name
            if candidate.is_file():
                result[name] = str(candidate)
                break
            try:
                match = next((item for item in directory.glob("*.dll") if item.name.lower() == lower), None)
            except OSError:
                match = None
            if match is not None:
                result[name] = str(match)
                break
    return result


def cuda12_runtime_report() -> DllResolutionReport:
    required = (
        "cudart64_12.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cufft64_11.dll",
        "cudnn64_9.dll",
    )
    registered = register_windows_dll_directories()
    directories = _unique_existing(Path(item) for item in registered)
    found = locate_dlls(required, directories)
    missing = tuple(name for name in required if name not in found)
    return DllResolutionReport(registered, found, missing)
