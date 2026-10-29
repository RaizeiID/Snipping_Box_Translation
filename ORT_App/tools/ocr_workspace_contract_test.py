"""OCR UI -> launcher contract tests, with no model execution or user-data writes."""
from __future__ import annotations

import ast
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from app.ocr.session_config import basic_capture_defaults, launch_options
import launcher_backend as backend


def ui_functions():
    """Load actual callbacks without building the UI or probing hardware."""
    tree = ast.parse((APP / "webui.py").read_text(encoding="utf-8-sig"))
    names = {"_start", "_oa_ocr_start", "_normalize_ui_mode", "_settings_mode_is_manual",
             "_ocr_language_update", "_ui_mode_visibility", "_oa_ocr_setup_ui"}
    namespace = {
        "gr": types.SimpleNamespace(update=lambda **kw: kw),
        "_status_html": lambda s: s, "runtime_summary_text": lambda: "runtime",
        "_load_saved_prefs": lambda: {}, "_save_ui_pref": Mock(),
        "_builtin_model_values": lambda *a: {"interval_ms": 240, "ocr_resolution": 65},
        "basic_capture_defaults": basic_capture_defaults,
        "BASIC_RESOURCE_DEFAULTS": ("stable", 3, "adaptive"),
        "_validated_ocr_options": lambda *a: (launch_options(*a), ""),
        "start_model": Mock(return_value=("RUNNING", "log", "started", "")),
        "html": __import__("html"),
        "PROJECT_ROOT": APP, "sys": sys, "subprocess": types.SimpleNamespace(run=Mock()),
        "_oa_ocr_provider_table": lambda: "providers",
    }
    from app.ocr.session_config import LANGUAGE_CHOICES
    namespace["OCR_LANGUAGE_CHOICES"] = LANGUAGE_CHOICES
    code = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    exec(compile(code, str(APP / "webui.py"), "exec"), namespace)
    return namespace


