from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from .pipeline import pipeline_payload
from .registry import provider
from app.audio.asr_provider_registry import PROVIDER_KOTOBA, normalize_provider_id


EXECUTABLE_AUDIO_PROVIDERS: dict[str, set[str]] = {
    "source": {"ort_wasapi"},
    "vad": {"ort_rms_vad"},
    "asr": {"ort_faster_whisper", "ort_japanese_specialist"},
    "streaming": {"ort_rolling_context", "confirmed_prefix", "local_agreement"},
    "translation": {"ortcore_fast_v2", "ja_en_id_bridge"},
    "overlay": {"ort_overlay"},
}


GAME_LANGUAGE_OPTIONS: dict[str, tuple[str, ...]] = {
    "GFL2_EXILIUM": ("ja_specialist", "zh"),
    "GFL": ("ja_specialist",),
    "GIRLS_FRONTLINE": ("ja_specialist",),
    "WUTHERING_WAVES": ("en", "ja_specialist", "zh", "ko"),
    "WUWA": ("en", "ja_specialist", "zh", "ko"),
    "DAILY_MEDIA": ("auto", "en", "ja_specialist", "zh", "ko"),
}


def normalise_resource_policy(value: str) -> str:
    token = str(value or "normal").strip().lower()
    return token if token in {"efficient", "normal", "optimal"} else "normal"


def normalise_delivery_mode(value: str) -> str:
    token = str(value or "offline").strip().lower()
    aliases = {"local": "offline", "cloud": "online", "azure": "online", "azure_fallback": "hybrid"}
    token = aliases.get(token, token)
    return token if token in {"offline", "online", "hybrid"} else "offline"


def normalise_cloud_provider(value: str) -> str:
    token = str(value or "azure").strip().lower()
    return token if token in {"azure", "google", "aws"} else "azure"


def normalise_game_language(game: str, language: str) -> str:
    game_key = str(game or "DAILY_MEDIA").strip().upper()
    requested = str(language or "auto").strip().lower()
    allowed = GAME_LANGUAGE_OPTIONS.get(game_key)
    if not allowed:
        return requested or "auto"
    if requested in allowed:
        return requested
    if requested in {"ja", "ja-jp", "japanese"} and "ja_specialist" in allowed:
        return "ja_specialist"
    return allowed[0]


def resource_policy_environment(policy: str) -> dict[str, str]:
    token = normalise_resource_policy(policy)
    common = {
        "ORT_AUDIO_RESOURCE_POLICY": token,
        "ORT_AUDIO_DUAL_STREAM": "0",
        "ORT_AUDIO_BACKGROUND_SPECIALIST_CORRECTION": "0",
        "ORT_AUDIO_ALLOW_ARGOS_RECOVERY": "0",
        "ORT_AUDIO_PROVIDER_TRANSPARENCY": "1",
    }
    if token == "efficient":
        common.update({
            "ORT_AUDIO_CONTEXT_WORDS": "48",
            "ORT_TRANSLATION_WATCHDOG_SECONDS": "18",
            "ORT_AUDIO_VRAM_MIN_FREE_MB": "2300",
            "ORT_AUDIO_PREFLIGHT_MAX_STEADY_MS": "900",
        })
    elif token == "optimal":
        common.update({
            "ORT_AUDIO_CONTEXT_WORDS": "64",
            "ORT_TRANSLATION_WATCHDOG_SECONDS": "15",
            "ORT_AUDIO_VRAM_MIN_FREE_MB": "1800",
            "ORT_AUDIO_PREFLIGHT_MAX_STEADY_MS": "1200",
        })
    else:
        common.update({
            "ORT_AUDIO_CONTEXT_WORDS": "72",
            "ORT_TRANSLATION_WATCHDOG_SECONDS": "15",
            "ORT_AUDIO_VRAM_MIN_FREE_MB": "1800",
            "ORT_AUDIO_PREFLIGHT_MAX_STEADY_MS": "1200",
        })
    return common


@dataclass(frozen=True)
class ArchitectureRuntimeValidation:
    ready: bool
    selections: dict[str, str]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    effective_language: str
    effective_processing: str
    agreement_passes: int

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "selections": dict(self.selections),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "effective_language": self.effective_language,
            "effective_processing": self.effective_processing,
            "agreement_passes": self.agreement_passes,
        }


