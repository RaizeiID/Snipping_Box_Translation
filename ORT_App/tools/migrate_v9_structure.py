from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class MigrationReport:
    project_root: str
    source_app: str
    target_app: str
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    moved: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    organized: list[str] = field(default_factory=list)
    junctions: list[str] = field(default_factory=list)
    removed_generated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def _clean_path_text(value: Path | str) -> str:
    # Windows command-line parsing can preserve a closing quote when a quoted
    # argument ends in a backslash, e.g. "C:\\ORT\\". Remove only wrapping
    # or orphan quote characters; a Windows filename cannot legally contain them.
    raw = os.path.expandvars(str(value or "")).strip().replace("\x00", "")
    while raw.startswith('"') or raw.endswith('"'):
        raw = raw.strip('"').strip()
    return raw


def _norm(path: Path | str) -> Path:
    raw = _clean_path_text(path)
    if not raw:
        return Path.cwd().resolve()
    return Path(raw).expanduser().resolve()


def _is_reparse(path: Path) -> bool:
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def _copy_or_replace(source: Path, target: Path, report: MigrationReport) -> None:
    if source.is_dir() and not source.is_symlink() and not _is_reparse(source):
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_or_replace(child, target / child.name, report)
        try:
            source.rmdir()
        except OSError:
            pass
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            source_stat = source.stat()
            target_stat = target.stat()
            replace = source_stat.st_mtime >= target_stat.st_mtime or source_stat.st_size != target_stat.st_size
        except OSError:
            replace = True
        if replace:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            shutil.move(str(source), str(target))
            report.merged.append(str(target))
        else:
            source.unlink(missing_ok=True)
    else:
        shutil.move(str(source), str(target))
        report.moved.append(str(target))


def _merge_directory(source: Path, target: Path, report: MigrationReport) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in list(source.iterdir()):
        _copy_or_replace(child, target / child.name, report)
    try:
        source.rmdir()
    except OSError:
        report.warnings.append(f"Folder sumber belum kosong dan dipertahankan: {source}")


def _safe_move(source: Path, target: Path, report: MigrationReport) -> None:
    if not source.exists() or source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.is_dir() and target.is_dir():
            _merge_directory(source, target, report)
            return
        if source.is_file() and target.is_file():
            try:
                if source.read_bytes() == target.read_bytes():
                    source.unlink()
                    report.merged.append(f"duplicate removed: {source}")
                    return
            except OSError:
                pass
            stamp = time.strftime("%Y%m%d_%H%M%S")
            alternate = target.with_name(f"{target.stem}_migrated_{stamp}{target.suffix}")
            shutil.move(str(source), str(alternate))
            report.warnings.append(f"Target sudah ada; file dipindahkan sebagai {alternate}")
            return
        alternate = target.with_name(target.name + "_migrated")
        shutil.move(str(source), str(alternate))
        report.warnings.append(f"Konflik tipe path; dipindahkan sebagai {alternate}")
        return
    shutil.move(str(source), str(target))
    report.moved.append(f"{source} -> {target}")


def _remove_generated(root: Path, report: MigrationReport) -> None:
    for directory in list(root.rglob("__pycache__")):
        if directory.is_dir() and not _is_reparse(directory):
            shutil.rmtree(directory, ignore_errors=True)
            report.removed_generated.append(str(directory))
    for pattern in ("*.pyc", "*.pyo"):
        for path in root.rglob(pattern):
            try:
                path.unlink()
                report.removed_generated.append(str(path))
            except OSError:
                pass


