from __future__ import annotations

import os
from pathlib import Path


def runtime_app_root() -> Path:
    """Return ORT_App or the legacy ORT/runtime_app directory."""
    return Path(__file__).resolve().parents[2]


def project_root() -> Path:
    app_root = runtime_app_root()
    # Legacy: <project>/ORT/runtime_app
    if app_root.name.lower() == "runtime_app" and app_root.parent.name.lower() == "ort":
        return app_root.parent.parent
    # v9: <project>/ORT_App
    return app_root.parent


def support_root() -> Path:
    return project_root() / "ORT"


def runtime_root() -> Path:
    override = os.environ.get("ORT_RUNTIME_ROOT", "").strip()
    return Path(override).expanduser().resolve() if override else project_root() / "ORT_Runtime"


def lab_data_root() -> Path:
    return support_root() / "user_data" / "open_architecture"


def lab_log_root() -> Path:
    return support_root() / "logs" / "open_architecture"


def export_root() -> Path:
    return support_root() / "exports"


def plugin_root() -> Path:
    return support_root() / "plugins"


def ensure_v9_roots() -> dict[str, Path]:
    roots = {
        "project": project_root(),
        "app": runtime_app_root(),
        "support": support_root(),
        "runtime": runtime_root(),
        "lab_data": lab_data_root(),
        "lab_logs": lab_log_root(),
        "exports": export_root(),
        "plugins": plugin_root(),
    }
    for key in ("support", "runtime", "lab_data", "lab_logs", "exports", "plugins"):
        roots[key].mkdir(parents=True, exist_ok=True)
    return roots