def _normalise_language(language: str, asr_provider: str, translation_route: str) -> str:
    requested = str(language or "auto").strip().lower()
    if requested in {"ja-specialist", "japanese_specialist", "japanese-specialist"}:
        requested = "ja_specialist"
    if asr_provider == "ort_japanese_specialist" and requested in {"", "auto", "ja", "ja-jp", "ja_specialist"}:
        return "ja_specialist"
    if asr_provider == "ort_faster_whisper" and requested == "ja_specialist":
        return "ja"
    # The bridge receives English from Whisper's translate task. It can therefore
    # accept Japanese, Chinese, or Korean instead of silently forcing every media
    # profile back to Japanese. English uses transcribe -> EN-ID.
    return requested or "auto"


def architecture_runtime_validation(
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    language: str = "auto",
    agreement_passes: int = 2,
) -> ArchitectureRuntimeValidation:
    selections = {
        "source": str(source or ""),
        "vad": str(vad or ""),
        "asr": str(asr or ""),
        "streaming": str(streaming or ""),
        "translation": str(translation or ""),
        "overlay": str(overlay or ""),
    }
    requested_language = str(language or "auto").strip().lower()
    provider_adjusted = False
    if selections["asr"] == "ort_japanese_specialist" and requested_language in {"en", "zh", "ko", "auto"}:
        selections["asr"] = "ort_faster_whisper"
        provider_adjusted = True
    payload = pipeline_payload(
        selections,
        preset_id="runtime:preview",
        label="Open Architecture Runtime Preview",
    )
    errors: list[str] = list(payload.get("errors") or [])
    warnings: list[str] = []
    if provider_adjusted:
        warnings.append("ASR efektif dialihkan ke Faster-Whisper karena bahasa yang dipilih bukan Japanese Specialist.")

    for category, provider_id in selections.items():
        if provider_id not in EXECUTABLE_AUDIO_PROVIDERS[category]:
            errors.append(
                f"{category}: provider '{provider_id}' belum memiliki executor Audio Lab."
            )
            continue
        try:
            spec = provider(provider_id)
            available, reason = spec.availability()
        except Exception as exc:
            errors.append(f"{category}: {exc}")
            continue
        if not available:
            errors.append(f"{category}: {spec.label} belum siap — {reason}")

    if selections["source"] != "ort_wasapi":
        errors.append("Audio Lab saat ini hanya menjalankan ORT WASAPI Loopback atau replay file melalui backend yang sama.")
    if selections["vad"] != "ort_rms_vad":
        errors.append("Silero/Hybrid VAD belum memiliki inferensi runtime Lab; gunakan ORT RMS/VAD Native.")
    if selections["translation"] == "ja_en_id_bridge" and selections["asr"] not in {
        "ort_japanese_specialist", "ort_faster_whisper",
    }:
        errors.append("Japanese bridge memerlukan provider ASR lokal ORT.")
    if selections["streaming"] == "local_agreement":
        warnings.append("Local Agreement memakai confirmed-prefix engine dengan agreement passes minimal 3.")
    if selections["streaming"] == "ort_rolling_context":
        warnings.append("Ini adalah baseline produksi; gunakan untuk pembanding sebelum eksperimen.")

    passes = max(2, min(4, int(agreement_passes or 2)))
    if selections["streaming"] == "local_agreement":
        passes = max(3, passes)

    effective_language = _normalise_language(language, selections["asr"], selections["translation"])
    effective_processing = "vad" if selections["vad"] == "ort_rms_vad" else "normal"

    return ArchitectureRuntimeValidation(
        ready=not errors,
        selections=selections,
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        effective_language=effective_language,
        effective_processing=effective_processing,
        agreement_passes=passes,
    )


