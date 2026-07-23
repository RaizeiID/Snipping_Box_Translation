#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_info import APP_VERSION_TAG, RELEASE_NAME
import audio_translation_sidecar


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.2-R6", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Audio Native Crash Isolation Hotfix", "Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")


def test_parent_process_isolation_contract() -> None:
    source = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    assert_true('sidecar = BASE_DIR / "audio_translation_sidecar.py"' in source, "translation sidecar is not launched")
    assert_true("stdin=subprocess.PIPE" in source and "stdout=subprocess.PIPE" in source, "translation sidecar protocol is incomplete")
    assert_true("class AudioTranslator" not in source, "native translation engine still initializes inside the PyQt parent")
    assert_true("from translation_engine import get_engine" not in source, "PyQt parent still imports the native translation engine")
    assert_true("WINDOWS_ACCESS_VIOLATION = 0xC0000005" in source, "Windows native crash code is not classified")
    assert_true('env["ORT_DISABLE_CT2"] = "1"' in source, "safe Argos recovery does not disable CT2")
    assert_true('env["CT2_PACKED_GEMM"] = "0"' in source, "packed GEMM stability override is missing")
    assert_true("self._pending: Optional[dict] = None" in source, "latest-only pending slot is missing")
    assert_true("self._inflight: Optional[dict] = None" in source, "single in-flight slot is missing")
    assert_true("stale translation blocked" in source, "generation guard was removed")
    application_source = source.split("class AudioApplication", 1)[1]
    start_block = application_source.split("def start(self) -> None:", 1)[1].split("def _handle_capture_event", 1)[0]
    assert_true(start_block.index("self.translator.start()") < start_block.index("self.asr.start()"), "translator is not preloaded before ASR starts")


def test_translation_sidecar_runtime_contract() -> None:
    source = (ROOT / "audio_translation_sidecar.py").read_text(encoding="utf-8")
    assert_true("faulthandler.enable(all_threads=True)" in source, "native crash diagnostics are disabled")
    assert_true('os.environ["CT2_PACKED_GEMM"] = "0"' in source, "sidecar can re-enable unstable packed GEMM")
    assert_true('os.environ["ORT_DISABLE_CT2"] = "1"' in source, "safe sidecar does not force non-CT2 recovery")
    assert_true('state="TRANSLATOR_READY"' in source, "translation readiness event is missing")
    assert_true("translation_safe_mode=" in source, "safe-mode result telemetry is missing")


def test_safe_environment_configuration() -> None:
    keys = (
        "ORT_AUDIO_TRANSLATION_SAFE_MODE",
        "ORT_DISABLE_CT2",
        "ORT_AUDIO_TRANSLATION_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "CT2_PACKED_GEMM",
        "CT2_USE_EXPERIMENTAL_PACKED_GEMM",
    )
    old = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["ORT_AUDIO_TRANSLATION_SAFE_MODE"] = "1"
        os.environ["ORT_AUDIO_TRANSLATION_THREADS"] = "6"
        safe_mode = audio_translation_sidecar.configure_native_runtime()
        assert_true(safe_mode, "safe mode was not detected")
        assert_true(os.environ.get("ORT_DISABLE_CT2") == "1", "CT2 was not disabled in recovery")
        assert_true(os.environ.get("OMP_NUM_THREADS") == "1", "safe mode did not reduce OMP to one thread")
        assert_true(os.environ.get("CT2_PACKED_GEMM") == "0", "packed GEMM remained enabled")
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_request_protocol_and_result_metadata() -> None:
    class FakeTranslator:
        safe_mode = False

        @staticmethod
        def engine_label() -> str:
            return "ct2_fast"

        @staticmethod
        def translate(text: str) -> tuple[str, dict]:
            return "Terjemahan uji", {"engine": "ct2_fast", "cache": "MISS"}

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        audio_translation_sidecar.process_request(FakeTranslator(), {
            "type": "translate",
            "generation_id": 7,
            "text": "Test sentence",
            "asr_ms": 125,
            "profile": "normal",
        })
    events = []
    for line in output.getvalue().splitlines():
        assert_true(line.startswith(audio_translation_sidecar.EVENT_PREFIX), f"unexpected protocol output: {line}")
        events.append(json.loads(line[len(audio_translation_sidecar.EVENT_PREFIX):]))
    assert_true([event.get("type") for event in events] == ["state", "translation"], f"unexpected event sequence: {events}")
    result = events[-1]
    assert_true(result.get("generation_id") == 7, "generation identity was lost")
    assert_true(result.get("translation") == "Terjemahan uji", "translation payload was lost")
    assert_true(result.get("total_ms", 0) >= 125, "ASR latency was not included")
    assert_true(result.get("translation_safe_mode") is False, "primary result was marked as recovery")


