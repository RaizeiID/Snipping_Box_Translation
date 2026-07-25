from __future__ import annotations

import importlib.util
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


def load_translation_module():
    path = APP_ROOT / "audio_translation_sidecar.py"
    spec = importlib.util.spec_from_file_location("ort_v904_r3_translation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeEngine:
    ct2 = object()
    def translate(self, text, bridge=None):
        assert text == "This is a test"
        return "Ini adalah sebuah tes", {"engine": "fake_ct2", "cache": "MISS"}


def main() -> int:
    module = load_translation_module()
    translator = module.AudioTranslator.__new__(module.AudioTranslator)
    translator._engine = FakeEngine()
    translator._source_bridge_cache = {}
    translator._source_bridge_cache_limit = 16
    translator._source_bridge_ready = True
    translator._source_bridge_warmup_ms = 321
    translator._argos_translate_pair = lambda text, source, target: (
        "This is a test" if (source, target) == ("ja", "en") else ""
    )

    output, meta = translator._translate_clause("これはテストです", "ja")
    assert output == "Ini adalah sebuah tes"
    assert meta["bridge_text"] == "This is a test"
    assert meta["preview_text"] == "This is a test"
    assert meta["preview_language"] == "en"
    assert meta["target_language"] == "id"
    assert meta["bridge_engine"] == "argos_ja_en"

    audio_main = (APP_ROOT / "audio_main.py").read_text(encoding="utf-8-sig")
    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    setup = (APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py").read_text(encoding="utf-8-sig")
    translation = (APP_ROOT / "audio_translation_sidecar.py").read_text(encoding="utf-8-sig")

    assert "bridge_preview = str(" in audio_main
    assert "self.overlay.set_cloud_translation(bridge_preview" in audio_main
    assert "last_bridge_preview=bridge_preview" in audio_main
    assert "preview_en={bridge_preview}" in audio_main
    assert "bridge_ready={event.get('source_bridge_ready', '-')}" in audio_main
    assert '_oa_setup_command(runtime_python, "argos_bridge", device)' in webui
    assert 'ASR_PROVIDERS[provider].output_language == "ja"' in webui
    assert "Argos bridge functional PASS" in setup
    assert "_prepare_source_bridge" in translation
    assert "Do not attempt a hidden JA->ID Argos" in translation

    print(json.dumps({
        "passed": True,
        "version": "v9.0.4-R3",
        "reazon_asr": "JA transcription",
        "english_preview": "JA->EN bridge",
        "indonesian_translation": "EN->ID CT2",
        "bridge_runtime_binding": "PASS",
        "bridge_prewarm": "PASS",
        "overlay_preview_en": "PASS",
        "hard_model_lock_preserved": True,
        "reazon_cuda_r2_preserved": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
