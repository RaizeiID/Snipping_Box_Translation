"""ORT v9 Open Architecture Lab.

This package is deliberately isolated from the production OCR/audio pipeline.
It provides provider metadata, experimental pipeline planning, compatibility
checks, and deterministic streaming-policy demos without replacing ORT Native.
"""

from .executor import (
    architecture_runtime_validation,
    architecture_runtime_validation_text,
    architecture_start_audio,
)

from .lab import (
    architecture_apply_preset,
    architecture_compare_presets,
    architecture_export_plan,
    architecture_initial_payload,
    architecture_provider_choices,
    architecture_preset_choices,
    architecture_refresh,
    architecture_save_custom,
    confirmed_prefix_demo,
)

__all__ = [
    "architecture_apply_preset",
    "architecture_compare_presets",
    "architecture_export_plan",
    "architecture_initial_payload",
    "architecture_provider_choices",
    "architecture_preset_choices",
    "architecture_refresh",
    "architecture_save_custom",
    "architecture_runtime_validation",
    "architecture_runtime_validation_text",
    "architecture_start_audio",
    "confirmed_prefix_demo",
]