def test_translation_engine_recovery_guard() -> None:
    source = (ROOT / "translation_engine.py").read_text(encoding="utf-8")
    assert_true('ct2_disabled = os.environ.get("ORT_DISABLE_CT2", "0") == "1"' in source, "translation engine ignores the recovery guard")
    assert_true("not ct2_disabled and (" in source, "CT2 can initialize despite the recovery guard")
    assert_true("CT2 disabled for isolated Audio recovery" in source, "recovery backend is not observable")


def _install_pyqt_stub() -> None:
    if "PyQt5" in sys.modules:
        return

    class Signal:
        def __init__(self, *_args, **_kwargs):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

        def emit(self, *args, **kwargs):
            for callback in list(self.callbacks):
                callback(*args, **kwargs)

    class Dummy:
        DemiBold = 1

        def __init__(self, *_args, **_kwargs):
            pass

    class Qt:
        FramelessWindowHint = 1
        WindowStaysOnTopHint = 2
        Tool = 4
        WA_TranslucentBackground = 8
        AlignRight = 16
        AlignVCenter = 32
        AlignLeft = 64
        LeftButton = 128

    package = types.ModuleType("PyQt5")
    core = types.ModuleType("PyQt5.QtCore")
    gui = types.ModuleType("PyQt5.QtGui")
    widgets = types.ModuleType("PyQt5.QtWidgets")
    core.QObject = Dummy
    core.QPoint = Dummy
    core.Qt = Qt
    core.QTimer = Dummy
    core.pyqtSignal = Signal
    gui.QFont = Dummy
    widgets.QApplication = Dummy
    widgets.QFrame = Dummy
    widgets.QHBoxLayout = Dummy
    widgets.QLabel = Dummy
    widgets.QVBoxLayout = Dummy
    widgets.QWidget = Dummy
    sys.modules["PyQt5"] = package
    sys.modules["PyQt5.QtCore"] = core
    sys.modules["PyQt5.QtGui"] = gui
    sys.modules["PyQt5.QtWidgets"] = widgets


def test_process_crash_recovery_replays_latest_transcript() -> None:
    _install_pyqt_stub()
    audio_main = importlib.import_module("audio_main")
    assert_true(audio_main.TranslationCoordinator._exit_label(-1073741819).startswith("0xC0000005"), "signed Windows access violation is not normalized")
    fake_sidecar = """\
import json
import os
import sys
import time

prefix = "ORT_AUDIO_TRANSLATION_EVENT "
safe = os.environ.get("ORT_AUDIO_TRANSLATION_SAFE_MODE") == "1"
if not safe:
    print(prefix + json.dumps({"type": "state", "state": "TRANSLATOR_LOADING", "safe_mode": False}), flush=True)
    os._exit(23)
print(prefix + json.dumps({"type": "state", "state": "TRANSLATOR_READY", "safe_mode": True, "engine": "argos_recovery"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if request.get("type") == "shutdown":
        break
    if request.get("type") == "translate":
        response = dict(request)
        response.update({
            "type": "translation",
            "translation": "Terjemahan pulih",
            "translation_ms": 9,
            "total_ms": int(request.get("asr_ms", 0)) + 9,
            "translation_engine": "argos_recovery",
            "cache": "MISS",
            "translation_safe_mode": True,
        })
        print(prefix + json.dumps(response), flush=True)
"""
    original_base = audio_main.BASE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        (temp_root / "audio_translation_sidecar.py").write_text(fake_sidecar, encoding="utf-8")
        audio_main.BASE_DIR = temp_root
        coordinator = audio_main.TranslationCoordinator()
        results = []
        events = []
        coordinator.translation_ready.connect(results.append)
        coordinator.runtime_event.connect(events.append)
        try:
            coordinator.start()
            generation = coordinator.submit({"text": "This is a test", "asr_ms": 100, "profile": "normal"})
            deadline = time.monotonic() + 5.0
            while not results and time.monotonic() < deadline:
                time.sleep(0.02)
            assert_true(results, f"translation was not recovered; events={events}")
            assert_true(results[-1].get("generation_id") == generation, "replayed result lost generation identity")
            assert_true(results[-1].get("translation") == "Terjemahan pulih", "safe process did not replay the transcript")
            assert_true(results[-1].get("translation_safe_mode") is True, "recovered result is not marked safe")
            assert_true(coordinator.restart_count == 1, f"unexpected recovery count: {coordinator.restart_count}")
            assert_true(any(event.get("type") == "TRANSLATION_PROCESS_EXIT" and event.get("restart") for event in events), "process exit did not trigger recovery telemetry")
        finally:
            coordinator.stop()
            audio_main.BASE_DIR = original_base


def main() -> None:
    test_release_identity()
    test_parent_process_isolation_contract()
    test_translation_sidecar_runtime_contract()
    test_safe_environment_configuration()
    test_request_protocol_and_result_metadata()
    test_translation_engine_recovery_guard()
    test_process_crash_recovery_replays_latest_transcript()
    print(f"{APP_VERSION_TAG} Audio native crash isolation regression PASS")


if __name__ == "__main__":
    main()
