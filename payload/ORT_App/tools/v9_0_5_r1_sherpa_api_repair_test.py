from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _test_submodule_alias() -> dict[str, str]:
    saved = {
        name: sys.modules.get(name)
        for name in ("sherpa_onnx", "sherpa_onnx.offline_recognizer")
    }

    class FakeRecognizer:
        @classmethod
        def from_transducer(cls, **_kwargs):
            return cls()

        @classmethod
        def from_sense_voice(cls, **_kwargs):
            return cls()

    package = types.ModuleType("sherpa_onnx")
    package.__path__ = []
    package.__file__ = "C:/fake/sherpa_onnx/__init__.py"
    submodule = types.ModuleType("sherpa_onnx.offline_recognizer")
    submodule.OfflineRecognizer = FakeRecognizer
    sys.modules["sherpa_onnx"] = package
    sys.modules["sherpa_onnx.offline_recognizer"] = submodule

    try:
        compat = importlib.import_module("app.audio.sherpa_compat")
        recognizer, info = compat.resolve_offline_recognizer()
        if recognizer is not FakeRecognizer:
            raise AssertionError("submodule recognizer was not selected")
        if getattr(package, "OfflineRecognizer", None) is not FakeRecognizer:
            raise AssertionError("top-level compatibility alias was not installed")
        if info.recognizer_source != "sherpa_onnx.offline_recognizer.OfflineRecognizer":
            raise AssertionError(info.recognizer_source)
        return info.as_dict()
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _test_top_level_api() -> dict[str, str]:
    saved = {
        name: sys.modules.get(name)
        for name in ("sherpa_onnx", "sherpa_onnx.offline_recognizer")
    }

    class FakeRecognizer:
        @classmethod
        def from_transducer(cls, **_kwargs):
            return cls()

    package = types.ModuleType("sherpa_onnx")
    package.__file__ = "C:/fake/sherpa_onnx/__init__.py"
    package.OfflineRecognizer = FakeRecognizer
    sys.modules["sherpa_onnx"] = package
    sys.modules.pop("sherpa_onnx.offline_recognizer", None)

    try:
        compat = importlib.import_module("app.audio.sherpa_compat")
        recognizer, info = compat.resolve_offline_recognizer()
        if recognizer is not FakeRecognizer:
            raise AssertionError("top-level recognizer was not selected")
        if info.recognizer_source != "sherpa_onnx.OfflineRecognizer":
            raise AssertionError(info.recognizer_source)
        return info.as_dict()
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def main() -> int:
    setup_text = (APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py").read_text(
        encoding="utf-8-sig"
    )
    adapter_text = (APP_ROOT / "app" / "audio" / "locked_asr_adapter.py").read_text(
        encoding="utf-8-sig"
    )
    webui_text = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")

    checks = {
        "runtime_probe_checks_api": "sherpa_onnx.offline_recognizer" in setup_text,
        "runtime_probe_requires_from_transducer": 'getattr(recognizer, "from_transducer", None)' in setup_text,
        "pinned_cpu_runtime": 'sherpa-onnx=={SHERPA_ONNX_VERSION}' in setup_text,
        "warmup_uses_compat": "create_offline_transducer" in setup_text,
        "adapter_uses_compat": "from .sherpa_compat import" in adapter_text,
        "webui_uses_v905_entry": "setup_v9_0_5_audio_providers.py" in webui_text,
        "no_legacy_reazon_warmup": "from reazonspeech.k2.asr import load_model" not in setup_text,
    }
    failed = [name for name, value in checks.items() if not value]
    payload = {
        "passed": not failed,
        "patch": "v9.0.5-r1-sherpa-api-repair",
        "submodule_alias": _test_submodule_alias(),
        "top_level_api": _test_top_level_api(),
        "checks": checks,
        "errors": failed,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
