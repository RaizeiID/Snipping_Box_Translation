from __future__ import annotations

import ast
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
WEBUI = APP / "webui.py"

REQUIRED_CALLBACKS = {
    "_oa_delivery_mode_updates",
    "_oa_refresh_provider_status_ui",
    "_oa_provider_status_ui",
    "_oa_setup_selected_provider_ui",
    "_oa_benchmark_providers_ui",
}


def main() -> int:
    source = WEBUI.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(WEBUI))
    errors: list[str] = []

    definitions: dict[str, int] = {}
    stored_names: set[str] = set()
    loaded_names: dict[str, list[int]] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions[node.name] = node.lineno
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                stored_names.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                loaded_names.setdefault(node.id, []).append(node.lineno)

    unresolved = sorted(
        name
        for name in loaded_names
        if name.startswith("_oa_") and name not in definitions and name not in stored_names
    )
    if unresolved:
        errors.append("unresolved Open Architecture names: " + ", ".join(unresolved))

    missing_required = sorted(REQUIRED_CALLBACKS - set(definitions))
    if missing_required:
        errors.append("missing required callbacks: " + ", ".join(missing_required))

    callback_uses: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"click", "change", "submit", "select", "input", "load", "tick"}:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name) and first.id.startswith("_oa_"):
            callback_uses.append((first.id, node.lineno))

    late_callbacks = []
    for name, use_line in callback_uses:
        definition_line = definitions.get(name)
        if definition_line is None:
            late_callbacks.append(f"{name}:missing@{use_line}")
        elif definition_line >= use_line:
            late_callbacks.append(f"{name}:def@{definition_line} use@{use_line}")
    if late_callbacks:
        errors.append("callbacks unavailable at UI wiring: " + ", ".join(late_callbacks))

    # The explicit refresh callback must remain a thin, deterministic fresh probe.
    refresh_defs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_oa_refresh_provider_status_ui"
    ]
    if len(refresh_defs) != 1:
        errors.append(
            f"expected one _oa_refresh_provider_status_ui definition, found {len(refresh_defs)}"
        )
    else:
        calls = [
            node for node in ast.walk(refresh_defs[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_oa_provider_status_ui"
        ]
        if len(calls) != 1:
            errors.append("refresh callback must delegate exactly once to _oa_provider_status_ui")

    result = {
        "passed": not errors,
        "version": "v9.0.4-R4-F2",
        "webui_compile": "PASS",
        "unresolved_open_architecture_names": unresolved,
        "event_callbacks_checked": len(callback_uses),
        "callbacks_defined_before_ui_wiring": not late_callbacks,
        "delivery_mode_callback_defined": "_oa_delivery_mode_updates" in definitions,
        "provider_refresh_callback_defined": "_oa_refresh_provider_status_ui" in definitions,
        "startup_import_smoke_required_by_applicator": True,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
