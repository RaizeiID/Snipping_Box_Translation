from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PROVIDER_AUTO = "auto"
PROVIDER_KOTOBA = "kotoba_bilingual"
PROVIDER_REAZON = "reazonspeech_k2"
PROVIDER_SENSEVOICE = "sensevoice_small"
PROVIDER_WHISPER_BASE = "faster_whisper_base"
PROVIDER_WHISPER_SMALL = "faster_whisper_small"


@dataclass(frozen=True)
class ASRProviderSpec:
    provider_id: str
    label: str
    owner: str
    backend: str
    license: str
    source_url: str
    purpose: str
    output_language: str
    bridge_language: str
    task: str
    supported_devices: tuple[str, ...]
    recommended_for: str
    experimental: bool = False

    def as_dict(self) -> dict:
        data = asdict(self)
        data["supported_devices"] = list(self.supported_devices)
        return data


PROVIDERS: dict[str, ASRProviderSpec] = {
    PROVIDER_AUTO: ASRProviderSpec(
        PROVIDER_AUTO,
        "Auto · ORT Recommendation",
        "ORT",
        "provider resolver",
        "ORT project",
        "",
        "Select a provider from the current resource and language profile.",
        "dynamic",
        "dynamic",
        "dynamic",
        ("cpu", "cuda"),
        "Convenience only; not used when model lock is enabled.",
    ),
    PROVIDER_KOTOBA: ASRProviderSpec(
        PROVIDER_KOTOBA,
        "Kotoba Bilingual · Current",
        "Kotoba Technologies",
        "Faster-Whisper / CTranslate2",
        "Apache-2.0 source model; MIT converted weights",
        "https://huggingface.co/kotoba-tech/kotoba-whisper-bilingual-v1.0-faster",
        "Japanese speech to English bridge, plus Japanese/English ASR.",
        "en",
        "en",
        "translate",
        ("cpu", "cuda"),
        "GPU when headroom is available; bounded CPU mode for comparison.",
    ),
    PROVIDER_REAZON: ASRProviderSpec(
        PROVIDER_REAZON,
        "ReazonSpeech K2 · Japanese Stable",
        "Reazon Human Interaction Lab",
        "reazonspeech.k2.asr / sherpa-onnx",
        "Apache-2.0",
        "https://github.com/reazon-research/ReazonSpeech",
        "Compact Japanese transcription with a 159M-parameter K2/Zipformer model.",
        "ja",
        "ja",
        "transcribe",
        ("cpu", "cuda"),
        "Game sessions and low-VRAM systems; preferred Japanese CPU candidate.",
    ),
    PROVIDER_SENSEVOICE: ASRProviderSpec(
        PROVIDER_SENSEVOICE,
        "SenseVoice-Small · Japanese Fast",
        "FunAudioLLM",
        "sherpa-onnx SenseVoice CTC",
        "FunASR Model License; attribution required",
        "https://github.com/FunAudioLLM/SenseVoice",
        "Fast multilingual transcription with language/audio-event tokens.",
        "ja",
        "ja",
        "transcribe",
        ("cpu",),
        "Fast CPU benchmark and dialogue/BGM discrimination experiments.",
        experimental=True,
    ),
    PROVIDER_WHISPER_BASE: ASRProviderSpec(
        PROVIDER_WHISPER_BASE,
        "Faster-Whisper Base · Baseline",
        "OpenAI / SYSTRAN",
        "Faster-Whisper / CTranslate2",
        "MIT runtime; Whisper model license",
        "https://github.com/SYSTRAN/faster-whisper",
        "Small baseline used to compare speed against Japanese-specialized providers.",
        "en",
        "en",
        "translate",
        ("cpu", "cuda"),
        "Diagnostic baseline only for Japanese; acceptable for English media.",
    ),
    PROVIDER_WHISPER_SMALL: ASRProviderSpec(
        PROVIDER_WHISPER_SMALL,
        "Faster-Whisper Small · Baseline Accurate",
        "OpenAI / SYSTRAN",
        "Faster-Whisper / CTranslate2",
        "MIT runtime; Whisper model license",
        "https://github.com/SYSTRAN/faster-whisper",
        "Larger generic Whisper baseline.",
        "en",
        "en",
        "translate",
        ("cpu", "cuda"),
        "Comparison provider; GPU recommended.",
    ),
}


