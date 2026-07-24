from __future__ import annotations

import ast
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
WEBUI = APP / "webui.py"
TARGET = "_oa_delivery_mode_updates"


def main() -> int:
    source = WEBUI.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(WEBUI))
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == TARGET
    ]
    errors: list[str] = []
    if len(definitions) != 1:
        errors.append(f"expected exactly one {TARGET} definition, found {len(definitions)}")
    if not calls:
        errors.append(f"no {TARGET} call found")
    if definitions and calls:
        definition_line = definitions[0].lineno
        first_call_line = min(node.lineno for node in calls)
        if definition_line >= first_call_line:
            errors.append(
                f"definition line {definition_line} must precede first call line {first_call_line}"
            )

    behavior = {}
    if definitions:
        namespace = {"_save_ui_pref": lambda **kwargs: behavior.setdefault("saved", kwargs)}
        isolated = ast.Module(body=[definitions[0]], type_ignores=[])
        ast.fix_missing_locations(isolated)
        exec(compile(isolated, str(WEBUI), "exec"), namespace)
        fn = namespace[TARGET]
        behavior["offline"] = fn("offline", "google")
        behavior["online"] = fn("online", "azure")
        behavior["hybrid_catalog"] = fn("hybrid", "aws")
        if "Offline" not in behavior["offline"]:
            errors.append("offline message invalid")
        if "Azure" not in behavior["online"]:
            errors.append("online message invalid")
        if "catalog-only" not in behavior["hybrid_catalog"]:
            errors.append("catalog guard message invalid")

    result = {
        "passed": not errors,
        "version": "v9.0.4-R4-F1",
        "webui_compile": "PASS",
        "delivery_mode_callback_defined": len(definitions) == 1,
        "definition_before_ui_construction": bool(definitions and calls and definitions[0].lineno < min(n.lineno for n in calls)),
        "startup_import_smoke_required_by_applicator": True,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
