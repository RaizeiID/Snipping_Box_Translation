#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.model_store import canonical_model_dir, inspect_local_model
from app.audio.profiles import get_audio_profile
from build_info import APP_VERSION_TAG, RELEASE_NAME
import audio_asr_sidecar
from audio_runtime_backend import audio_model_ready


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _write_complete_model(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{" + (" " * 120) + "}", encoding="utf-8")
    (model_dir / "vocabulary.txt").write_text("token\n", encoding="utf-8")
    with (model_dir / "model.bin").open("wb") as handle:
        handle.truncate(1_000_000)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.2-R4", "v8.9.2-R5", "v8.9.2-R6", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Audio Model Recovery Hotfix", "Audio Model Compatibility Hotfix", "Audio Native Crash Isolation Hotfix", "Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")


def test_partial_snapshot_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        model_root = Path(tmp)
        model_dir = canonical_model_dir(model_root, "base")
        model_dir.mkdir(parents=True)
        with (model_dir / "model.bin").open("wb") as handle:
            handle.truncate(1_000_000)
        partial = inspect_local_model(model_root, "base")
        assert_true(not partial.ready, "model.bin alone was incorrectly accepted")
        for expected in ("config.json", "tokenizer.json", "vocabulary.*"):
            assert_true(expected in partial.missing_files, f"missing file was not reported: {expected}")
        assert_true("preprocessor_config.json" in partial.optional_missing_files, "optional preprocessor status was not reported")
        _write_complete_model(model_dir)
        complete = inspect_local_model(model_root, "base")
        assert_true(complete.ready, f"complete local model rejected: {complete}")


def test_stale_prepared_marker_cannot_bypass_backend() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)
        audio_root = base_dir / "_runtime" / "audio_cpu"
        model_name = get_audio_profile("normal").model_size
        model_dir = canonical_model_dir(audio_root / "models", model_name)
        model_dir.mkdir(parents=True)
        with (model_dir / "model.bin").open("wb") as handle:
            handle.truncate(1_000_000)
        (audio_root / "prepared_base.json").write_text('{"files_verified": false}', encoding="utf-8")
        assert_true(not audio_model_ready("normal", base_dir), "stale marker bypassed incomplete-model validation")
        _write_complete_model(model_dir)
        assert_true(audio_model_ready("normal", base_dir), "complete backend model was not accepted")


def test_retry_then_resume_to_canonical_folder() -> None:
    profile = get_audio_profile("normal")
    calls = []
    package = types.ModuleType("faster_whisper")
    package.__path__ = []
    utils = types.ModuleType("faster_whisper.utils")
    hub = types.ModuleType("huggingface_hub")

    def fake_download_model(size, output_dir=None, cache_dir=None):
        calls.append((size, output_dir, cache_dir))
        if len(calls) == 1:
            raise ConnectionError("simulated interrupted connection")
        target = Path(str(output_dir))
        _write_complete_model(target)
        return str(target)

    utils.download_model = fake_download_model
    def fake_snapshot_download(repository, revision=None, local_dir=None, cache_dir=None, allow_patterns=None, max_workers=None):
        calls.append((repository, local_dir, cache_dir, revision, max_workers))
        target = Path(str(local_dir))
        _write_complete_model(target)
        return str(target)

    hub.snapshot_download = fake_snapshot_download
    old_package = sys.modules.get("faster_whisper")
    old_utils = sys.modules.get("faster_whisper.utils")
    old_hub = sys.modules.get("huggingface_hub")
    old_sleep = audio_asr_sidecar.time.sleep
    sys.modules["faster_whisper"] = package
    sys.modules["faster_whisper.utils"] = utils
    sys.modules["huggingface_hub"] = hub
    audio_asr_sidecar.time.sleep = lambda _seconds: None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            model_root = Path(tmp)
            prepared = audio_asr_sidecar._prepare_whisper(profile, model_root, retry_count=3)
            assert_true(prepared == canonical_model_dir(model_root, profile.model_size), "download did not use the canonical local folder")
            assert_true(len(calls) == 2, f"interrupted download was not retried once: {len(calls)}")
            assert_true(calls[-1][2] == str(model_root), "existing cache root was not offered for resume/reuse")
            assert_true(calls[-1][-1] == 1, "recovery retry did not switch to a single-worker transfer")
            assert_true(inspect_local_model(model_root, profile.model_size).ready, "resumed model did not pass validation")
    finally:
        audio_asr_sidecar.time.sleep = old_sleep
        if old_package is None:
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = old_package
        if old_utils is None:
            sys.modules.pop("faster_whisper.utils", None)
        else:
            sys.modules["faster_whisper.utils"] = old_utils
        if old_hub is None:
            sys.modules.pop("huggingface_hub", None)
        else:
            sys.modules["huggingface_hub"] = old_hub


def test_runtime_load_is_offline_only() -> None:
    profile = get_audio_profile("normal")
    captured = {}
    package = types.ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, model_path, **kwargs):
            captured["model_path"] = model_path
            captured.update(kwargs)

    package.WhisperModel = FakeWhisperModel
    old_package = sys.modules.get("faster_whisper")
    sys.modules["faster_whisper"] = package
    try:
        with tempfile.TemporaryDirectory() as tmp:
            model_root = Path(tmp)
            model_dir = canonical_model_dir(model_root, profile.model_size)
            _write_complete_model(model_dir)
            audio_asr_sidecar._load_whisper(profile, model_root)
            assert_true(Path(captured["model_path"]) == model_dir, "runtime did not load the validated local folder")
            assert_true(captured.get("local_files_only") is True, "runtime is still allowed to contact the Hub")
            assert_true(captured.get("device") == "cpu" and captured.get("compute_type") == "int8", "CPU INT8 contract changed")
    finally:
        if old_package is None:
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = old_package


def test_backend_and_ui_contract() -> None:
    backend = (ROOT / "audio_runtime_backend.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    assert_true("marker.exists()" not in backend, "stale prepared marker can still bypass validation")
    assert_true("dependencies=already_ready" in backend, "repeat setup still reinstalls healthy dependencies")
    assert_true('"--retry-count"' in backend, "model setup does not request retries")
    assert_true("_SETUP_LOCK.acquire(blocking=False)" in backend, "concurrent setup clicks are not guarded")
    sidecar = (ROOT / "audio_asr_sidecar.py").read_text(encoding="utf-8")
    assert_true("max_workers=1" in sidecar, "recovery retry still uses concurrent model transfers")
    assert_true("audio_model_status" in launcher, "launcher cannot explain incomplete model files")
    assert_true("Unduhan model belum lengkap" in webui, "UI cannot distinguish dependencies from model readiness")


def main() -> None:
    test_release_identity()
    test_partial_snapshot_is_rejected()
    test_stale_prepared_marker_cannot_bypass_backend()
    test_retry_then_resume_to_canonical_folder()
    test_runtime_load_is_offline_only()
    test_backend_and_ui_contract()
    print(f"{APP_VERSION_TAG} Audio model recovery regression PASS")


if __name__ == "__main__":
    main()