def normalize_provider_id(value: str, *, japanese: bool = True) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "": PROVIDER_KOTOBA if japanese else PROVIDER_WHISPER_BASE,
        "auto": PROVIDER_AUTO,
        "kotoba": PROVIDER_KOTOBA,
        "kotoba_bilingual": PROVIDER_KOTOBA,
        "ort_japanese_specialist": PROVIDER_KOTOBA,
        "reazon": PROVIDER_REAZON,
        "reazonspeech": PROVIDER_REAZON,
        "reazonspeech_k2": PROVIDER_REAZON,
        "sensevoice": PROVIDER_SENSEVOICE,
        "sensevoice_small": PROVIDER_SENSEVOICE,
        "base": PROVIDER_WHISPER_BASE,
        "faster_whisper_base": PROVIDER_WHISPER_BASE,
        "small": PROVIDER_WHISPER_SMALL,
        "faster_whisper_small": PROVIDER_WHISPER_SMALL,
    }
    result = aliases.get(token, token)
    return result if result in PROVIDERS else (PROVIDER_KOTOBA if japanese else PROVIDER_WHISPER_BASE)


def provider_choices(*, include_auto: bool = False) -> list[tuple[str, str]]:
    ids = [
        PROVIDER_KOTOBA,
        PROVIDER_REAZON,
        PROVIDER_SENSEVOICE,
        PROVIDER_WHISPER_BASE,
        PROVIDER_WHISPER_SMALL,
    ]
    if include_auto:
        ids.insert(0, PROVIDER_AUTO)
    return [(PROVIDERS[item].label, item) for item in ids]


