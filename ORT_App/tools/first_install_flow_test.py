"""Test Windows installer success/failure without installing packages or opening WebUI."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1]


class FirstInstallTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows batch execution")
    def test_dependency_failures_do_not_start_webui_and_can_retry(self):
        original = (APP / "Start_ORT_Translation.bat").read_text(encoding="utf-8-sig")
        # Select a runtime fixture instead of presenting an interactive menu.
        body = original[original.index(":write_cfg\n"):]
        body = body.replace('set "RUNTIME_PY=%RUNTIME_ROOT%\\.venv\\Scripts\\python.exe"',
                            f'set "RUNTIME_PY={sys.executable}"', 1)
        body = body.replace("\npause\n", "\nrem noninteractive test\n")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / "ORT_App"
            app.mkdir()
            runtime = root / "ORT_Runtime"
            script = app / "test_setup.bat"
            header = (f'@echo off\nsetlocal EnableExtensions EnableDelayedExpansion\n'
                      f'cd /d "{app}"\nset "APP_ROOT={app}"\n'
                      f'set "PROJECT_ROOT={root}"\nset "RUNTIME_ROOT={runtime}"\n'
                      f'set "CFG={app / "runtime_paths.json"}"\n')
            script.write_bytes((header + body).replace("\n", "\r\n").encode("utf-8"))
            for name in ("requirements_base.txt", "requirements_torch_cu121.txt",
                         "requirements_torch_cpu.txt", "constraints_runtime_cu121.txt",
                         "constraints_runtime_cpu.txt"):
                (app / name).touch()
            # Python -m resolves this fixture before the real pip package.
            (app / "pip.py").write_text(
                'import os,sys\nfrom pathlib import Path\n'
                'stage="torch" if any("requirements_torch_" in s for s in sys.argv) else '
                '("base" if any("requirements_base" in s for s in sys.argv) else "upgrade")\n'
                'with Path("attempts.txt").open("a") as f: f.write(stage+"\\n")\n'
                'sys.exit(7 if os.environ.get("ORT_TEST_FAIL_AT")==stage else 0)\n', encoding="utf-8")
            (app / "webui.py").write_text(
                'from pathlib import Path\nPath("web_started").write_text("yes")\n', encoding="utf-8")
            for failure in ("upgrade", "torch", "base", ""):
                with self.subTest(failure=failure or "retry-success"):
                    result = subprocess.run(["cmd", "/d", "/c", str(script)], cwd=app,
                        env={**os.environ, "ORT_TEST_FAIL_AT": failure}, capture_output=True,
                        text=True, errors="replace", timeout=30)
                    self.assertEqual(result.returncode, 4 if failure else 0, result.stdout + result.stderr)
                    self.assertEqual((app / "web_started").exists(), not bool(failure))
            self.assertTrue((app / "runtime_paths.json").is_file())

    def test_repair_preserves_public_readme_and_launchers(self):
        spec = importlib.util.spec_from_file_location("migration_fixture", APP / "tools/migrate_v9_structure.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            support = root / "ORT"
            names = ["README.md", "Instalation First.bat", "Start WebUI.bat", "Repair Struktur ORT.bat"]
            for name in names:
                (root / name).write_text("keep-me", encoding="utf-8")
            report = module.MigrationReport(str(root), "source", "target")
            module._organize_root_files(root, support, report)
            for name in names:
                self.assertEqual((root / name).read_text(encoding="utf-8"), "keep-me")


if __name__ == "__main__":
    unittest.main(verbosity=2)
