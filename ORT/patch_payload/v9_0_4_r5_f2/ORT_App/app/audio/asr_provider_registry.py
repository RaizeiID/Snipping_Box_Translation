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

REAZON_LOCAL_DIR = "reazonspeech-k2-v2"
REAZON_FILE_SIZES = {
    "tokens.txt": 45754,
    "encoder-epoch-99-avg-1.int8.onnx": 154670139,
    "decoder-epoch-99-avg-1.int8.onnx": 2959337,
    "decoder-epoch-99-avg-1.onnx": 11767836,
    "joiner-epoch-99-avg-1.int8.onnx": 2696970,
}
REAZON_DEVICE_FILES = {
    "cpu": ("tokens.txt", "encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.int8.onnx", "joiner-epoch-99-avg-1.int8.onnx"),
    "cuda": ("tokens.txt", "encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.onnx", "joiner-epoch-99-avg-1.int8.onnx"),
}


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
    if provider_id == PROVIDER_REAZON:
        return [root / REAZON_LOCAL_DIR]
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




def _human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def provider_setup_status_root(model_root: Path) -> Path:
    root = Path(model_root).expanduser().resolve()
    try:
        return root.parent.parent / "provider_setup_status"
    except Exception:
        return root / ".provider_setup_status"


def _load_setup_marker(model_root: Path, provider_id: str, device: str) -> dict:
    path = provider_setup_status_root(model_root) / f"{provider_id}_{device}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data["status_path"] = str(path)
            return data
    except Exception:
        pass
    return {}


def _marker_file_health(marker: dict) -> tuple[bool, int, list[str]]:
    errors: list[str] = []
    files = marker.get("model_files") or []
    total = int(marker.get("model_total_bytes", 0) or 0)
    downloaded = 0
    if files:
        for item in files:
            try:
                path = Path(str(item.get("path") or ""))
                expected = int(item.get("size", 0) or 0)
                if not path.is_file():
                    errors.append(f"File model hilang: {path}")
                    continue
                actual = int(path.stat().st_size)
                if expected and actual < expected:
                    errors.append(f"File model belum lengkap: {path.name} ({actual}/{expected} byte)")
                    continue
                downloaded += expected or actual
            except Exception as exc:
                errors.append(f"Pemeriksaan file model gagal: {exc}")
    else:
        downloaded = int(marker.get("model_downloaded_bytes", 0) or 0)
    complete = bool(marker.get("model_complete")) and bool(total) and downloaded >= total and not errors
    return complete, downloaded, errors