def _runtime_text_probe(runtime_python: Path | None, code: str, timeout: int = 20) -> tuple[bool, str]:
    if runtime_python is None or not Path(runtime_python).is_file():
        return False, "runtime python unavailable"
    try:
        result = subprocess.run(
            [str(runtime_python), "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
        return result.returncode == 0, output
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _module_available(name: str, runtime_python: Path | None = None) -> bool:
    if runtime_python is not None and Path(runtime_python).is_file():
        try:
            result = subprocess.run(
                [str(runtime_python), "-c", f"import {name}"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        try:
            if path.exists():
                return path.resolve()
        except Exception:
            continue
    return None


def provider_model_candidates(model_root: Path, provider_id: str) -> list[Path]:
    root = Path(model_root).expanduser().resolve()
    provider_id = normalize_provider_id(provider_id)
    if provider_id == PROVIDER_KOTOBA:
        return [
            root / "kotoba-whisper-bilingual-v1.0-faster",
            root / "faster-whisper-kotoba-bilingual-v1.0",
            root / "kotoba-bilingual",
        ]
    if provider_id == PROVIDER_SENSEVOICE:
        return [
            root / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09",
            root / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
            root / "sensevoice-small-sherpa-onnx",
            root / "sensevoice-small",
        ]
    if provider_id == PROVIDER_WHISPER_BASE:
        return [root / "faster-whisper-base", root / "base"]
    if provider_id == PROVIDER_WHISPER_SMALL:
        return [root / "faster-whisper-small", root / "small"]
    return []


def provider_status(model_root: Path, provider_id: str, device: str = "cpu", runtime_python: Path | None = None) -> dict:
    provider_id = normalize_provider_id(provider_id)
    spec = PROVIDERS[provider_id]
    requested_device = str(device or "cpu").lower()
    errors: list[str] = []
    warnings: list[str] = []
    location: Path | None = None

    if provider_id == PROVIDER_AUTO:
        return {
            **spec.as_dict(),
            "ready": True,
            "device_ready": True,
            "model_path": "resolved at start",
            "errors": [],
            "warnings": ["Auto is incompatible with hard model lock."],
        }

    if requested_device not in spec.supported_devices:
        errors.append(f"Provider supports {', '.join(spec.supported_devices)}, not {requested_device}.")

    if provider_id in {PROVIDER_KOTOBA, PROVIDER_WHISPER_BASE, PROVIDER_WHISPER_SMALL}:
        if not _module_available("faster_whisper", runtime_python):
            errors.append("Python module faster_whisper is not installed in the selected runtime.")
        location = _first_existing(provider_model_candidates(model_root, provider_id))
        if location is None:
            errors.append("Model folder is not present under the Audio model root.")
    elif provider_id == PROVIDER_REAZON:
        if not _module_available("reazonspeech.k2.asr", runtime_python):
            errors.append("reazonspeech.k2.asr is not installed.")
        if not _module_available("sherpa_onnx", runtime_python):
            errors.append("sherpa_onnx is not installed.")
        else:
            ok, version_text = _runtime_text_probe(
                runtime_python,
                "import sherpa_onnx; print(getattr(sherpa_onnx,'__version__','unknown'))",
            )
            if not ok:
                errors.append("sherpa_onnx runtime probe failed: " + version_text[-400:])
            elif requested_device == "cuda" and "+cuda" not in version_text.lower():
                errors.append(
                    "CUDA runtime belum terpasang; sherpa-onnx yang aktif adalah build CPU "
                    f"({version_text or 'unknown'}). Jalankan setup Reazon dengan Perangkat ASR GPU/Hybrid."
                )
            elif requested_device == "cuda":
                warnings.append(f"CUDA-enabled sherpa-onnx detected: {version_text}")
            else:
                warnings.append(f"sherpa-onnx runtime: {version_text}")
        location = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
        warnings.append("Reazon CPU dan CUDA memakai weight K2 yang sama di Hugging Face cache; yang berbeda adalah runtime sherpa-onnx.")
    elif provider_id == PROVIDER_SENSEVOICE:
        if not _module_available("sherpa_onnx", runtime_python):
            errors.append("sherpa_onnx is not installed.")
        location = _first_existing(provider_model_candidates(model_root, provider_id))
        if location is None:
            errors.append("SenseVoice sherpa-onnx model folder is missing.")
        elif not ((location / "model.int8.onnx").is_file() or (location / "model.onnx").is_file()):
            errors.append("SenseVoice model.onnx/model.int8.onnx is missing.")
        if location is not None and not (location / "tokens.txt").is_file():
            errors.append("SenseVoice tokens.txt is missing.")

    return {
        **spec.as_dict(),
        "ready": not errors,
        "device_ready": requested_device in spec.supported_devices,
        "model_path": str(location) if location is not None else "",
        "errors": errors,
        "warnings": warnings,
    }


def all_provider_statuses(model_root: Path, device: str = "cpu", runtime_python: Path | None = None) -> list[dict]:
    return [
        provider_status(model_root, provider_id, device, runtime_python)
        for provider_id in (
            PROVIDER_KOTOBA,
            PROVIDER_REAZON,
            PROVIDER_SENSEVOICE,
            PROVIDER_WHISPER_BASE,
            PROVIDER_WHISPER_SMALL,
        )
    ]


def status_markdown(model_root: Path, selected_provider: str, device: str = "cpu", runtime_python: Path | None = None) -> str:
    selected = normalize_provider_id(selected_provider)
    rows = []
    for item in all_provider_statuses(model_root, device, runtime_python):
        marker = "🔒" if item["provider_id"] == selected else ""
        state = "READY" if item["ready"] else "SETUP REQUIRED"
        details = "; ".join(item["errors"][:2]) or item["recommended_for"]
        rows.append(
            f"| {marker} {item['label']} | {state} | {item['backend']} | {', '.join(item['supported_devices'])} | {details} |"
        )
    return "\n".join([
        "### ASR provider status",
        "Model lock means the selected provider never changes automatically during a session.",
        "",
        "| Provider | Status | Backend | Device | Detail |",
        "|---|---|---|---|---|",
        *rows,
    ])


def write_status_json(path: Path, model_root: Path, selected_provider: str, device: str, runtime_python: Path | None = None) -> None:
    payload = {
        "selected_provider": normalize_provider_id(selected_provider),
        "device": device,
        "providers": all_provider_statuses(model_root, device, runtime_python),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
