from __future__ import annotations

import ctypes
import os
import site
import sys
from pathlib import Path
from typing import Any

_DLL_HANDLES: list[Any] = []
_ACTIVE_DIRS: list[str] = []


def _unique_existing(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            continue
        key = str(resolved).lower()
        if key in seen or not resolved.is_dir():
            continue
        seen.add(key)
        result.append(resolved)
    return result


def discover_cuda_dll_directories() -> list[Path]:
    candidates: list[Path] = []
    explicit = str(os.environ.get("ORT_AUDIO_CUDA_DLL_DIRS", "") or "")
    for item in explicit.split(os.pathsep):
        if item.strip():
            candidates.append(Path(item.strip()))

    site_roots: list[Path] = []
    try:
        site_roots.extend(Path(item) for item in site.getsitepackages())
    except Exception:
        pass
    try:
        site_roots.append(Path(site.getusersitepackages()))
    except Exception:
        pass
    site_roots.extend([Path(sys.prefix) / "Lib" / "site-packages", Path(sys.base_prefix) / "Lib" / "site-packages"])
    for root in _unique_existing(site_roots):
        nvidia_root = root / "nvidia"
        if not nvidia_root.is_dir():
            continue
        for component in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            base = nvidia_root / component
            candidates.extend([base / "bin", base / "lib", base / "lib" / "x64"])
        for child in nvidia_root.iterdir():
            if child.is_dir():
                candidates.extend([child / "bin", child / "lib", child / "lib" / "x64"])

    for key in ("CUDA_PATH", "CUDA_HOME", "CUDNN_PATH"):
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            root = Path(value)
            candidates.extend([root / "bin", root / "lib" / "x64"])

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    cuda_root = program_files / "NVIDIA GPU Computing Toolkit" / "CUDA"
    if cuda_root.is_dir():
        for child in sorted(cuda_root.glob("v12*"), reverse=True):
            candidates.append(child / "bin")
    cudnn_root = program_files / "NVIDIA" / "CUDNN"
    if cudnn_root.is_dir():
        for child in sorted(cudnn_root.glob("v9*"), reverse=True):
            candidates.append(child / "bin")

    return _unique_existing(candidates)


def activate_cuda_dll_search() -> dict[str, Any]:
    global _DLL_HANDLES, _ACTIVE_DIRS
    directories = discover_cuda_dll_directories()
    path_parts = [str(item) for item in directories]
    current = [item for item in os.environ.get("PATH", "").split(os.pathsep) if item]
    lowered = {item.lower() for item in path_parts}
    os.environ["PATH"] = os.pathsep.join(path_parts + [item for item in current if item.lower() not in lowered])

    handles: list[Any] = []
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for directory in directories:
            try:
                handles.append(os.add_dll_directory(str(directory)))
            except Exception:
                continue
    _DLL_HANDLES.extend(handles)
    _ACTIVE_DIRS = path_parts
    return {"activated": bool(path_parts), "directories": path_parts, "handles": len(handles)}


def _load_named_dll(name: str) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Windows-only DLL check"
    try:
        ctypes.WinDLL(name)
        return True, "loaded"
    except Exception as exc:
        return False, str(exc)


def cuda_runtime_report() -> dict[str, Any]:
    activation = activate_cuda_dll_search()
    required = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll")
    optional = ("cudart64_12.dll", "nvrtc64_120_0.dll", "nvrtc64_12.dll")
    dlls = {name: dict(zip(("available", "detail"), _load_named_dll(name))) for name in required}
    optional_dlls = {name: dict(zip(("available", "detail"), _load_named_dll(name))) for name in optional}
    ct2: dict[str, Any] = {"available": False, "cuda_device_count": 0, "detail": ""}
    try:
        import ctranslate2
        ct2["available"] = True
        ct2["version"] = getattr(ctranslate2, "__version__", "")
        ct2["cuda_device_count"] = int(ctranslate2.get_cuda_device_count())
    except Exception as exc:
        ct2["detail"] = str(exc)
    return {
        "activation": activation,
        "required_dlls": dlls,
        "optional_dlls": optional_dlls,
        "ctranslate2": ct2,
        "passed": bool(ct2["available"] and ct2["cuda_device_count"] > 0 and all(item["available"] for item in dlls.values())),
    }
