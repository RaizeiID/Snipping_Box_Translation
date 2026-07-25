from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SherpaOnnxCompatibilityError(RuntimeError):
    """Raised when the installed sherpa-onnx package lacks the Python API ORT needs."""


@dataclass(frozen=True)
class SherpaOnnxInfo:
    package_version: str
    runtime_version: str
    module_file: str
    recognizer_source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "package_version": self.package_version,
            "runtime_version": self.runtime_version,
            "module_file": self.module_file,
            "recognizer_source": self.recognizer_source,
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
    if paths:
        return ";".join(str(item) for item in paths)
    return "<unknown>"


def resolve_offline_recognizer() -> tuple[type[Any], SherpaOnnxInfo]:
    """Return a compatible OfflineRecognizer class.

    Some Windows environments expose the class only from
    ``sherpa_onnx.offline_recognizer`` even though the official package also
    exports it at the package root. ORT accepts both layouts and restores the
    top-level alias so third-party ReazonSpeech code can use the same process.
    """

    try:
        module = importlib.import_module("sherpa_onnx")
    except Exception as exc:
        raise SherpaOnnxCompatibilityError(
            f"sherpa_onnx tidak dapat diimpor: {type(exc).__name__}: {exc}"
        ) from exc

    recognizer = getattr(module, "OfflineRecognizer", None)
    source = "sherpa_onnx.OfflineRecognizer"
    if recognizer is None or not callable(getattr(recognizer, "from_transducer", None)):
        try:
            submodule = importlib.import_module("sherpa_onnx.offline_recognizer")
            recognizer = getattr(submodule, "OfflineRecognizer", None)
            source = "sherpa_onnx.offline_recognizer.OfflineRecognizer"
        except Exception as exc:
            recognizer = None
            submodule_error = f"{type(exc).__name__}: {exc}"
        else:
            submodule_error = ""

        if recognizer is not None and callable(getattr(recognizer, "from_transducer", None)):
            # Compatibility alias for ReazonSpeech's loader, which expects the
            # class at the package root.
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
    )
    return recognizer, info


def create_offline_transducer(**kwargs: Any) -> tuple[Any, SherpaOnnxInfo]:
    recognizer, info = resolve_offline_recognizer()
    return recognizer.from_transducer(**kwargs), info


def create_offline_sense_voice(**kwargs: Any) -> tuple[Any, SherpaOnnxInfo]:
    recognizer, info = resolve_offline_recognizer()
    factory = getattr(recognizer, "from_sense_voice", None)
    if not callable(factory):
        raise SherpaOnnxCompatibilityError(
            "API OfflineRecognizer.from_sense_voice tidak tersedia pada runtime sherpa-onnx ini."
        )
    return factory(**kwargs), info
