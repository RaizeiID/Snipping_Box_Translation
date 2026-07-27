from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from enum import Enum
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SETUP_PATH = APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py"


class FakeChunkType(Enum):
    STANZA = 1
    MINISBD = 2


class FakeTranslator:
    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target

    def translate(self, text: str) -> str:
        key = (self.source, self.target, str(text))
        known = {
            ("ja", "en", "これはテストです"): "This is a test",
            ("en", "id", "This is a test"): "Ini adalah tes",
        }
        return known.get(key, f"{self.target}:{text}")


class FakeLanguage:
    def __init__(self, code: str):
        self.code = code

    def get_translation(self, target):
        return FakeTranslator(self.code, target.code) if target else None


def install_fake_argos() -> types.ModuleType:
    package = types.ModuleType("argostranslate")
    package.__path__ = []
    settings = types.ModuleType("argostranslate.settings")
    settings.ChunkType = FakeChunkType
    settings.chunk_type = FakeChunkType.STANZA
    translate = types.ModuleType("argostranslate.translate")
    translate.get_installed_languages = lambda: [
        FakeLanguage("ja"), FakeLanguage("en"), FakeLanguage("id")
    ]
    package.settings = settings
    package.translate = translate
    sys.modules["argostranslate"] = package
    sys.modules["argostranslate.settings"] = settings
    sys.modules["argostranslate.translate"] = translate
    return settings


def load_setup_module():
    spec = importlib.util.spec_from_file_location("ort_v905_r3_setup", SETUP_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.path.insert(0, str(APP_ROOT))
    settings = install_fake_argos()
    sys.modules.pop("app.audio.argos_offline", None)
    argos = importlib.import_module("app.audio.argos_offline")

    info = argos.configure_argos_offline_environment()
    assert info["chunk_type"] == "MINISBD"
    assert info["device_type"] == "cpu"
    assert os.environ["ARGOS_CHUNK_TYPE"] == "MINISBD"
    assert os.environ["ARGOS_DEVICE_TYPE"] == "cpu"
    assert settings.chunk_type == FakeChunkType.MINISBD

    ja_en, ja_info = argos.get_translation_pair("ja", "en")
    en_id, id_info = argos.get_translation_pair("en", "id")
    assert ja_en.translate("これはテストです") == "This is a test"
    assert en_id.translate("This is a test") == "Ini adalah tes"
    assert ja_info.chunk_type == id_info.chunk_type == "MINISBD"

    setup = load_setup_module()
    detail = json.dumps({
        "ok": False,
        "package_version": "1.13.4+cuda12.cudnn9",
        "missing_dlls": ["cufft64_11.dll"],
    })
    assert setup._cuda_missing_dlls_from_probe(detail) == ("cufft64_11.dll",)
    assert setup.NVIDIA_CUDA12_DLL_PACKAGES["cufft64_11.dll"].startswith("nvidia-cufft-cu12")

    source = SETUP_PATH.read_text(encoding="utf-8")
    assert "ARGOS_CHUNK_TYPE'] = 'MINISBD'" in source
    assert "socket.create_connection = forbidden" in source
    assert "Paket Argos JA→EN dan EN→ID sudah tersedia; akses package index dilewati." in source
    assert "_install_nvidia_cuda12_dependencies(python, missing_cuda_dlls)" in source
    assert "direct_static_manifest_r3" in source

    from app.audio import windows_dll_resolver

    with tempfile.TemporaryDirectory(prefix="ort-v905-r3-dll-") as temp:
        dll_dir = Path(temp)
        expected = dll_dir / "cufft64_11.dll"
        expected.write_bytes(b"fake")
        found = windows_dll_resolver.locate_dlls(["cufft64_11.dll"], [dll_dir])
        assert found["cufft64_11.dll"] == str(expected)

    print(json.dumps({
        "passed": True,
        "version": "v9.0.5-R3",
        "argos_minisbd_offline_contract": "PASS",
        "argos_pair_resolution": "PASS",
        "argos_package_index_cache_first": "PASS",
        "cuda_missing_dll_mapping": "PASS",
        "windows_dll_discovery": "PASS",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
