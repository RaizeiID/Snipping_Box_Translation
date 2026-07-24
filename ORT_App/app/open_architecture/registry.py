from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .paths import plugin_root, runtime_root


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    category: str
    label: str
    origin: str
    license_name: str
    maturity: str
    description: str
    integration: str
    repository: str = ""
    python_module: str = ""
    required_file: str = ""
    default_available: bool = True

    def availability(self) -> tuple[bool, str]:
        if self.python_module and importlib.util.find_spec(self.python_module) is None:
            return False, f"Python module belum tersedia: {self.python_module}"
        if self.required_file:
            required = Path(self.required_file)
            if not required.is_absolute():
                required = runtime_root() / required
            if not required.exists():
                return False, f"File/provider belum dipasang: {required}"
        if not self.default_available:
            return False, "Memerlukan setup eksternal atau implementasi lanjutan."
        return True, "Siap digunakan pada level arsitektur."

    def payload(self) -> dict:
        ready, reason = self.availability()
        data = asdict(self)
        data.update({"available": ready, "availability_reason": reason})
        return data


_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "ort_ocr", "source", "ORT OCR Native", "ORT Native", "ORT Project",
        "Stable", "Capture layar, OCR consensus, identity guard, dan overlay ORT.",
        "Internal provider; pipeline produksi tidak diubah.",
    ),
    ProviderSpec(
        "ort_wasapi", "source", "ORT WASAPI Loopback", "ORT Native", "ORT Project",
        "Stable", "Audio loopback Windows yang sudah digunakan ORT.",
        "Internal provider; menghasilkan PCM untuk provider VAD/ASR.",
    ),
    ProviderSpec(
        "multi_region_ocr", "source", "Multi-Region OCR Adapter", "Adapted Open Source", "MIT-compatible design",
        "Experimental", "Rancangan beberapa ROI dan engine OCR yang terinspirasi arsitektur MORT.",
        "Adapter baru; tidak menyalin aplikasi MORT.",
        "https://github.com/killkimno/MORT", default_available=False,
    ),
    ProviderSpec(
        "external_text_hook", "source", "External Text Hook Connector", "External Connector", "GPL external process",
        "Planned", "Menerima teks dari Textractor/LunaTranslator melalui clipboard, pipe, atau localhost.",
        "Proses eksternal agar kode GPL tidak digabungkan ke ORT.",
        "https://github.com/Artikash/Textractor", default_available=False,
    ),
    ProviderSpec(
        "ort_rms_vad", "vad", "ORT RMS/VAD Native", "ORT Native", "ORT Project",
        "Stable", "Endpointing ringan berbasis RMS, noise floor, dan hangover ORT.",
        "Internal provider produksi.",
    ),
    ProviderSpec(
        "silero_vad", "vad", "Silero VAD ONNX", "Adapted Open Source", "MIT",
        "Testing", "Speech probability multilingual untuk suara pelan, anime, musik, dan efek game.",
        "Adapter opsional; model disimpan di ORT_Runtime.",
        "https://github.com/snakers4/silero-vad", python_module="onnxruntime",
        required_file="open_architecture/models/silero_vad.onnx",
    ),
    ProviderSpec(
        "hybrid_rms_silero", "vad", "Hybrid RMS + Silero", "ORT Integration", "ORT Project + MIT adapter",
        "Experimental", "RMS dipakai sebagai trigger cepat, Silero sebagai konfirmasi speech/endpoint.",
        "Orchestrator ORT menggabungkan dua provider tanpa menimpa ORT Native.",
        python_module="onnxruntime", required_file="open_architecture/models/silero_vad.onnx",
    ),
    ProviderSpec(
        "ort_faster_whisper", "asr", "ORT Faster-Whisper", "ORT Native", "MIT dependencies",
        "Stable", "ASR multilingual CPU/GPU/Hybrid milik pipeline ORT.",
        "Internal provider dengan runtime terisolasi.",
    ),
    ProviderSpec(
        "ort_japanese_specialist", "asr", "ORT Japanese Specialist", "ORT Native", "Model-specific license",
        "Stable", "Kotoba bilingual dengan CUDA preflight dan CPU fallback.",
        "Internal provider ORT; model tetap berada di ORT_Runtime.",
    ),
    ProviderSpec(
        "whisperlive_worker", "asr", "WhisperLive Worker Adapter", "Adapted Open Source", "MIT",
        "Experimental", "Worker ASR persisten, raw PCM streaming, hotwords, dan backpressure.",
        "Adapter subprocess/server lokal; tidak aktif pada pipeline utama.",
        "https://github.com/collabora/WhisperLive", default_available=False,
    ),
    ProviderSpec(
        "ort_rolling_context", "streaming", "ORT Rolling Turn Context", "ORT Native", "ORT Project",
        "Stable", "Konteks turn panjang v8.9.9 F2 dengan live tail yang dapat diganti.",
        "Internal provider produksi.",
    ),
    ProviderSpec(
        "confirmed_prefix", "streaming", "Confirmed Prefix", "Adapted Open Source", "MIT concept",
        "Testing", "Prefix stabil dikomit; hanya live tail yang berubah pada setiap hipotesis.",
        "Implementasi bersih ORT berdasarkan konsep local agreement.",
        "https://github.com/ufal/whisper_streaming",
    ),
    ProviderSpec(
        "local_agreement", "streaming", "Local Agreement", "Adapted Open Source", "MIT concept",
        "Experimental", "Kata baru dikomit setelah disepakati beberapa inferensi berturut-turut.",
        "Policy eksperimental terisolasi untuk dialog panjang.",
        "https://github.com/ufal/SimulStreaming",
    ),
    ProviderSpec(
        "ortcore_fast_v2", "translation", "ORTCore Fast V2", "ORT Native", "ORT Project",
        "Stable", "Penerjemah lokal cepat yang sudah digunakan ORT.",
        "Internal provider produksi.",
    ),
    ProviderSpec(
        "ja_en_id_bridge", "translation", "Japanese → English → Indonesian", "ORT Native", "ORT Project",
        "Stable", "Jalur kompatibilitas Japanese Specialist saat ini.",
        "Menjaga English preview dan terjemahan Indonesia.",
    ),
    ProviderSpec(
        "direct_ja_id", "translation", "Direct Japanese → Indonesian", "ORT Research", "Provider-dependent",
        "Planned", "Menghindari akumulasi error dari English bridge.",
        "Belum mengganti rute produksi; disiapkan sebagai provider v9.",
        default_available=False,
    ),
    ProviderSpec(
        "external_translation_api", "translation", "External Translation API", "External Connector", "Provider-dependent",
        "Experimental", "Adapter localhost/HTTP untuk LibreTranslate, DeepLX, atau provider custom.",
        "Credential tetap berada di user_data dan tidak masuk source export.",
    ),
    ProviderSpec(
        "ort_overlay", "overlay", "ORT Overlay", "ORT Native", "ORT Project",
        "Stable", "Overlay Indonesia, source preview, latency, dan engine badge.",
        "Dipakai bersama pipeline Original dan Lab.",
    ),
)


PROVIDER_BY_ID = {item.provider_id: item for item in _PROVIDERS}
CATEGORIES = ("source", "vad", "asr", "streaming", "translation", "overlay")


def providers(category: str | None = None) -> tuple[ProviderSpec, ...]:
    if not category:
        return _PROVIDERS
    token = str(category).strip().lower()
    return tuple(item for item in _PROVIDERS if item.category == token)


def provider(provider_id: str) -> ProviderSpec:
    try:
        return PROVIDER_BY_ID[str(provider_id)]
    except KeyError as exc:
        raise ValueError(f"Provider tidak dikenal: {provider_id}") from exc


def choices(category: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in providers(category):
        ready, _ = item.availability()
        badge = "Ready" if ready else item.maturity
        result.append((f"{item.label} · {badge}", item.provider_id))
    return result


def export_registry(path: Path | None = None) -> Path:
    target = path or (plugin_root() / "open_architecture" / "provider_registry.runtime.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"schema": 1, "providers": [item.payload() for item in _PROVIDERS]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def selected_payload(provider_ids: Iterable[str]) -> list[dict]:
    return [provider(item).payload() for item in provider_ids]