def architecture_runtime_validation_text(
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    language: str = "auto",
    agreement_passes: int = 2,
    ui_mode: str = "normal",
) -> str:
    report = architecture_runtime_validation(
        source, vad, asr, streaming, translation, overlay,
        language, agreement_passes,
    )
    developer = str(ui_mode or "normal").strip().lower() in {"developer", "expert"}
    if report.ready:
        lines = [
            "### ✅ Pipeline Audio Lab siap",
            "Tekan **Preload & Mulai Audio Lab**. Overlay baru muncul setelah ASR dan penerjemah siap.",
            "",
            f"- Bahasa efektif: `{report.effective_language}`",
            f"- Pemrosesan: `{report.effective_processing}`",
            f"- Streaming: `{report.selections['streaming']}`",
            f"- Agreement passes: `{report.agreement_passes}`",
            "- Pipeline produksi tidak diubah; satu ProcessManager tetap mencegah dua sesi berjalan bersamaan.",
            "- Runtime Python, model ASR, WASAPI, dan CUDA diverifikasi kembali oleh backend saat Start.",
            "- Strategi terjemahan internal dikunci ke ORTCore Fast V2; pilihan model OCR tidak lagi ditampilkan pada Audio Lab.",
        ]
    else:
        lines = [
            "### ⛔ Pipeline Audio Lab belum dapat dimulai",
            "Perbaiki provider berikut sebelum menekan **Mulai Audio Lab**:",
            "",
            *[f"- {item}" for item in report.errors],
        ]
    if report.warnings:
        lines.extend(["", "**Catatan:**", *[f"- {item}" for item in report.warnings]])
    if developer:
        lines.extend([
            "",
            "**Developer contract**",
            f"- source = `{report.selections['source']}`",
            f"- vad = `{report.selections['vad']}`",
            f"- asr = `{report.selections['asr']}`",
            f"- streaming = `{report.selections['streaming']}`",
            f"- translation = `{report.selections['translation']}`",
            f"- overlay = `{report.selections['overlay']}`",
            "- session marker = `ORT_OPEN_ARCHITECTURE_LAB=1`",
        ])
    return "\n".join(lines)


