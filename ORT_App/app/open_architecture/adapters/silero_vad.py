from __future__ import annotations

import importlib.util
from pathlib import Path

from ..paths import runtime_root
from .base import ProviderHealth


class SileroVADAdapter:
    provider_id = "silero_vad"

    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = model_path or runtime_root() / "open_architecture" / "models" / "silero_vad.onnx"

    def health(self) -> ProviderHealth:
        has_runtime = importlib.util.find_spec("onnxruntime") is not None
        has_model = self.model_path.is_file()
        ready = has_runtime and has_model
        if ready:
            message = "Silero VAD adapter siap untuk eksperimen."
        elif not has_runtime:
            message = "onnxruntime belum tersedia pada runtime aktif."
        else:
            message = f"Model Silero belum tersedia: {self.model_path}"
        return ProviderHealth(
            ready,
            "READY" if ready else "SETUP_REQUIRED",
            message,
            {"onnxruntime": has_runtime, "model_exists": has_model, "model_path": str(self.model_path)},
        )
