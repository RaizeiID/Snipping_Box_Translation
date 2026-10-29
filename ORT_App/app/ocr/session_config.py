"""Explicit per-launch OCR configuration, independent of shared audio prefs."""
from __future__ import annotations

from app.runtime.resource_levels import (
    normalize_device_resource, normalize_resource_level, normalize_resource_mode,
)

LANGUAGE_CHOICES = [
    ("Inggris", "en"), ("Jepang + Inggris", "ja,en"),
    ("Mandarin sederhana + Inggris", "ch_sim,en"),
    ("Korea + Inggris", "ko,en"), ("Indonesia + Inggris", "id,en"),
]
BASIC_RESOURCES = ("stable", 3, "adaptive")


def launch_options(provider, languages, resource_mode, resource_level, device_resource,
                   workspace="tools") -> dict:
    """Only supported UI language packs and resource tokens cross the launch boundary."""
    languages = str(languages or "en").strip()
    if languages not in {value for _, value in LANGUAGE_CHOICES}:
        raise ValueError("Pilih bahasa sesuai teks yang terlihat di layar.")
    return {
        "ocr_provider": str(provider or "easyocr_craft"),
        "ocr_languages": languages,
        "audio_resource_mode": normalize_resource_mode(resource_mode),
        "audio_resource_level": normalize_resource_level(resource_level),
        "device_resource": normalize_device_resource(device_resource),
        "workspace": "lab" if workspace == "lab" else "tools",
    }


def basic_capture_defaults(base: dict, gpu_available: bool) -> dict:
    """Hidden experimental/manual values cannot leak into a Basic OCR launch."""
    return {
        "mode": "auto", "engine": "hybrid" if gpu_available else "cpu",
        "interval_ms": max(90, int(base["interval_ms"])),
        "ocr_resolution": max(40, min(100, int(base["ocr_resolution"]))),
        "settings_mode": "recommended", "responsive_story_mode": False,
        "diagnostic_profile": "baseline", "mode_buffer_enabled": False,
    }