def provider_status(model_root: Path, provider_id: str, device: str = "cpu", runtime_python: Path | None = None) -> dict:
    provider_id = normalize_provider_id(provider_id)
    spec = PROVIDERS[provider_id]
    requested_device = str(device or "cpu").lower()
    errors: list[str] = []
    warnings: list[str] = []
    location: Path | None = None
    marker = _load_setup_marker(model_root, provider_id, requested_device)
    marker_complete, marker_downloaded, marker_errors = _marker_file_health(marker) if marker else (False, 0, [])
    marker_total = int(marker.get("model_total_bytes", 0) or 0) if marker else 0

    if provider_id == PROVIDER_AUTO:
        return {
            **spec.as_dict(), "ready": True, "device_ready": True,
            "model_path": "resolved at start", "errors": [],
            "warnings": ["Auto is incompatible with hard model lock."],
            "status_level": "ready", "model_total_bytes": 0,
            "model_downloaded_bytes": 0, "model_complete": True,
        }

    if requested_device not in spec.supported_devices:
        return {
            **spec.as_dict(), "ready": False, "device_ready": False,
            "model_path": "", "errors": [f"Provider tidak mendukung {requested_device}."],
            "warnings": [], "status_level": "unsupported",
            "model_total_bytes": marker_total,
            "model_downloaded_bytes": marker_downloaded,
            "model_complete": False, "bridge_ready": None,
            "status_path": marker.get("status_path", "") if marker else "",
        }

    if marker_errors:
        errors.extend(marker_errors)

    if provider_id in {PROVIDER_KOTOBA, PROVIDER_WHISPER_BASE, PROVIDER_WHISPER_SMALL}:
        if not _module_available("faster_whisper", runtime_python):
            errors.append("Python module faster_whisper belum terpasang pada runtime device ini.")
        location = _first_existing(provider_model_candidates(model_root, provider_id))
        if location is None:
            errors.append("Folder model belum tersedia di Audio model root.")
    elif provider_id == PROVIDER_REAZON:
        if not _module_available("reazonspeech.k2.asr", runtime_python):
            errors.append("reazonspeech.k2.asr belum terpasang.")
        if not _module_available("sherpa_onnx", runtime_python):
            errors.append("sherpa_onnx belum terpasang.")
        else:
            ok, version_text = _runtime_text_probe(
                runtime_python,
                "import sherpa_onnx; print(getattr(sherpa_onnx,'__version__','unknown'))",
            )
            if not ok:
                errors.append("Probe sherpa_onnx gagal: " + version_text[-400:])
            elif requested_device == "cuda" and "+cuda" not in version_text.lower():
                errors.append(f"Runtime GPU masih build CPU ({version_text or 'unknown'}).")
            else:
                warnings.append(f"sherpa-onnx runtime: {version_text}")
        location = _first_existing(provider_model_candidates(model_root, provider_id))
        if location is None:
            location = Path(model_root).expanduser().resolve() / REAZON_LOCAL_DIR
            errors.append("Folder model lokal Reazon belum tersedia.")
        required = REAZON_DEVICE_FILES["cuda" if requested_device == "cuda" else "cpu"]
        for filename in required:
            path = location / filename
            expected = REAZON_FILE_SIZES[filename]
            if not path.is_file():
                errors.append(f"File Reazon belum tersedia: {filename}")
            elif path.stat().st_size != expected:
                errors.append(f"File Reazon belum lengkap: {filename} ({path.stat().st_size}/{expected} byte)")
        warnings.append("Weight Reazon disimpan pada Audio model root dan dipakai bersama CPU/GPU.")
    elif provider_id == PROVIDER_SENSEVOICE:
        if not _module_available("sherpa_onnx", runtime_python):
            errors.append("sherpa_onnx belum terpasang.")
        location = _first_existing(provider_model_candidates(model_root, provider_id))
        if location is None:
            errors.append("Folder model SenseVoice belum tersedia.")
        elif not ((location / "model.int8.onnx").is_file() or (location / "model.onnx").is_file()):
            errors.append("model.onnx/model.int8.onnx belum lengkap.")
        if location is not None and not (location / "tokens.txt").is_file():
            errors.append("tokens.txt belum tersedia.")

    bridge_ready: bool | None = None
    if spec.output_language == "ja":
        bridge = _load_setup_marker(model_root, "argos_bridge", requested_device)
        bridge_ready = bool(bridge.get("bridge_ready") and bridge.get("runtime_ready"))
        if not bridge_ready:
            errors.append(f"Bridge Jepang→Inggris→Indonesia belum siap pada runtime {requested_device.upper()}.")

    if marker:
        if not marker_complete:
            errors.append("Manifest download R4 menunjukkan model belum lengkap.")
        if not marker.get("runtime_ready"):
            errors.append("Probe runtime device belum lulus.")
    else:
        warnings.append("Belum ada manifest instalasi R4; status legacy tidak dapat dipastikan sepenuhnya.")

    legacy_model_present = location is not None and location.exists()
    ready = bool(marker and marker_complete and marker.get("runtime_ready") and not errors)
    if ready:
        level = "ready"
    elif marker or errors:
        level = "missing"
    elif legacy_model_present:
        level = "partial"
    else:
        level = "missing"

    return {
        **spec.as_dict(),
        "ready": ready,
        "device_ready": requested_device in spec.supported_devices,
        "model_path": str(location) if location is not None else str(marker.get("model_path") or ""),
        "errors": errors,
        "warnings": warnings,
        "status_level": level,
        "model_total_bytes": marker_total,
        "model_downloaded_bytes": marker_downloaded,
        "model_total_human": _human_bytes(marker_total),
        "model_downloaded_human": _human_bytes(marker_downloaded),
        "model_complete": marker_complete,
        "bridge_ready": bridge_ready,
        "status_path": marker.get("status_path", "") if marker else "",
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