class OCRContractTests(unittest.TestCase):
    def test_setup_installs_the_selected_provider(self):
        for provider, expected in (("easyocr_craft", ["easyocr"]),
                                   ("rapidocr_onnx", ["-r", str(APP / "requirements_ocr_lab.txt")])):
            ui = ui_functions()
            ui["subprocess"].run.return_value = types.SimpleNamespace(returncode=0, stdout="done", stderr="")
            with patch("app.ocr.ocr_provider_registry.probe_provider", side_effect=[
                    {"ready": False}, {"ready": True, "detail": "installed"}]):
                _, message = ui["_oa_ocr_setup_ui"](provider, "cpu")
            self.assertEqual(ui["subprocess"].run.call_args.args[0][4:], expected)
            self.assertIn("BERHASIL", message)

    def test_main_basic_ignores_hidden_manual_settings(self):
        ui = ui_functions()
        with patch("app.ocr.ocr_provider_registry.effective_devices", return_value=("cpu",)):
            ui["_start"]("ORTCore V3", "GFL2_EXILIUM", "freeze", "gpu", 45, 5,
                         "manual", True, "diagnostic_no_name_roi", True, "ocr",
                         "intensive", 5, "quality", "easyocr_craft", "en", "basic")
        args, kw = ui["start_model"].call_args
        self.assertEqual(args[2:6], ("auto", "cpu", 240, 65))
        self.assertEqual(args[8:], ("recommended", False, "baseline", False))
        self.assertEqual(kw["ocr_options"]["audio_resource_mode"], "stable")
        self.assertEqual(kw["ocr_options"]["audio_resource_level"], 3)

    def test_lab_does_not_save_tools_or_audio_preferences(self):
        ui = ui_functions()
        with patch("app.ocr.ocr_provider_registry.effective_devices", return_value=("cpu", "cuda")):
            ui["_oa_ocr_start"]("GFL2_EXILIUM", "ORTCore V3", "ja,en", "interval", "gpu",
                                True, 420, 75, "intensive", 5, "quality", "easyocr_craft", "developer")
        args, kw = ui["start_model"].call_args
        self.assertEqual(args[2:5], ("interval", "gpu", 420))
        self.assertEqual(kw["ocr_resolution"], 75)
        self.assertEqual(kw["ocr_options"]["ocr_languages"], "ja,en")
        self.assertEqual(kw["ocr_options"]["workspace"], "lab")
        for call in ui["_save_ui_pref"].call_args_list:
            self.assertTrue(all(k.startswith("oa_ocr_") for k in call.kwargs))

    def test_lab_basic_uses_core_defaults_not_hidden_sliders(self):
        ui = ui_functions()
        with patch("app.ocr.ocr_provider_registry.effective_devices", return_value=("cpu",)):
            ui["_oa_ocr_start"]("GFL2_EXILIUM", "ORTCore V3", "en", "freeze", "gpu",
                                True, 45, 40, "intensive", 5, "quality", "tesseract", "basic")
        args, kw = ui["start_model"].call_args
        self.assertEqual(args[2:5], ("auto", "cpu", 240))
        self.assertEqual(kw["ocr_resolution"], 65)
        self.assertFalse(kw["mode_buffer_enabled"])
        self.assertEqual(kw["ocr_options"]["audio_resource_level"], 3)

    def test_fixed_rapidocr_language_and_basic_visibility(self):
        ui = ui_functions()
        update, note = ui["_ocr_language_update"]("rapidocr_onnx", "ja,en")
        self.assertEqual(update, {"value": "ch_sim,en", "interactive": False})
        self.assertIn("model bawaan", note)
        self.assertFalse(ui["_ui_mode_visibility"]("basic")["core_controls"])
        self.assertTrue(ui["_ui_mode_visibility"]("developer")["core_controls"])
        with self.assertRaises(ValueError):
            launch_options("easyocr_craft", "bad-language", "stable", 3, "adaptive")

    def launch_backend(self, workspace, resource_mode, level, engine="cpu", capture="interval", basic=False, model="ORTCore V3"):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            (root / "TITANMAIN.py").touch()
            stack.enter_context(patch.object(backend, "BASE_DIR", root))
            stack.enter_context(patch.object(backend, "load_prefs", return_value={
                "ocr_provider": "tesseract", "ocr_languages": "ch_sim,en",
                "audio_resource_mode": "efficient", "audio_resource_level": 1}))
            stack.enter_context(patch.object(backend, "get_runtime_config", return_value={
                "runtime_python": sys.executable, "runtime_root": str(root)}))
            save = stack.enter_context(patch.object(backend, "save_prefs"))
            for name in ("save_state", "clear_stop_request", "write_strategy_status",
                         "write_lite_gpu_status", "record_runtime_line"):
                stack.enter_context(patch.object(backend, name))
            stack.enter_context(patch.object(backend, "load_settings", return_value={}))
            stack.enter_context(patch.object(backend, "env_from_settings", return_value={}))
            stack.enter_context(patch.object(backend, "apply_online_config_to_env", return_value={}))
            stack.enter_context(patch.object(backend, "apply_vram_safety_env", return_value=None))
            stack.enter_context(patch.object(backend, "apply_lite_gpu_env", return_value=None))
            stack.enter_context(patch.object(backend, "FastModelManager", return_value=types.SimpleNamespace(
                status=lambda: {"state": "ACTIVE", "active": True, "model_dir": str(root)}, model_dir=root)))
            session = types.SimpleNamespace(session_id="test", full_log_path=root / "full.log",
                                            jsonl_path=root / "events.jsonl", append_line=lambda text: None)
            stack.enter_context(patch.object(backend, "start_session", return_value=session))
            popen = stack.enter_context(patch.object(backend.subprocess, "Popen"))
            stack.enter_context(patch.object(backend.threading, "Thread"))
            manager = backend.ProcessManager()
            options = launch_options("easyocr_craft", "en", resource_mode, level, "adaptive", workspace)
            options["basic"] = basic
            result = manager.start(model, "GFL2_EXILIUM", capture, engine, 420,
                ocr_resolution=75, settings_mode="manual", mode_buffer_enabled=True,
                ocr_options=options)
            self.assertIn("RUNNING", result[0])
            return popen.call_args.kwargs["env"], save.call_count

    def test_real_launcher_receives_lab_contract_without_saving_main(self):
        env, saves = self.launch_backend("lab", "intensive", 5, "gpu")
        self.assertEqual(saves, 0)
        self.assertEqual(env["ORT_OCR_PROVIDER"], "easyocr_craft")
        self.assertEqual(env["ORT_OCR_LANGUAGES"], "en")
        self.assertEqual(env["ORT_BOOT_ENGINE"], "gpu")
        self.assertEqual(env["ORT_BOOT_MODE"], "interval")
        self.assertEqual(env["ORT_BOOT_INTERVAL_MS"], "420")
        self.assertEqual(env["ORT_MODE_BUFFER"], "1")
        self.assertEqual(env["ORT_RESOURCE_LEVEL"], "5")
        self.assertEqual(env["ORT_BOOT_OCR_RESOLUTION"], "68")  # existing GFL2 normal-core safety cap
        self.assertEqual(env["ORT_REQUESTED_OCR_RESOLUTION_PERCENT"], "75")
        # These keys were absent when strategy was read before assignment.
        self.assertIn("ORT_STRICT_CT2_RELEASE_FRAGMENTS", env)
        self.assertIn("ORT_STRICT_CT2_FRAGMENT_MIN_WORDS", env)

    def test_resource_controls_change_real_runtime_environment(self):
        light, _ = self.launch_backend("lab", "efficient", 5)
        heavy, _ = self.launch_backend("lab", "intensive", 5)
        for key in ("TITAN_CT2_BEAM", "ORT_OCR_DETECTOR_CANVAS", "TITAN_CPU_THREADS",
                    "TITAN_QUEUE_MAX", "TITAN_VRAM_CRITICAL_GB"):
            self.assertNotEqual(light[key], heavy[key], key)
        _, saves = self.launch_backend("tools", "stable", 3)
        self.assertGreater(saves, 0)

    def test_basic_launch_does_not_overwrite_saved_advanced_settings(self):
        _, saves = self.launch_backend("tools", "stable", 3, basic=True)
        self.assertEqual(saves, 0)

    def test_every_ocr_core_launches_with_all_three_resource_modes(self):
        from model_registry import list_models
        for model in list_models():
            for mode, level in (("efficient", 5), ("stable", 3), ("intensive", 5)):
                with self.subTest(core=model.title, resource=mode):
                    env, saves = self.launch_backend("lab", mode, level, model=model.title)
                    self.assertEqual(env["ORT_MODEL_KEY"], model.key)
                    self.assertEqual(env["ORT_RESOURCE_MODE"], mode)
                    self.assertEqual(env["ORT_BOOT_MODE"], "interval")
                    self.assertEqual(env["ORT_BOOT_ENGINE"], "cpu")
                    self.assertIn("ORT_STRICT_CT2_RELEASE_FRAGMENTS", env)
                    self.assertEqual(saves, 0)

    def test_rapidocr_passes_device_and_thread_choices_to_engine(self):
        from app.ocr import ocr_provider_registry as registry
        # No model loading: inspect what the adapter sends to the actual API boundary.
        for gpu in (False, True):
            constructor = Mock()
            module = types.SimpleNamespace(RapidOCR=constructor)
            with patch.dict(sys.modules, {"rapidocr_onnxruntime": module}), \
                 patch.object(registry, "effective_devices", return_value=("cpu", "cuda")), \
                 patch.dict(__import__("os").environ, {"TITAN_CPU_THREADS": "2"}):
                engine = registry.OCREngine("rapidocr_onnx", gpu=gpu, languages=("en",))
                engine.load()
            self.assertEqual(constructor.call_args.kwargs, {
                "det_use_cuda": gpu, "cls_use_cuda": gpu, "rec_use_cuda": gpu,
                "intra_op_num_threads": min(__import__("os").cpu_count() or 1, 2),
                "inter_op_num_threads": 1,
            })

    def test_native_provider_boxes_keep_text_coordinates_and_confidence(self):
        from app.ocr import ocr_provider_registry as registry
        box = [[1, 2], [20, 2], [20, 12], [1, 12]]
        with patch.object(registry, "effective_devices", return_value=("cpu",)):
            rapid = registry.OCREngine("rapidocr_onnx")
            rapid._impl = Mock(return_value=([[box, "Helena", 0.95]], 0.1))
            self.assertEqual(rapid.read_boxes(None), [[box, "Helena", 0.95]])
            tess = registry.OCREngine("tesseract", languages=("en",))
            data = {
                "text": ["", "Commander,", "ready"], "conf": [-1, 90, 80],
                "block_num": [0, 1, 1], "par_num": [0, 1, 1], "line_num": [0, 1, 1],
                "left": [0, 10, 100], "top": [0, 5, 5], "width": [0, 80, 40], "height": [0, 20, 20],
            }
            tess._impl = types.SimpleNamespace(image_to_data=Mock(return_value=data),
                                                Output=types.SimpleNamespace(DICT="dict"))
            result = tess.read_boxes(None)
            self.assertEqual(result[0][0], [[10, 5], [140, 5], [140, 25], [10, 25]])
            self.assertEqual(result[0][1], "Commander, ready")
            self.assertAlmostEqual(result[0][2], 0.85)
            self.assertEqual(tess._impl.image_to_data.call_args.kwargs["lang"], "eng")

    def test_runtime_detail_pass_does_not_substitute_easyocr(self):
        tree = ast.parse((APP / "TITANMAIN.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_ORTProviderReader")
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "TITANMAIN.py", "exec"), scope)
        reader = object.__new__(scope["_ORTProviderReader"])
        reader._engine = types.SimpleNamespace(read_boxes=Mock(return_value=["boxes"]),
                                               read=Mock(return_value=["text"]))
        self.assertEqual(reader.readtext("image", detail=1, allowlist="ABC"), ["boxes"])
        reader._engine.read_boxes.assert_called_once_with("image", allowlist="ABC")
        self.assertEqual(reader.readtext("image", detail=0), ["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
