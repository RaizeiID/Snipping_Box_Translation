#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_info import APP_VERSION_TAG, RELEASE_NAME


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG.startswith(("v8.9.2", "v8.9.3", "v8.9.4", "v8.9.5", "v8.9.6")), f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME in {"Guided & Expert UI Refresh", "Audio CPU First-Test", "Audio Model Recovery Hotfix", "Audio Model Compatibility Hotfix", "Audio Native Crash Isolation Hotfix", "Audio Tri-Mode & Japanese Quality Update", "Cloud Live Media Streaming Update"}, f"unexpected release: {RELEASE_NAME}")


def test_ui_information_architecture() -> None:
    source = (ROOT / "webui.py").read_text(encoding="utf-8")
    required = (
        'with gr.Tab("Mulai")',
        'label="Sumber aktif"',
        '("OCR · Siap", "ocr")',
        '("Audio · Live Media/Local", "audio")',
        'label="Tingkat tampilan"',
        '("Basic", "basic")',
        '("Terpandu", "recommended")',
        '("Expert", "expert")',
        'Expert workspace',
        'advanced_controls_panel',
        'Mulai Audio',
        'Pemrosesan lokal/fallback',
        'Profil ASR lokal/fallback',
    )
    for marker in required:
        assert_true(marker in source, f"missing UI marker: {marker}")
    assert_true("Mode Pengaturan" not in source, "ambiguous Mode Pengaturan label returned")


def test_source_exclusivity_and_guard() -> None:
    source = (ROOT / "webui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    start = function_node(tree, "_start")
    args = [item.arg for item in start.args.args]
    assert_true("translation_source" in args, "start handler has no translation source guard")
    switch = function_node(tree, "_translation_source_updates")
    switch_source = ast.get_source_segment(source, switch) or ""
    assert_true("_stop_runtime_for_source_switch" in switch_source, "source switch does not stop the previous runtime")
    assert_true("threading.Thread" in switch_source, "source switch blocks the UI while OCR stops")
    assert_true("gr.update(visible=is_ocr)" in switch_source, "OCR panel visibility is not source-bound")
    assert_true("gr.update(visible=not is_ocr)" in switch_source, "Audio panel visibility is not source-bound")


def test_audio_status_is_honest() -> None:
    source = (ROOT / "webui.py").read_text(encoding="utf-8")
    assert_true("AUDIO_RUNTIME_AVAILABLE = False" not in source, "Audio is still hard-disabled")
    assert_true("Siapkan Audio" in source, "Audio first-run setup is missing")
    assert_true("WASAPI" in source and "VAD" in source and "faster-whisper" in source, "Audio runtime boundary is not explained")
    assert_true('audio_start_btn = gr.Button("Mulai Audio"' in source, "Audio start control is missing")
    assert_true(("Mode eksekusi Audio" in source or "Perangkat ASR lokal / fallback" in source) and "Hybrid · Rekomendasi" in source, "tri-mode contract is not visible")


def test_visual_contract() -> None:
    source = (ROOT / "webui.py").read_text(encoding="utf-8")
    for selector in (
        ".source-stage",
        "#translation_source [role='radiogroup']",
        ".expert-banner",
        ".expert-controls",
        ".audio-preview",
        "@media (max-width: 820px)",
    ):
        assert_true(selector in source, f"missing visual contract: {selector}")


def main() -> None:
    test_release_identity()
    test_ui_information_architecture()
    test_source_exclusivity_and_guard()
    test_audio_status_is_honest()
    test_visual_contract()
    print(f"{APP_VERSION_TAG} guided/expert UI regression PASS")


if __name__ == "__main__":
    main()
