#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audio.profiles import get_audio_profile
from app.audio.streaming import LiveAudioSegmenter, TranscriptDeduplicator, pcm16_to_mono_float, resample_linear
from audio_runtime_backend import EVENT_PREFIX, parse_sidecar_events
from build_info import APP_VERSION_TAG, RELEASE_NAME


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG in {"v8.9.2-R3", "v8.9.2-R4", "v8.9.2-R5", "v8.9.2-R6", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6"}, f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Audio CPU First-Test", "Audio Model Recovery Hotfix", "Audio Model Compatibility Hotfix", "Audio Native Crash Isolation Hotfix", "Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")
    for path in (ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt", ROOT.parents[1] / "VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_profile_contract() -> None:
    speed = get_audio_profile("speed")
    normal = get_audio_profile("normal")
    accurate = get_audio_profile("accurate")
    assert_true((speed.model_size, normal.model_size, accurate.model_size) == ("base", "small", "small"), "CPU ASR model ladder changed")
    assert_true((speed.gpu_model_size, normal.gpu_model_size, accurate.gpu_model_size) == ("small", "small", "medium"), "GPU ASR model ladder changed")
    assert_true(speed.cpu_threads < normal.cpu_threads < accurate.cpu_threads <= 6, "CPU thread budget is not bounded")
    assert_true(speed.beam_size < accurate.beam_size, "quality profile does not widen decoding")
    assert_true(get_audio_profile("unknown").key == "normal", "invalid profile does not fall back safely")


def test_streaming_and_deduplication() -> None:
    profile = get_audio_profile("speed")
    segmenter = LiveAudioSegmenter(profile, processing="vad", sample_rate=16000)
    emitted = []
    for _ in range(8):
        value = segmenter.feed(np.zeros(800, dtype=np.float32))
        if value is not None:
            emitted.append(value)
    for _ in range(16):
        value = segmenter.feed(np.full(800, 0.05, dtype=np.float32))
        if value is not None:
            emitted.append(value)
    for _ in range(12):
        value = segmenter.feed(np.zeros(800, dtype=np.float32))
        if value is not None:
            emitted.append(value)
    assert_true(len(emitted) == 1, f"VAD did not coalesce one utterance: {len(emitted)}")
    assert_true(emitted[0].size >= int(profile.min_speech_seconds * 16000), "VAD emitted an undersized segment")

    normal_segmenter = LiveAudioSegmenter(profile, processing="normal", sample_rate=16000)
    normal_emitted = None
    normal_chunks = int(np.ceil((profile.normal_chunk_seconds * 16000) / 800.0)) + 2
    for _ in range(normal_chunks):
        value = normal_segmenter.feed(np.full(800, 0.02, dtype=np.float32))
        if value is not None:
            normal_emitted = value
    assert_true(normal_emitted is not None, "Normal processing never emitted a fixed window")

    dedupe = TranscriptDeduplicator()
    assert_true(dedupe.accept("We are going home") == "We are going home", "first transcript rejected")
    assert_true(dedupe.accept("We are going home") == "", "duplicate transcript was not blocked")
    trimmed = dedupe.accept("going home right now", allow_overlap_trim=True)
    assert_true(trimmed == "right now", f"overlap was not trimmed: {trimmed}")


def test_pcm_conversion() -> None:
    stereo = np.array([1000, -1000, 3000, 1000], dtype=np.int16).tobytes()
    mono = pcm16_to_mono_float(stereo, 2)
    assert_true(mono.shape == (2,), f"stereo conversion shape invalid: {mono.shape}")
    assert_true(abs(float(mono[0])) < 1e-7, "stereo mean conversion invalid")
    resampled = resample_linear(np.arange(480, dtype=np.float32), 48000, 16000)
    assert_true(resampled.shape == (160,), f"resample ratio invalid: {resampled.shape}")


def test_sidecar_protocol() -> None:
    payload = EVENT_PREFIX + '{"type":"transcript","text":"hello"}\nnoise\n'
    events = parse_sidecar_events(payload)
    assert_true(events == [{"type": "transcript", "text": "hello"}], f"sidecar protocol parse failed: {events}")
    source = (ROOT / "audio_asr_sidecar.py").read_text(encoding="utf-8")
    assert_true('selected_device = "cuda"' in source and '"int8_float16"' in source and '"int8"' in source, "sidecar does not expose CPU/GPU compute contracts")
    assert_true('queue.Queue(maxsize=2)' in source, "ASR queue is unbounded")
    assert_true('task="translate"' in source, "non-English speech is not normalized to English before ID translation")
    assert_true('choices=["normal", "vad"]' in source, "unsupported isolation entered the runtime path")
    tree = ast.parse(source)
    parser_options = [
        arg.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for arg in node.args[:1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    assert_true(len(parser_options) == len(set(parser_options)), "sidecar CLI contains duplicate options")


def test_runtime_isolation() -> None:
    requirements = (ROOT / "requirements_audio_cpu.txt").read_text(encoding="utf-8")
    assert_true("faster-whisper==1.2.1" in requirements, "faster-whisper is not pinned")
    assert_true("PyAudioWPatch==0.2.12.8" in requirements, "WASAPI dependency is not pinned")
    for forbidden in ("torch", "PyQt5", "argostranslate"):
        assert_true(forbidden not in requirements, f"Audio sidecar unnecessarily duplicates main runtime dependency: {forbidden}")
    backend = (ROOT / "audio_runtime_backend.py").read_text(encoding="utf-8")
    assert_true('runtime_root / "audio_cpu"' in backend, "Audio runtime is not isolated")
    assert_true('"-m", "venv"' in backend, "Audio setup does not create a sidecar environment")
    assert_true('cfg.get("runtime_python")' in backend, "custom ORT runtime Python path is ignored")


def test_launcher_and_source_exclusivity() -> None:
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    translation = (ROOT / "translation_engine.py").read_text(encoding="utf-8")
    assert_true("def start_audio(" in launcher, "Audio launch path missing")
    assert_true('script_path = BASE_DIR / "audio_main.py"' in launcher, "Audio does not use its dedicated parent runtime")
    assert_true('"translation_source": "audio"' in launcher, "Audio state identity missing")
    assert_true("ocr_process=disabled" in launcher, "OCR exclusivity is not logged")
    assert_true("if self.proc and self.proc.poll() is None" in launcher, "single-process exclusivity guard missing")
    assert_true('"ORT_AUDIO_RUNTIME_PYTHON"' in launcher, "ASR sidecar runtime is not injected")
    assert_true('test_path = None\n        if input_mode == "file":' in launcher, "hidden test file can override live loopback input")
    assert_true('ORT_TRANSLATION_SOURCE", "ocr").strip().lower() == "audio"' in translation, "Audio utterances are still treated as progressive OCR fragments")


def test_ui_contract() -> None:
    source = (ROOT / "webui.py").read_text(encoding="utf-8")
    ast.parse(source)
    for marker in (
        '("Audio · Live Media/Local", "audio")',
        'audio_start_btn = gr.Button("Mulai Audio"',
        'setup_audio_btn = gr.Button(',
        'label="File audio uji',
        'label="Pemrosesan lokal/fallback"',
        'label="Profil ASR lokal/fallback"',
        'label="Perangkat ASR lokal / fallback"',
        "start_audio_model(",
        "_stop_runtime_for_source_switch",
    ):
        assert_true(marker in source, f"missing UI marker: {marker}")
    assert_true("AUDIO_RUNTIME_AVAILABLE = False" not in source, "Audio remains hard-disabled")
    assert_true('(“Isolasi Suara”, "isolation")' not in source and '("Isolasi Suara", "isolation")' not in source, "unimplemented isolation is selectable")
    assert_true("prepare_source_switch_stop()" in source, "asynchronous source switch has no lifecycle guard")
    assert_true("finish_source_switch_stop()" in source, "source-switch lifecycle guard is never released")


def test_parent_generation_guard() -> None:
    source = (ROOT / "audio_main.py").read_text(encoding="utf-8")
    assert_true("self._pending: Optional[dict] = None" in source, "latest-only pending translation slot is missing")
    assert_true("self._inflight: Optional[dict] = None" in source, "single in-flight translation guard is missing")
    assert_true("stale translation blocked" in source, "stale translation guard missing")
    assert_true("generation_id" in source, "Audio results have no generation identity")
    assert_true("ORT_STOP_REQUEST_FILE" in source, "Audio parent ignores graceful stop request")
    assert_true("AudioOverlay" in source, "Audio has no playable overlay")
    assert_true('self.translation_label.setText("Menerjemahkan…")' not in source, "Audio overlay flashes a translation placeholder")


def test_status_contract() -> None:
    status = (ROOT / "status_manager.py").read_text(encoding="utf-8")
    launcher = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    assert_true('"audio_runtime"' in status, "Audio status is not canonical")
    assert_true('read_status("audio_runtime"' in launcher, "WebUI runtime cards do not read Audio status")


def main() -> None:
    test_release_identity()
    test_profile_contract()
    test_streaming_and_deduplication()
    test_pcm_conversion()
    test_sidecar_protocol()
    test_runtime_isolation()
    test_launcher_and_source_exclusivity()
    test_ui_contract()
    test_parent_generation_guard()
    test_status_contract()
    print(f"{APP_VERSION_TAG} Audio CPU regression PASS")


if __name__ == "__main__":
    main()
