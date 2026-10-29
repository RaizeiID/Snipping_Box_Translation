"""Exercise the real ProcessManager without loading OCR/models or touching user data."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch


APP = Path(__file__).resolve().parent.parent
source = (APP / "launcher_backend.py").read_text(encoding="utf-8-sig")
tree = ast.parse(source)
manager_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProcessManager")
# Compile the production class, not a copy of its log implementation. Unused
# runtime globals are deliberately absent so a test cannot launch a model.
namespace = {"threading": threading, "os": os, "APP_VERSION_TAG": "test",
             "record_runtime_line": lambda *args: None}
exec(compile("from __future__ import annotations\n" + ast.unparse(manager_node),
             str(APP / "launcher_backend.py"), "exec"), namespace)
ProcessManager = namespace["ProcessManager"]


class RecordingSession:
    def __init__(self):
        self.lines = []

    def append_line(self, line):
        self.lines.append(line)


class RetentionTests(unittest.TestCase):
    def test_two_hour_session_keeps_every_line_even_with_old_tail_setting(self):
        manager = ProcessManager()
        session = manager.session = RecordingSession()
        # Ten lines per second for two hours, exceeding the former 3,000-line cap.
        expected = [f"[{i // 10}s] GFL2 dialog {i}: 翻译 → Terjemahan Indonesia"
                    for i in range(2 * 60 * 60 * 10)]
        with patch.dict(os.environ, {"ORT_WEBUI_LOG_TAIL_LINES": "3"}):
            for line in expected:
                manager._push(line + "\n")
        full = manager.get_log()
        self.assertEqual(full.splitlines(), expected)
        self.assertEqual(session.lines, expected)
        self.assertIs(manager.get_log(), full)  # unchanged polls reuse snapshot
        manager._push("FINAL")
        self.assertEqual(manager.get_log(), full + "\nFINAL")

    def test_stop_preserves_history_and_new_session_resets_only_live_view(self):
        manager = ProcessManager()
        old_session = manager.session = RecordingSession()
        manager._push("SESSION ONE START")
        manager._push("SESSION ONE END")
        # A finished subprocess is also a normal state when Stop is clicked.
        manager.stop()
        self.assertEqual(manager.get_log(), "SESSION ONE START\nSESSION ONE END")
        self.assertEqual(manager.clear_log(), manager.get_log())
        manager._reset_session_log()
        manager.session = RecordingSession()
        self.assertEqual(manager.get_log(), "")
        manager._push("SESSION TWO START")
        self.assertEqual(manager.get_log(), "SESSION TWO START")
        self.assertEqual(old_session.lines, ["SESSION ONE START", "SESSION ONE END"])

    def test_start_while_running_does_not_reset_history(self):
        manager = ProcessManager()
        manager.proc = type("RunningProcess", (), {"poll": lambda self: None})()
        manager._push("EXISTING SESSION")
        manager.start("lite_v1", "GFL2_EXILIUM", "auto", "cpu", 100)
        self.assertEqual(manager.get_log(), "EXISTING SESSION")

    def test_both_session_start_paths_reset_and_ui_has_no_manual_clear(self):
        for name in ("start", "start_audio"):
            method = next(n for n in manager_node.body if isinstance(n, ast.FunctionDef) and n.name == name)
            calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "_reset_session_log"]
            self.assertEqual(len(calls), 1, name)
        ui = (APP / "webui.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("reset_live_log_btn", ui)
        self.assertIn('elem_id="live_log"', ui)  # existing Copy Live Log still works


if __name__ == "__main__":
    unittest.main(verbosity=2)