@contextmanager
def _lab_environment(
    report: ArchitectureRuntimeValidation,
    preset_id: str = "custom",
    *,
    overlay_mode: str = "adaptive",
    overlay_width_percent: int = 92,
    overlay_height_px: int = 190,
    overlay_font_size: int = 15,
    overlay_opacity_percent: int = 91,
    overlay_show_source: bool = True,
    overlay_alignment: str = "left",
    resource_policy: str = "normal",
    game_profile: str = "DAILY_MEDIA",
    asr_model_provider: str = "kotoba_bilingual",
    model_lock: bool = True,
    delivery_mode: str = "offline",
    cloud_provider: str = "azure",
) -> Iterator[None]:
    mode = str(overlay_mode or "adaptive").strip().lower()
    if mode not in {"adaptive", "fixed", "custom"}:
        mode = "adaptive"
    updates = {
        "ORT_OPEN_ARCHITECTURE_LAB": "1",
        "ORT_OA_PRESET_ID": str(preset_id or "custom"),
        "ORT_OA_SOURCE_PROVIDER": report.selections["source"],
        "ORT_OA_VAD_PROVIDER": report.selections["vad"],
        "ORT_OA_ASR_PROVIDER": report.selections["asr"],
        "ORT_OA_STREAMING_POLICY": report.selections["streaming"],
        "ORT_OA_TRANSLATION_ROUTE": report.selections["translation"],
        "ORT_OA_OVERLAY_PROVIDER": report.selections["overlay"],
        "ORT_AUDIO_STREAMING_POLICY": report.selections["streaming"],
        "ORT_AUDIO_TRANSLATION_ROUTE": report.selections["translation"],
        "ORT_AUDIO_AGREEMENT_PASSES": str(report.agreement_passes),
        "ORT_AUDIO_SMART_SEGMENTATION": "1",
        "ORT_AUDIO_OVERLAY_MODE": mode,
        "ORT_AUDIO_OVERLAY_WIDTH_PERCENT": str(max(40, min(100, int(overlay_width_percent or 92)))),
        "ORT_AUDIO_OVERLAY_HEIGHT_PX": str(max(100, min(720, int(overlay_height_px or 190)))),
        "ORT_AUDIO_OVERLAY_FONT_SIZE": str(max(10, min(30, int(overlay_font_size or 15)))),
        "ORT_AUDIO_OVERLAY_OPACITY_PERCENT": str(max(45, min(100, int(overlay_opacity_percent or 91)))),
        "ORT_AUDIO_OVERLAY_SHOW_SOURCE": "1" if overlay_show_source else "0",
        "ORT_AUDIO_OVERLAY_ALIGNMENT": "center" if str(overlay_alignment or "left").lower() == "center" else "left",
        "ORT_AUDIO_USAGE_PROFILE": str(game_profile or "DAILY_MEDIA").upper(),
        "ORT_AUDIO_ASR_PROVIDER": normalize_provider_id(asr_model_provider),
        "ORT_AUDIO_MODEL_LOCK": "1" if model_lock else "0",
        "ORT_AUDIO_DELIVERY_MODE": normalise_delivery_mode(delivery_mode),
        "ORT_AUDIO_CLOUD_PROVIDER": normalise_cloud_provider(cloud_provider),
    }
    updates.update(resource_policy_environment(resource_policy))
    previous = {key: os.environ.get(key) for key in updates}
    try:
        os.environ.update(updates)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def architecture_start_audio(
    game: str,
    input_mode: str,
    device_index: str,
    language: str,
    audio_mode: str,
    profile: str,
    test_file: str,
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    agreement_passes: int = 2,
    language_correction: str = "balanced",
    language_lock: bool = False,
    preset_id: str = "custom",
    overlay_mode: str = "adaptive",
    overlay_width_percent: int = 92,
    overlay_height_px: int = 190,
    overlay_font_size: int = 15,
    overlay_opacity_percent: int = 91,
    overlay_show_source: bool = True,
    overlay_alignment: str = "left",
    resource_policy: str = "normal",
    asr_model_provider: str = "kotoba_bilingual",
    model_lock: bool = True,
    delivery_mode: str = "offline",
    cloud_provider: str = "azure",
):
    effective_language = normalise_game_language(game, language)
    report = architecture_runtime_validation(
        source, vad, asr, streaming, translation, overlay,
        effective_language, agreement_passes,
    )
    if not report.ready:
        message = "Audio Lab diblokir:\n" + "\n".join(f"- {item}" for item in report.errors)
        return "STATUS: ERROR", "", message, ""

    selected_provider = normalize_provider_id(asr_model_provider)
    if bool(model_lock) and selected_provider == "auto":
        return "STATUS: ERROR", "", "Model lock memerlukan provider eksplisit; Auto tidak diizinkan.", ""
    delivery = normalise_delivery_mode(delivery_mode)
    cloud = normalise_cloud_provider(cloud_provider)
    if delivery in {"online", "hybrid"} and cloud != "azure":
        return (
            "STATUS: ERROR", "",
            f"Cloud provider {cloud.upper()} masih benchmark-catalog only pada v9.0.5. Gunakan Azure untuk live Online/Hybrid.",
            "",
        )
    audio_engine = "local" if delivery == "offline" else ("azure" if delivery == "online" else "azure_fallback")

    from launcher_backend import start_audio_model

    # Audio Lab uses a fixed internal translation strategy. The old WebUI field
    # reused OCR model choices and did not select the Japanese ASR model.
    internal_translation_model = "ORTCore Fast V2"
    with _lab_environment(
        report,
        preset_id=preset_id,
        overlay_mode=overlay_mode,
        overlay_width_percent=overlay_width_percent,
        overlay_height_px=overlay_height_px,
        overlay_font_size=overlay_font_size,
        overlay_opacity_percent=overlay_opacity_percent,
        overlay_show_source=overlay_show_source,
        overlay_alignment=overlay_alignment,
        resource_policy=resource_policy,
        game_profile=game,
        asr_model_provider=selected_provider,
        model_lock=bool(model_lock),
        delivery_mode=delivery,
        cloud_provider=cloud,
    ):
        os.environ["ORT_AUDIO_JA_SPECIALIST"] = "1" if selected_provider == PROVIDER_KOTOBA else "0"
        return start_audio_model(
            internal_translation_model,
            game,
            input_mode,
            device_index,
            report.effective_language,
            report.effective_processing,
            profile,
            test_file,
            audio_mode,
            "live_media",
            audio_engine,
            language_correction,
            bool(language_lock),
        )
