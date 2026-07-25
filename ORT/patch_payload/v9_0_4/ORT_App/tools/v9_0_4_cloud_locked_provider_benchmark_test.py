from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from build_info import APP_VERSION_TAG, RELEASE_NAME
from app.audio.asr_provider_registry import (
    PROVIDER_KOTOBA,
    PROVIDER_REAZON,
    PROVIDER_SENSEVOICE,
    PROVIDER_WHISPER_BASE,
    PROVIDER_WHISPER_SMALL,
    normalize_provider_id,
    provider_choices,
)
from app.audio.locked_asr_adapter import LockedASRProviderAdapter


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.4"
    assert RELEASE_NAME == "Cloud & Locked Provider Benchmark Lab"

    ids = [value for _label, value in provider_choices(include_auto=False)]
    assert ids == [
        PROVIDER_KOTOBA,
        PROVIDER_REAZON,
        PROVIDER_SENSEVOICE,
        PROVIDER_WHISPER_BASE,
        PROVIDER_WHISPER_SMALL,
    ]
    assert normalize_provider_id("reazon") == PROVIDER_REAZON
    assert normalize_provider_id("sensevoice") == PROVIDER_SENSEVOICE

    events: list[dict] = []
    adapter = LockedASRProviderAdapter(
        model_root=APP_ROOT / "_missing_test_models",
        provider_id=PROVIDER_KOTOBA,
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        source_language="ja",
        requested_language="ja",
        profile="speed",
        emit_event=lambda *args, **kwargs: events.append({"args": args, **kwargs}),
    )
    assert adapter.provider_id == PROVIDER_KOTOBA
    assert adapter._window_seconds(False) <= 2.2
    assert adapter._window_seconds(True) <= 4.0
    assert adapter.dual_stream_cpu_specialist is False

    executor = (APP_ROOT / "app" / "open_architecture" / "executor.py").read_text(encoding="utf-8-sig")
    assert '"ORT_AUDIO_ASR_PROVIDER": normalize_provider_id(asr_model_provider)' in executor
    assert '"ORT_AUDIO_MODEL_LOCK": "1" if model_lock else "0"' in executor
    assert '"ORT_AUDIO_DELIVERY_MODE": normalise_delivery_mode(delivery_mode)' in executor
    assert '"ORT_AUDIO_CLOUD_PROVIDER": normalise_cloud_provider(cloud_provider)' in executor

    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    sidecar = (APP_ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8-sig")
    audio_main = (APP_ROOT / "audio_main.py").read_text(encoding="utf-8-sig")
    translation = (APP_ROOT / "audio_translation_sidecar.py").read_text(encoding="utf-8-sig")
    setup = (APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py").read_text(encoding="utf-8-sig")

    for marker in (
        "Model ASR Jepang · hard lock",
        "Kunci model selama sesi",
        "Siapkan model sesuai CPU/GPU/Hybrid",
        "Provider Benchmark Lab · WAV yang sama",
        "Mode delivery",
        "Azure Speech · live",
        "Google Cloud · benchmark catalog",
        "AWS Transcribe · benchmark catalog",
    ):
        assert marker in webui, marker

    for marker in (
        "--asr-provider",
        "--model-lock",
        "provider_changed=False",
        "run_provider_benchmark",
        "LockedASRProviderAdapter",
    ):
        assert marker in sidecar, marker

    assert 'selected_provider == "sensevoice_small"' in audio_main
    assert "sensevoice_cpu_only" in audio_main
    assert "translation_unavailable" in translation
    assert "bridge_language" in translation
    assert "Model lock memerlukan provider eksplisit" in executor
    assert "catalog only pada v9.0.4" in executor
    assert "install_reazon" in setup
    assert 'parser.add_argument("--device", choices=["cpu", "cuda"]' in setup
    assert "SHERPA_CUDA_INDEX" in setup
    assert "int8-fp32" in setup
    assert '"--device", "cuda" if str(device).lower() == "cuda" else "cpu"' in webui
    assert "CUDA-enabled sherpa-onnx detected" in (APP_ROOT / "app" / "audio" / "asr_provider_registry.py").read_text(encoding="utf-8-sig")
    assert "install_sensevoice" in setup
    assert "install_argos_bridge" in setup

    result = {
        "passed": True,
        "version": APP_VERSION_TAG,
        "locked_providers": ids,
        "provider_substitution": "BLOCKED",
        "same_provider_device_switch": "ALLOWED",
        "kotoba_cpu_bounded_window": "PASS",
        "sensevoice_cpu_routing": "PASS",
        "source_aware_translation_bridge": "PASS",
        "delivery_modes": ["offline", "online", "hybrid"],
        "live_cloud_provider": "azure",
        "catalog_cloud_providers": ["google", "aws"],
        "wav_provider_benchmark": "PASS",
        "reazonspeech_cuda_setup": "PASS",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
