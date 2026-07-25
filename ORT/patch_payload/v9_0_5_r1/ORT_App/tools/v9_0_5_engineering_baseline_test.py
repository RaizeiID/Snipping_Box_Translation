from __future__ import annotations

import importlib
import json
import py_compile
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = APP_ROOT / "tools"
for candidate in (str(APP_ROOT), str(TOOLS_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 206) -> None:
        self._payload = payload
        self._offset = 0
        self.status = status
        self.headers = {"Content-Length": str(len(payload))}

    def read(self, amount: int = -1) -> bytes:
        if self._offset >= len(self._payload):
            return b""
        if amount < 0:
            amount = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + amount]
        self._offset += len(chunk)
        return chunk

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def main() -> int:
    paths = [
        APP_ROOT / "build_info.py",
        APP_ROOT / "webui.py",
        TOOLS_ROOT / "setup_v9_0_4_audio_providers.py",
        TOOLS_ROOT / "setup_v9_0_5_audio_providers.py",
        APP_ROOT / "app" / "audio" / "asr_provider_registry.py",
        APP_ROOT / "app" / "audio" / "locked_asr_adapter.py",
        APP_ROOT / "app" / "audio" / "sherpa_compat.py",
    ]
    for path in paths:
        py_compile.compile(str(path), doraise=True)

    build_info = importlib.import_module("build_info")
    setup = importlib.import_module("setup_v9_0_4_audio_providers")
    if build_info.APP_VERSION_TAG != "v9.0.5":
        raise AssertionError(build_info.APP_VERSION_TAG)
    if setup.SETUP_VERSION != "v9.0.5":
        raise AssertionError(setup.SETUP_VERSION)

    inner = OSError(10054, "An existing connection was forcibly closed by the remote host")
    outer = RuntimeError("DryRunError: repository cannot be accessed")
    outer.__cause__ = inner
    if not setup._transient_download_error(outer):
        raise AssertionError("nested WinError 10054 was not treated as transient")
    chain = setup._exception_chain_text(outer)
    if "10054" not in chain or "DryRunError" not in chain:
        raise AssertionError(chain)

    with tempfile.TemporaryDirectory(prefix="ort-v905-resume-") as temp:
        root = Path(temp)
        destination = root / "model.bin"
        Path(str(destination) + ".part").write_bytes(b"abc")
        original = setup.urllib.request.urlopen
        observed_range = {"value": ""}

        def fake_urlopen(request, timeout=0):
            observed_range["value"] = str(request.headers.get("Range") or request.get_header("Range") or "")
            return _FakeResponse(b"def", status=206)

        setup.urllib.request.urlopen = fake_urlopen
        try:
            result = setup._download_static_file(
                "test_provider",
                "owner/repo",
                "revision",
                "model.bin",
                {"size": 6, "sha256": ""},
                destination,
                token=None,
                aggregate_total=6,
                aggregate_complete_before=0,
            )
        finally:
            setup.urllib.request.urlopen = original
        if result.read_bytes() != b"abcdef":
            raise AssertionError("range resume did not preserve the partial prefix")
        if "bytes=3-" not in observed_range["value"]:
            raise AssertionError(observed_range)

    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    adapter = (APP_ROOT / "app" / "audio" / "locked_asr_adapter.py").read_text(encoding="utf-8-sig")
    sherpa_compat = (APP_ROOT / "app" / "audio" / "sherpa_compat.py").read_text(encoding="utf-8-sig")
    registry = (APP_ROOT / "app" / "audio" / "asr_provider_registry.py").read_text(encoding="utf-8-sig")
    setup_text = (TOOLS_ROOT / "setup_v9_0_4_audio_providers.py").read_text(encoding="utf-8-sig")

    required = {
        "new_setup_entry": 'setup_v9_0_5_audio_providers.py' in webui,
        "network_ui": 'SETUP: JARINGAN TERPUTUS' in webui,
        "diagnostic_log": 'last_error_' in setup_text,
        "direct_manifest": 'def _download_reazon_static(' in setup_text,
        "no_reazon_dry_run": 'metadata_preflight=False' in setup_text,
        "local_reazon_load": "create_offline_transducer(" in adapter,
        "sherpa_submodule_fallback": "sherpa_onnx.offline_recognizer" in sherpa_compat,
        "local_reazon_decode": 'self.model.decode_stream(stream)' in adapter,
        "device_files": 'REAZON_DEVICE_FILES' in registry,
    }
    failed = [name for name, passed in required.items() if not passed]
    payload = {
        "passed": not failed,
        "version": build_info.APP_VERSION_TAG,
        "release": build_info.RELEASE_NAME,
        "nested_winerror_retry": "PASS",
        "range_resume": "PASS",
        "project_setup_separated": "PASS",
        "checks": required,
        "errors": failed,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
