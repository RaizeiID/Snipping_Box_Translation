"""Generate a lightweight Python-file usage report for ORT Translation v7.1.
Run from project root: python _tools/audit_py_usage_v71.py
"""
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENTRY_POINTS = {"webui.py", "launcher_backend.py", "TITANMAIN.py", "model_registry.py", "v7_system_profile.py", "v71_runtime_bridge.py"}
ARCHIVE_DIRS = {"_archive_v6_legacy", "__pycache__"}


def imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def main():
    py_files = [p for p in ROOT.rglob("*.py") if not any(part in ARCHIVE_DIRS for part in p.parts)]
    module_to_file = {p.stem: p for p in py_files}
    graph = {str(p.relative_to(ROOT)): sorted(imports_of(p) & module_to_file.keys()) for p in py_files}
    reachable = set()
    stack = [Path(x).stem for x in ENTRY_POINTS]
    # v71_runtime_bridge uses safe dynamic imports from CORE_SLOTS, so include those modules.
    try:
        from v71_runtime_bridge import CORE_SLOTS
        stack.extend([slot.module for slot in CORE_SLOTS if getattr(slot, "active", False)])
    except Exception:
        pass
    while stack:
        mod = stack.pop()
        if mod in reachable:
            continue
        reachable.add(mod)
        p = module_to_file.get(mod)
        if not p:
            continue
        for nxt in imports_of(p) & module_to_file.keys():
            if nxt not in reachable:
                stack.append(nxt)
    report = {
        "entry_points": sorted(ENTRY_POINTS),
        "total_py_files_non_archive": len(py_files),
        "reachable_or_v71_bridge_active_modules": sorted(reachable),
        "maybe_manual_or_compat_modules": sorted(set(module_to_file) - reachable),
        "graph": graph,
    }
    out = ROOT / "V7_1_PY_USAGE_REPORT.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"reachable={len(reachable)} / total={len(py_files)}")

if __name__ == "__main__":
    main()
