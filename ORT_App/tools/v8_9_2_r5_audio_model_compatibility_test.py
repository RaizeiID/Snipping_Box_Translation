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


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _write_official_ct2_layout(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{" + (" " * 120) + "}", encoding="utf-8")
    (model_dir / "vocabulary.txt").write_text("token\n", encoding="utf-8")
    with (model_dir / "model.bin").open("wb") as handle:
        handle.truncate(1_000_000)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.2-R5", "v8.9.2-R6", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Audio Model Compatibility Hotfix", "Audio Native Crash Isolation Hotfix", "Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")


def test_official_profile_layouts_are_ready_without_preprocessor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        model_root = Path(tmp)
        for model_size in ("tiny", "base", "small"):
            model_dir = canonical_model_dir(model_root, model_size)
            _write_official_ct2_layout(model_dir)
            inspection = inspect_local_model(model_root, model_size)
            assert_true(inspection.ready, f"official {model_size} layout was rejected: {inspection}")
            assert_true(not inspection.missing_files, f"core file was reported missing for {model_size}: {inspection.missing_files}")
            assert_true("preprocessor_config.json" in inspection.optional_missing_files, f"optional preprocessor status was lost for {model_size}")


def test_core_files_are_still_mandatory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        model_root = Path(tmp)
        model_dir = canonical_model_dir(model_root, "tiny")
        _write_official_ct2_layout(model_dir)
        (model_dir / "tokenizer.json").unlink()
        inspection = inspect_local_model(model_root, "tiny")
        assert_true(not inspection.ready, "model without tokenizer.json was accepted")
        assert_true("tokenizer.json" in inspection.missing_files, "missing tokenizer was not reported")


def test_cached_profiles_skip_network_and_load_offline() -> None:
    captured = []
    package = types.ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, model_path, **kwargs):
            captured.append({"model_path": model_path, **kwargs})

    package.WhisperModel = FakeWhisperModel
    old_package = sys.modules.get("faster_whisper")
    old_download = audio_asr_sidecar._download_whisper_once
    sys.modules["faster_whisper"] = package

    def fail_download(*_args, **_kwargs):
        raise AssertionError("network download was attempted for a complete official snapshot")

    audio_asr_sidecar._download_whisper_once = fail_download
    try:
        with tempfile.TemporaryDirectory() as tmp:
            model_root = Path(tmp)
            for profile_key in ("speed", "normal", "accurate"):
                profile = get_audio_profile(profile_key)
                model_dir = canonical_model_dir(model_root, profile.model_size)
                _write_official_ct2_layout(model_dir)
                prepared = audio_asr_sidecar._prepare_whisper(profile, model_root, retry_count=3)
                assert_true(prepared == model_dir, f"cached {profile.model_size} path changed")
                audio_asr_sidecar._load_whisper(profile, model_root)
                loaded = captured[-1]
                assert_true(Path(loaded["model_path"]) == model_dir, f"loader did not use cached {profile.model_size}")
                assert_true(loaded.get("local_files_only") is True, f"{profile.model_size} loader can still contact the Hub")
                assert_true(loaded.get("device") == "cpu", f"{profile.model_size} CPU loading contract changed")
                assert_true(loaded.get("compute_type") == "int8", f"{profile.model_size} INT8 loading contract changed")
                assert_true(loaded.get("cpu_threads") == profile.cpu_threads, f"{profile.model_size} thread budget changed")
    finally:
        audio_asr_sidecar._download_whisper_once = old_download
        if old_package is None:
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = old_package


def test_validator_contract() -> None:
    source = (ROOT / "app" / "audio" / "model_store.py").read_text(encoding="utf-8")
    assert_true("REQUIRED_MODEL_FILE_MIN_BYTES" in source, "required model file contract is missing")
    assert_true("OPTIONAL_MODEL_FILE_MIN_BYTES" in source, "optional model file contract is missing")
    required_block = source.split("REQUIRED_MODEL_FILE_MIN_BYTES", 1)[1].split("OPTIONAL_MODEL_FILE_MIN_BYTES", 1)[0]
    optional_block = source.split("OPTIONAL_MODEL_FILE_MIN_BYTES", 1)[1].split("@dataclass", 1)[0]
    assert_true("preprocessor_config.json" not in required_block, "preprocessor config is still mandatory")
    assert_true("preprocessor_config.json" in optional_block, "preprocessor config is not tracked as optional")


def main() -> None:
    test_release_identity()
    test_official_profile_layouts_are_ready_without_preprocessor()
    test_core_files_are_still_mandatory()
    test_cached_profiles_skip_network_and_load_offline()
    test_validator_contract()
    print(f"{APP_VERSION_TAG} Audio model compatibility regression PASS")


if __name__ == "__main__":
    main()
