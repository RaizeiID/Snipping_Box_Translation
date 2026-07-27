from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .windows_dll_resolver import cuda12_runtime_report, register_windows_dll_directories


class SherpaOnnxCompatibilityError(RuntimeError):
    """Raised when the installed sherpa-onnx package lacks the API or DLLs ORT needs."""


@dataclass(frozen=True)
class SherpaOnnxInfo:
    package_version: str
    runtime_version: str
    module_file: str
    recognizer_source: str
    dll_paths: tuple[str, ...] = ()
    missing_dlls: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "package_version": self.package_version,
            "runtime_version": self.runtime_version,
            "module_file": self.module_file,
            "recognizer_source": self.recognizer_source,
            "dll_paths": list(self.dll_paths),
            "missing_dlls": list(self.missing_dlls),
        }


def _package_version() -> str:
    for distribution in ("sherpa-onnx", "sherpa_onnx"):
        try:
            return str(importlib.metadata.version(distribution))
        except importlib.metadata.PackageNotFoundError:
            continue
        except Exception:
            break
    return "unknown"


def _runtime_version(module: Any) -> str:
    for name in ("__version__", "version"):
        value = getattr(module, name, "")
        if callable(value):
            try:
                value = value()
            except Exception:
                value = ""
        text = str(value or "").strip()
        if text:
            return text
    return "unknown"


def _module_file(module: Any) -> str:
    value = getattr(module, "__file__", "")
    if value:
        try:
            return str(Path(value).resolve(strict=False))
        except Exception:
            return str(value)
    paths = getattr(module, "__path__", None)
    return ";".join(str(item) for item in paths) if paths else "<unknown>"


def resolve_offline_recognizer(*, provider: str = "cpu") -> tuple[type[Any], SherpaOnnxInfo]:
    # Register CUDA/PyTorch/NVIDIA wheel directories before importing the native extension.
    dll_paths = register_windows_dll_directories()
    missing_dlls: tuple[str, ...] = ()
    if str(provider or "cpu").lower() in {"cuda", "gpu"}:
        report = cuda12_runtime_report()
        dll_paths = report.registered_paths
        missing_dlls = report.missing

    try:
        module = importlib.import_module("sherpa_onnx")
    except Exception as exc:
        suffix = f" DLL CUDA belum ditemukan: {', '.join(missing_dlls)}." if missing_dlls else ""
        raise SherpaOnnxCompatibilityError(
            f"sherpa_onnx tidak dapat diimpor: {type(exc).__name__}: {exc}.{suffix}"
        ) from exc

    recognizer = getattr(module, "OfflineRecognizer", None)
    source = "sherpa_onnx.OfflineRecognizer"
    if recognizer is None or not callable(getattr(recognizer, "from_transducer", None)):
        submodule_error = ""
        try:
            submodule = importlib.import_module("sherpa_onnx.offline_recognizer")
            recognizer = getattr(submodule, "OfflineRecognizer", None)
            source = "sherpa_onnx.offline_recognizer.OfflineRecognizer"
        except Exception as exc:
            recognizer = None
            submodule_error = f"{type(exc).__name__}: {exc}"

        if recognizer is not None and callable(getattr(recognizer, "from_transducer", None)):
            setattr(module, "OfflineRecognizer", recognizer)
        else:
            available = sorted(name for name in dir(module) if "Recognizer" in name)
            detail = (
                f"module={_module_file(module)!r}, package={_package_version()!r}, "
                f"runtime={_runtime_version(module)!r}, recognizer_symbols={available!r}"
            )
            if submodule_error:
                detail += f", submodule_error={submodule_error}"
            raise SherpaOnnxCompatibilityError(
                "API OfflineRecognizer.from_transducer tidak tersedia. "
                "Runtime sherpa-onnx perlu diperbaiki. " + detail
            )

    info = SherpaOnnxInfo(
        package_version=_package_version(),
        runtime_version=_runtime_version(module),
        module_file=_module_file(module),
        recognizer_source=source,
        dll_paths=dll_paths,
        missing_dlls=missing_dlls,
    )
    return recognizer, info


def create_offline_transducer(**kwargs: Any) -> tuple[Any, SherpaOnnxInfo]:
    provider = str(kwargs.get("provider") or "cpu")
    recognizer, info = resolve_offline_recognizer(provider=provider)
    try:
        return recognizer.from_transducer(**kwargs), info
    except Exception as exc:
        message = str(exc)
        if provider.lower() in {"cuda", "gpu"} and (
            "Failed to load shared library" in message
            or "Error loading" in message
            or "cufft64_11.dll" in message
            or "OrtSessionOptionsAppendExecutionProvider_Cuda" in message
        ):
            report = cuda12_runtime_report()
            missing = ", ".join(report.missing) or "DLL dependency tidak dapat dimuat"
            raise SherpaOnnxCompatibilityError(
                "CUDA sherpa-onnx tidak dapat dimuat. Komponen yang belum ditemukan: "
                f"{missing}. Jalankan repair runtime CUDA ORT v9.0.5 R2. Detail asli: {message}"
            ) from exc
        raise


def create_offline_sense_voice(**kwargs: Any) -> tuple[Any, SherpaOnnxInfo]:
    provider = str(kwargs.get("provider") or "cpu")
    recognizer, info = resolve_offline_recognizer(provider=provider)
    factory = getattr(recognizer, "from_sense_voice", None)
    if not callable(factory):
        raise SherpaOnnxCompatibilityError(
            "API OfflineRecognizer.from_sense_voice tidak tersedia pada runtime sherpa-onnx ini."
        )
    return factory(**kwargs), info
