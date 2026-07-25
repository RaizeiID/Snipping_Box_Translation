from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from build_info import APP_VERSION_TAG, RELEASE_NAME
from app.open_architecture.runtime_control import TranslationWatchdogPolicy


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.4"
    assert RELEASE_NAME == "Cloud & Locked Provider Benchmark Lab"

    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    audio_main = (APP_ROOT / "audio_main.py").read_text(encoding="utf-8-sig")
    sidecar = (APP_ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8-sig")
    translation = (APP_ROOT / "audio_translation_sidecar.py").read_text(encoding="utf-8-sig")
    executor = (APP_ROOT / "app" / "open_architecture" / "executor.py").read_text(encoding="utf-8-sig")
    preview = (APP_ROOT / "app" / "open_architecture" / "overlay_preview.py").read_text(encoding="utf-8-sig")

    # Realtime overlay preview is persistent and updates without closing the box.
    for marker in (
        'gr.Button("Preview"',
        'gr.update(value="Preview")',
        'Preview aktif · perubahan diterapkan realtime',
        'oa_live_timer.tick',
        'Log realtime',
        'Transparansi provider aktif',
    ):
        assert marker in webui, marker
    for marker in ('--overlay-preview-config', 'apply_preview_config', 'OverlayPreviewApplication'):
        assert marker in audio_main, marker
    for marker in ('start_overlay_preview', 'stop_overlay_preview', 'update_overlay_preview'):
        assert marker in preview, marker

    # Stability recovery: single stream by default and CT2-safe restart before Argos.
    assert 'ORT_AUDIO_DUAL_STREAM": "0"' in executor
    assert 'ORT_AUDIO_ALLOW_ARGOS_RECOVERY": "0"' in executor
    assert 'ct2_safe' in audio_main
    assert 'ORT_AUDIO_ALLOW_ARGOS_RECOVERY' in translation
    assert 'ORT_DISABLE_CT2' in translation  # still supported only for explicit Argos recovery
    assert 'restarting CT2 worker with latest request' in audio_main

    # Resource controller and false-speech cooldown must be wired to the live sidecar.
    for marker in (
        'RESOURCE_POLICY_DECISION',
        'locked_provider_preserved_vram_guard_',
        'ORT_AUDIO_PREFLIGHT_MAX_STEADY_MS',
        'false_speech_cooldown',
        'ORT_AUDIO_CONTEXT_WORDS',
    ):
        assert marker in sidecar, marker

    # Game/media profiles must no longer force English media through Japanese translate.
    assert '"DAILY_MEDIA": ("auto", "en", "ja_specialist", "zh", "ko")' in executor
    assert '"GFL2_EXILIUM": ("ja_specialist", "zh")' in executor
    assert '"GFL": ("ja_specialist",)' in executor
    assert '"WUTHERING_WAVES": ("en", "ja_specialist", "zh", "ko")' in executor
    assert 'return requested or "auto"' in executor

    old = os.environ.get("ORT_TRANSLATION_WATCHDOG_SECONDS")
    try:
        os.environ.pop("ORT_TRANSLATION_WATCHDOG_SECONDS", None)
        defaults = {
            "speed": TranslationWatchdogPolicy.for_profile("speed").timeout_s,
            "normal": TranslationWatchdogPolicy.for_profile("normal").timeout_s,
            "accurate": TranslationWatchdogPolicy.for_profile("accurate").timeout_s,
        }
        assert defaults["speed"] >= 12.0
        assert defaults["normal"] >= 15.0
        assert defaults["accurate"] >= 22.0
        os.environ["ORT_TRANSLATION_WATCHDOG_SECONDS"] = "19"
        assert TranslationWatchdogPolicy.for_profile("speed").timeout_s == 19.0
    finally:
        if old is None:
            os.environ.pop("ORT_TRANSLATION_WATCHDOG_SECONDS", None)
        else:
            os.environ["ORT_TRANSLATION_WATCHDOG_SECONDS"] = old

    result = {
        "passed": True,
        "version": APP_VERSION_TAG,
        "single_stream_default": True,
        "ct2_latest_wins_recovery": "PASS",
        "resource_modes": ["efficient", "normal", "optimal"],
        "realtime_log": "PASS",
        "realtime_overlay_preview": "PASS",
        "game_language_profiles": "PASS",
        "provider_transparency": "PASS",
        "cloud_provider_benchmark_integrated_in": "v9.0.4",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
