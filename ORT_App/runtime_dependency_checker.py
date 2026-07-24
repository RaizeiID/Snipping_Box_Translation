"""ORT Translation v8.0 runtime dependency checker."""
from __future__ import annotations
import importlib.util, json, sys, time
from pathlib import Path
from typing import Dict, Any
from status_manager import write_status
BASE_DIR = Path(__file__).resolve().parent
MODULES = {
    "PyQt5": "PyQt5",
    "gradio": "gradio",
    "easyocr": "easyocr",
    "mss": "mss",
    "cv2/opencv-python": "cv2",
    "numpy": "numpy",
    "torch": "torch",
    "keyboard": "keyboard",
    "argostranslate": "argostranslate",
    "psutil": "psutil",
    "requests": "requests",
    "ctranslate2(optional_fast)": "ctranslate2",
    "sentencepiece(optional_fast)": "sentencepiece",
}
def check_dependencies(base_dir: str | Path | None = None) -> Dict[str, Any]:
    base = Path(base_dir or BASE_DIR).resolve()
    items = {name: (importlib.util.find_spec(mod) is not None) for name, mod in MODULES.items()}
    required = ["PyQt5","gradio","easyocr","mss","cv2/opencv-python","numpy","torch","keyboard","argostranslate","psutil","requests"]
    missing_required = [x for x in required if not items.get(x)]
    payload = {
        "version":"v8.0", "ts":time.time(), "python":sys.executable,
        "ok": not missing_required, "missing_required": missing_required, "modules": items,
        "hint":"Install requirements.txt for base runtime; requirements_fast_optional.txt for full Fast Engine.",
    }
    write_status("dependency_check", payload, base)
    return payload
def dependency_report_text(base_dir: str | Path | None = None) -> str:
    data = check_dependencies(base_dir)
    lines = ["ORT Translation v8.0 Dependency Check", "====================================", f"Python: {data['python']}", f"Base OK: {data['ok']}"]
    if data["missing_required"]:
        lines.append("Missing required: " + ", ".join(data["missing_required"]))
    lines.append("")
    for k, v in data["modules"].items():
        lines.append(f"{k:30s}: {'OK' if v else 'MISSING'}")
    lines.append("")
    lines.append(data["hint"])
    return "\n".join(lines)
if __name__ == "__main__":
    print(dependency_report_text())