def _create_junction(link: Path, target: Path, report: MigrationReport) -> None:
    if os.name != "nt":
        # Linux/macOS test path: use a directory symlink.
        try:
            if link.exists() or link.is_symlink():
                return
            link.symlink_to(target, target_is_directory=True)
            report.junctions.append(f"{link} -> {target}")
        except OSError as exc:
            link.mkdir(parents=True, exist_ok=True)
            report.warnings.append(f"Tidak dapat membuat symlink {link}; memakai folder lokal kompatibilitas: {exc}")
        return
    if link.exists() or _is_reparse(link):
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    command = ["cmd", "/c", "mklink", "/J", str(link), str(target)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode == 0:
        report.junctions.append(f"{link} -> {target}")
    else:
        link.mkdir(parents=True, exist_ok=True)
        report.warnings.append(
            f"Junction gagal {link}; memakai folder lokal kompatibilitas. "
            f"Jalankan setup sebagai Administrator untuk pemisahan penuh. {(result.stdout or result.stderr).strip()}"
        )


def _organize_generated_dirs(app_root: Path, support_root: Path, report: MigrationReport) -> None:
    mapping = {
        "logs": support_root / "logs" / "runtime_app",
        "cache": support_root / "cache" / "runtime_app",
        "status": support_root / "status",
        "backups": support_root / "backups",
        "debug_bundles": support_root / "debug_bundles",
        "sessions": support_root / "logs" / "sessions",
    }
    for name, destination in mapping.items():
        source = app_root / name
        if source.exists() and not _is_reparse(source):
            _safe_move(source, destination, report)
        destination.mkdir(parents=True, exist_ok=True)
        _create_junction(source, destination, report)


def _move_runtime_payload(app_root: Path, project_root: Path, report: MigrationReport) -> None:
    runtime_root = project_root / "ORT_Runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    for name in ("_runtime", ".venv", "models", "model", "audio_spool"):
        source = app_root / name
        if not source.exists() or _is_reparse(source):
            continue
        if name == "_runtime":
            destination = runtime_root
        elif name == ".venv":
            destination = runtime_root / ".venv"
        else:
            destination = runtime_root / "legacy_payload" / name
        _safe_move(source, destination, report)


def _organize_root_files(project_root: Path, support_root: Path, report: MigrationReport) -> None:
    docs = support_root / "docs"
    maintenance = support_root / "maintenance"
    release = support_root / "release"
    packages = release / "packages"
    legacy_docs = docs / "legacy_apply_notes"
    legacy_tools = maintenance / "legacy_v8"
    legacy_release = release / "legacy_v8"
    for path in (docs, maintenance, release, packages, legacy_docs, legacy_tools, legacy_release):
        path.mkdir(parents=True, exist_ok=True)

    protected = {
        "START_HERE.bat", "Start WebUI.bat", "Start OCR.bat", "Runtime.bat",
        "ORT v9 Setup.bat", "VERSION.txt", ".gitignore", "LICENSE", "LICENSE.txt",
    }
    for item in list(project_root.iterdir()):
        if item.name in protected or item.is_dir():
            continue
        upper = item.name.upper()
        target: Path | None = None
        if item.name == "README.md":
            target = docs / "README.md"
        elif item.name == "CHANGELOG.md":
            target = docs / "CHANGELOG.md"
        elif upper.startswith(("README_APPLY_", "APPLY_NOTES_")):
            target = legacy_docs / item.name
        elif upper.startswith(("CHANGED_FILES_MANIFEST_", "SHA256SUMS_")):
            target = legacy_release / item.name
        elif upper.startswith(("VERIFY_ORT_V8", "CHECK_AUDIO_GPU_", "INSTALL_AUDIO_GPU_", "INSTALL_JAPANESE_", "SETUP_JAPANESE_")) and upper.endswith((".BAT", ".CMD")):
            target = legacy_tools / item.name
        elif upper.startswith("ORT_TRANSLATION_") and upper.endswith(".ZIP"):
            target = packages / item.name
        if target is not None:
            _safe_move(item, target, report)
            report.organized.append(f"{item.name} -> {target.relative_to(project_root)}")


def _update_runtime_config(app_root: Path, project_root: Path, report: MigrationReport) -> None:
    path = app_root / "runtime_paths.json"
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                data = {}
        except Exception as exc:
            report.warnings.append(f"runtime_paths.json lama tidak dapat dibaca: {exc}")
    current_runtime = str(data.get("runtime_root") or "").strip()
    old_local_fragments = ("\\ORT\\runtime_app\\_runtime", "/ORT/runtime_app/_runtime", "\\ORT_App\\_runtime", "/ORT_App/_runtime")
    if not current_runtime or any(fragment.lower() in current_runtime.lower() for fragment in old_local_fragments):
        current_runtime = str(project_root / "ORT_Runtime")
    runtime_python = Path(current_runtime) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    data.update({
        "layout_version": 9,
        "project_root": str(project_root),
        "app_root": str(app_root),
        "runtime_root": current_runtime,
        "runtime_python": str(runtime_python),
        "storage_mode": "surface_or_custom",
        "last_runtime_valid": runtime_python.exists(),
    })
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_layout(project_root: Path, app_root: Path, support_root: Path, report: MigrationReport) -> None:
    layout = {
        "schema": 9,
        "version": "v9.0.0",
        "project_root": str(project_root),
        "application_root": str(app_root),
        "runtime_root": str(project_root / "ORT_Runtime"),
        "support_root": str(support_root),
        "folders": {
            "docs": str(support_root / "docs"),
            "plugins": str(support_root / "plugins"),
            "logs": str(support_root / "logs"),
            "cache": str(support_root / "cache"),
            "status": str(support_root / "status"),
            "maintenance": str(support_root / "maintenance"),
            "exports": str(support_root / "exports"),
            "release": str(support_root / "release"),
        },
        "root_policy": "launchers_only",
        "compatibility": {"legacy_app_path": "ORT/runtime_app", "fallback_supported_by_root_launchers": True},
    }
    config = support_root / "config" / "project_layout.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate(project_root: Path) -> MigrationReport:
    project_root = _norm(project_root)
    legacy_app = project_root / "ORT" / "runtime_app"
    target_app = project_root / "ORT_App"
    source_app = legacy_app if legacy_app.exists() else target_app
    report = MigrationReport(str(project_root), str(source_app), str(target_app))
    support_root = project_root / "ORT"

    try:
        support_dirs = (
            "docs", "plugins", "logs", "cache", "status", "user_data", "maintenance",
            "exports", "release", "backups", "debug_bundles", "config",
        )
        for name in support_dirs:
            (support_root / name).mkdir(parents=True, exist_ok=True)
        (project_root / "ORT_Runtime").mkdir(parents=True, exist_ok=True)

        if legacy_app.exists() and not target_app.exists():
            shutil.move(str(legacy_app), str(target_app))
            report.moved.append(f"{legacy_app} -> {target_app}")
        elif legacy_app.exists() and target_app.exists():
            _merge_directory(legacy_app, target_app, report)
        if not target_app.exists():
            report.errors.append("Folder aplikasi tidak ditemukan pada ORT_App atau ORT/runtime_app.")
            return report

        _move_runtime_payload(target_app, project_root, report)
        _remove_generated(target_app, report)
        _organize_generated_dirs(target_app, support_root, report)
        _organize_root_files(project_root, support_root, report)
        _update_runtime_config(target_app, project_root, report)
        _write_layout(project_root, target_app, support_root, report)

        redirect = support_root / "RUNTIME_APP_MOVED_TO_ROOT.txt"
        redirect.write_text(
            "ORT/runtime_app telah dipindahkan ke folder surface ORT_App pada v9.0.0.\n"
            "Gunakan launcher root; jangan menyalin ORT_Runtime ketika membuat ZIP source.\n",
            encoding="utf-8",
        )
    except Exception as exc:
        report.errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        report.finished_at = time.time()
        stamp = time.strftime("%Y%m%d_%H%M%S")
        try:
            log_root = support_root / "logs" / "migration"
            log_root.mkdir(parents=True, exist_ok=True)
            report_path = log_root / f"v9_migration_{stamp}.json"
            report_path.write_text(
                json.dumps(asdict(report) | {"passed": report.passed}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as log_exc:
            report.warnings.append(f"Laporan migrasi tidak dapat ditulis: {type(log_exc).__name__}: {log_exc}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate ORT to the v9 clean project layout.")
    parser.add_argument("--project-root", default="", help="ORT project root")
    args = parser.parse_args()
    if args.project_root:
        root = _norm(args.project_root)
    else:
        here = Path(__file__).resolve()
        app = here.parents[1]
        root = app.parent.parent if app.name == "runtime_app" and app.parent.name == "ORT" else app.parent
    report = migrate(root)
    print(json.dumps(asdict(report) | {"passed": report.passed}, ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
