"""ORT Translation v7.8 Python usage audit.
Run from project root: python _tools/audit_py_usage.py
"""
from __future__ import annotations
import ast, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINTS = {"webui.py", "launcher_backend.py", "TITANMAIN.py", "model_registry.py", "model_strategy.py", "runtime_bridge.py", "runtime_actions.py", "translation_engine.py", "status_manager.py"}

def imports_of(path: Path):
    try: tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception: return []
    out=[]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name.split('.')[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.append(n.module.split('.')[0])
    return out

def main():
    py = {p.stem:p for p in ROOT.glob('*.py')}
    graph = {p.name: imports_of(p) for p in ROOT.glob('*.py')}
    seen=set(); stack=[Path(x).stem for x in ENTRY_POINTS if (ROOT/x).exists()]
    while stack:
        m=stack.pop()
        if m in seen: continue
        seen.add(m)
        for imp in graph.get(m+'.py', []):
            if imp in py and imp not in seen: stack.append(imp)
    report={"version":"v7.8", "entry_points":sorted(ENTRY_POINTS), "reachable_modules":sorted(seen), "root_py_count":len(py), "inactive_root_modules":sorted(set(py)-seen)}
    out=ROOT/'V7_8_PY_USAGE_REPORT.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
if __name__=='__main__': main()
