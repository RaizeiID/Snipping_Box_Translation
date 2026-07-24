from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from build_info import APP_VERSION_TAG
from app.runtime.ct2_path_resolver import resolve_ct2_model_dir


def _load_realtime_sidecar():
    try:
        import app.audio.cuda_bootstrap  # noqa: F401
        import app.audio.turn_context  # noqa: F401
    except Exception:
        app = sys.modules.setdefault("app", types.ModuleType("app"))
        if not hasattr(app, "__path__"):
            app.__path__ = []
        audio = sys.modules.setdefault("app.audio", types.ModuleType("app.audio"))
        if not hasattr(audio, "__path__"):
            audio.__path__ = []
        cuda = types.ModuleType("app.audio.cuda_bootstrap")
        cuda.activate_cuda_dll_search = lambda: {}
        turn = types.ModuleType("app.audio.turn_context")

        @dataclass
        class Result:
            text: str
            full_words: int
            words: int
            truncated: bool
            revisions: int
            appended_words: int

        class RollingTurnContext:
            def __init__(self, max_history_words=96, display_words=36):
                self.display_words = display_words

            def update(self, key, text, stable=False):
                words = " ".join(str(text or "").split()).split()
                shown = words[-self.display_words :]
                return Result(
                    ("… " if len(words) > self.display_words else "") + " ".join(shown),
                    len(words),
                    len(shown),
                    len(words) > self.display_words,
                    1,
                    len(words),
                )

            def clear(self, key):
                return None

        turn.RollingTurnContext = RollingTurnContext
        sys.modules["app.audio.cuda_bootstrap"] = cuda
        sys.modules["app.audio.turn_context"] = turn

    path = APP_ROOT / "audio_realtime_local_sidecar.py"
    spec = importlib.util.spec_from_file_location("ort_v902_sidecar_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_translation_sidecar():
    path = APP_ROOT / "audio_translation_sidecar.py"
    spec = importlib.util.spec_from_file_location("ort_v902_translation_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.4"

    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    audio_main = (APP_ROOT / "audio_main.py").read_text(encoding="utf-8-sig")
    executor = (APP_ROOT / "app" / "open_architecture" / "executor.py").read_text(encoding="utf-8-sig")
    assert "Model terjemahan ORT" not in webui
    assert "Mode box terjemahan" in webui
    assert "Adaptif · mengikuti teks" in webui
    assert "Fix · ukuran tetap mengikuti monitor" in webui
    assert "Custom · ukuran dan layout bebas" in webui
    assert "QSizeGrip" in audio_main
    assert 'overlay_mode == "fixed"' in audio_main
    assert 'internal_translation_model = "ORTCore Fast V2"' in executor

    with tempfile.TemporaryDirectory(prefix="ort-v902-ct2-") as tmp:
        root = Path(tmp)
        app_root = root / "ORT_App"
        app_root.mkdir()
        model = root / "ORT_Runtime" / "translation" / "models" / "ct2_opus_mt_en_id"
        model.mkdir(parents=True)
        for name in ("model.bin", "source.spm", "target.spm"):
            (model / name).write_bytes(b"test")
        resolved = resolve_ct2_model_dir(app_root)
        assert resolved.likely_valid
        assert resolved.path == model.resolve()

    translation = _load_translation_sidecar()

    class FakeEngine:
        def __init__(self):
            self.calls = []

        def translate(self, text, bridge=None):
            self.calls.append(text)
            return "ID<" + text + ">", {"engine": "fake_ct2", "cache": "MISS"}

    translator = translation.AudioTranslator.__new__(translation.AudioTranslator)
    translator.safe_mode = False
    translator._argos_translation = False
    translator._engine = FakeEngine()
    translator._segments = {}
    translator._segment_limit = 32
    translator.engine_label = lambda: "fake_ct2"
    translator._argos_translate = lambda text: "ID-RECOVERY<" + text + ">"

    first, first_meta = translator.translate("First sentence.", segment_id="seg-1", stable=False)
    second, second_meta = translator.translate("First sentence. Second sentence.", segment_id="seg-1", stable=False)
    repeated, repeated_meta = translator.translate("First sentence. Second sentence.", segment_id="seg-1", stable=True)
    assert first == "ID<First sentence.>"
    assert second == "ID<First sentence.> ID<Second sentence.>"
    assert second_meta["audio_reused_clauses"] == 1
    assert second_meta["audio_translated_clauses"] == 1
    assert repeated == second
    assert repeated_meta["audio_translated_clauses"] == 0
    assert len(translator._engine.calls) == 2

    sidecar = _load_realtime_sidecar()

    class FakeWorker:
        def __init__(self):
            self.rows = []
            self.submitted = []

        def drain_feedback(self):
            rows, self.rows = self.rows, []
            return rows

        def submit(self, snapshot):
            self.submitted.append(snapshot)

    policy = sidecar.LocalRealtimePolicy(
        profile="test",
        first_partial_s=0.20,
        partial_interval_s=0.20,
        endpoint_s=9.0,
        max_phrase_s=6.0,
        pre_roll_s=0.10,
        carry_over_s=0.10,
        minimum_rms=0.003,
        noise_multiplier=2.0,
        short_pause_s=0.20,
        long_pause_s=0.40,
        subtitle_window_s=0.80,
        hard_turn_s=1.20,
        semantic_no_speech_passes=2,
    )
    worker = FakeWorker()
    controller = sidecar.UtteranceController(worker, policy)
    chunk = sidecar.np.full(int(sidecar.TARGET_SAMPLE_RATE * 0.02), 0.05, dtype=sidecar.np.float32)
    start = 100.0
    for index in range(20):
        controller.feed(chunk, start + index * 0.02)
    active = controller.active_result_id
    worker.rows.extend([
        {"kind": "semantic", "result_id": active, "text": "Sentence complete.", "stable": False, "at": start + 0.40},
        {"kind": "no_speech", "result_id": active, "text": "", "stable": False, "at": start + 0.42},
        {"kind": "no_speech", "result_id": active, "text": "", "stable": False, "at": start + 0.44},
    ])
    for index in range(25):
        controller.feed(chunk, start + 0.46 + index * 0.02)
    assert any(item.stable and item.result_id == active for item in worker.submitted)
    assert controller.active_result_id != active

    # An unfinished clause must survive a short pause. This distinguishes a
    # speaker thinking mid-sentence from a real dialogue boundary.
    worker2 = FakeWorker()
    controller2 = sidecar.UtteranceController(worker2, policy)
    for index in range(20):
        controller2.feed(chunk, start + 2.0 + index * 0.02)
    active2 = controller2.active_result_id
    worker2.rows.extend([
        {"kind": "semantic", "result_id": active2, "text": "This clause is still", "stable": False, "at": start + 2.40},
        {"kind": "no_speech", "result_id": active2, "text": "", "stable": False, "at": start + 2.42},
        {"kind": "no_speech", "result_id": active2, "text": "", "stable": False, "at": start + 2.44},
    ])
    for index in range(12):
        controller2.feed(chunk, start + 2.46 + index * 0.02)
    assert controller2.active_result_id == active2
    worker2.rows.append({
        "kind": "semantic", "result_id": active2, "text": "This clause is still continuing", "stable": False, "at": start + 2.72,
    })
    controller2.feed(chunk, start + 2.74)
    assert controller2.active_result_id == active2

    result = {
        "passed": True,
        "version": APP_VERSION_TAG,
        "model_selector_removed": True,
        "overlay_modes": ["adaptive", "fixed", "custom"],
        "ct2_v9_layout_resolution": "PASS",
        "incremental_translation": {
            "engine_calls": len(translator._engine.calls),
            "reused_clauses": second_meta["audio_reused_clauses"],
        },
        "smart_turn_boundary": "PASS",
        "short_pause_continuation": "PASS",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
