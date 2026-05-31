"""ORT Translation v8.3 Fast CT2 engine status, validation, and setup helper.

This module is intentionally defensive: it does not download model files by itself.
It detects CT2 dependencies, searches common model folders, creates a clear target
folder, writes a README, and exposes human-readable diagnostics for WebUI.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from status_manager import write_status
try:
    from app.runtime.ct2_path_resolver import candidate_ct2_dirs, validate_ct2_dir, resolve_ct2_model_dir
except Exception:
    candidate_ct2_dirs = validate_ct2_dir = resolve_ct2_model_dir = None

ROOT = Path(__file__).resolve().parent
REQUIRED_MARKERS = ("model.bin", "model.bin.index.json", "config.json", "shared_vocabulary.json", "source.spm", "target.spm")
MODEL_DIR_NAMES = ("ct2_opus_mt_en_id", "ct2_en_id", "opus_mt_en_id_ct2", "en-id-ct2")


def _bool_spec(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


class FastModelManager:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.default_model_dir = self.base_dir / "models" / "ct2_opus_mt_en_id"
        self.model_dir = self._select_model_dir()

    def _candidate_dirs(self) -> List[Path]:
        if candidate_ct2_dirs is not None:
            try:
                return candidate_ct2_dirs(self.base_dir)
            except Exception:
                pass
        candidates: List[Path] = []
        for env_key in ("ORT_CT2_EN_ID_DIR", "TITAN_CT2_EN_ID_DIR", "ORT_FAST_CT2_MODEL_DIR", "ORT_LITE_CT2_MODEL_DIR"):
            value = os.environ.get(env_key)
            if value:
                candidates.append(Path(value).expanduser())
        project_root = self.base_dir.parent.parent if self.base_dir.name.lower() == "runtime_app" and self.base_dir.parent.name.upper() == "ORT" else self.base_dir
        for parent in (self.base_dir / "models", project_root / "models", self.base_dir.parent / "_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD" / "models", self.base_dir / "_runtime" / "models", self.base_dir):
            for name in MODEL_DIR_NAMES:
                candidates.append(parent / name)
        candidates.append(self.default_model_dir)
        out: List[Path] = []
        seen = set()
        for p in candidates:
            try:
                r = str(p.resolve())
            except Exception:
                r = str(p)
            if r not in seen:
                seen.add(r)
                out.append(p)
        return out

    def _model_files_for(self, path: Path) -> List[str]:
        try:
            return sorted(p.name for p in path.iterdir() if p.is_file()) if path.exists() else []
        except Exception:
            return []

    def _validate_dir(self, path: Path) -> Dict[str, Any]:
        files = self._model_files_for(path)
        has_files = bool(files)
        markers = [m for m in REQUIRED_MARKERS if m in files]
        has_model = "model.bin" in files or "model.bin.index.json" in files
        has_spm = ("source.spm" in files and "target.spm" in files) or "shared_vocabulary.json" in files
        likely_valid = bool(has_files and has_model and has_spm)
        missing = []
        if not has_model:
            missing.append("model.bin atau model.bin.index.json")
        if not has_spm:
            missing.append("source.spm + target.spm atau shared_vocabulary.json")
        return {
            "path": str(path),
            "has_files": has_files,
            "files": files[:60],
            "markers": markers,
            "likely_valid": likely_valid,
            "missing": missing,
        }

    def _select_model_dir(self) -> Path:
        best = self.default_model_dir
        for p in self._candidate_dirs():
            v = self._validate_dir(p)
            if v["likely_valid"]:
                return p.resolve()
            if v["has_files"]:
                best = p
        return best.resolve()

    def validate_model_dir(self) -> Dict[str, Any]:
        return self._validate_dir(self.model_dir)

    def all_candidate_status(self) -> List[Dict[str, Any]]:
        return [self._validate_dir(p) for p in self._candidate_dirs()]

    def status(self) -> Dict[str, Any]:
        ctranslate2_ok = _bool_spec("ctranslate2")
        sentencepiece_ok = _bool_spec("sentencepiece")
        if resolve_ct2_model_dir is not None:
            try:
                resolved = resolve_ct2_model_dir(self.base_dir)
                self.model_dir = resolved.path
            except Exception:
                pass
        validation = self.validate_model_dir()
        active = bool(ctranslate2_ok and sentencepiece_ok and validation["likely_valid"])
        if active:
            state = "ACTIVE"
            reason = "CT2 dependencies and model files are ready."
        elif ctranslate2_ok and sentencepiece_ok and validation["has_files"]:
            state = "FALLBACK_ARGOS"
            reason = "CT2 dependencies exist, but the detected model folder is incomplete."
        elif ctranslate2_ok and sentencepiece_ok:
            state = "FALLBACK_ARGOS"
            reason = "CT2 dependencies exist, but no valid CT2 model folder was found."
        else:
            state = "NOT_INSTALLED"
            reason = "ctranslate2/sentencepiece missing; Fast uses Argos fallback."
        model_dir_used = str(self.model_dir)
        spm_dir_used = str(os.environ.get("TITAN_SPM_EN_ID_DIR") or self.model_dir)
        data = {
            "version": "v8.8.5",
            "state": state,
            "active": active,
            "python": sys.executable,
            "ctranslate2": ctranslate2_ok,
            "sentencepiece": sentencepiece_ok,
            "model_dir": str(self.model_dir),
            "model_dir_used": model_dir_used,
            "spm_dir_used": spm_dir_used,
            "path_conflict": model_dir_used.lower() != spm_dir_used.lower(),
            "model_validation": validation,
            "candidates": self.all_candidate_status()[:12],
            "reason": reason,
            "setup_hint": "Place a converted CTranslate2 EN->ID model in models/ct2_opus_mt_en_id or set TITAN_CT2_EN_ID_DIR.",
        }
        self.write_status(data)
        return data

    def write_status(self, data: Dict[str, Any]) -> None:
        try:
            write_status("fast_engine", data, self.base_dir)
        except Exception:
            pass

    def _readme_text(self) -> str:
        return """ORT Translation v8.3 - Fast CT2 Model Folder
================================================

Folder ini dipakai agar model Fast benar-benar memakai CTranslate2, bukan fallback Argos.

Isi minimal yang dibutuhkan:
- model.bin atau model.bin.index.json
- source.spm dan target.spm, atau shared_vocabulary.json jika model CT2 Anda memakai shared vocab
- config.json jika tersedia dari hasil convert

Target default:
models/ct2_opus_mt_en_id

Alternatif:
Set environment variable TITAN_CT2_EN_ID_DIR ke folder model CT2 EN->ID.

Catatan penting:
- File dependency ctranslate2 dan sentencepiece saja belum cukup.
- Jika model files belum ada, WebUI akan menampilkan FALLBACK_ARGOS.
- ORT tidak menyertakan model CT2 besar di patch kecil ini.
"""

    def ensure_model_folder(self) -> Dict[str, Any]:
        self.default_model_dir.mkdir(parents=True, exist_ok=True)
        try:
            readme = self.default_model_dir / "README_FAST_CT2_MODEL.txt"
            if not readme.exists():
                readme.write_text(self._readme_text(), encoding="utf-8")
        except Exception:
            pass
        data = self.status()
        data["folder_created"] = True
        self.write_status(data)
        return data

    def quick_translation_test(self, text: str = "Hello") -> Dict[str, Any]:
        data = self.status()
        result = {"version": "v8.8.5", "input": text, "state": data.get("state"), "active": data.get("active"), "ok": False, "output": "", "reason": data.get("reason", "")}
        if not data.get("active"):
            result["reason"] = "Fast CT2 is not active; runtime will use Argos fallback. Check model_dir and missing files."
            try:
                write_status("fast_setup", result, self.base_dir)
            except Exception:
                pass
            return result
        try:
            from fast_mt_core_ct2 import CT2Config, FastCT2Translator
            cfg = CT2Config(
                model_dir_en_id=str(self.model_dir),
                spm_dir_en_id=str(self.model_dir),
                beam_size=1,
                device=os.environ.get("TITAN_CT2_DEVICE", "cpu"),
                compute_type=os.environ.get("TITAN_CT2_COMPUTE_TYPE", "int8"),
            )
            tr = FastCT2Translator(cfg)
            out = (tr.translate(text) or "").strip()
            result.update({"ok": bool(out), "output": out, "reason": "Fast CT2 quick translation test completed."})
        except Exception as exc:
            result.update({"ok": False, "reason": f"{type(exc).__name__}: {exc}"})
        try:
            write_status("fast_setup", result, self.base_dir)
        except Exception:
            pass
        return result

    def quick_translation_report(self, text: str = "Hello") -> str:
        data = self.quick_translation_test(text)
        return "\n".join([
            "Fast Engine Quick Translation Test v8.8.5",
            "=====================================",
            f"state = {data.get('state')}",
            f"active = {data.get('active')}",
            f"ok = {data.get('ok')}",
            f"input = {data.get('input')}",
            f"output = {data.get('output') or '-'}",
            f"reason = {data.get('reason')}",
        ])

    def wizard_report(self) -> str:
        self.ensure_model_folder()
        data = self.status()
        val = data["model_validation"]
        lines = [
            "Fast Engine Setup Wizard v8.3",
            "===============================",
            f"State           : {data['state']}",
            f"Python          : {data['python']}",
            f"ctranslate2     : {data['ctranslate2']}",
            f"sentencepiece   : {data['sentencepiece']}",
            f"Model folder    : {data['model_dir']}",
            f"Model likely OK : {val['likely_valid']}",
            f"Detected markers: {', '.join(val['markers']) if val['markers'] else '-'}",
            f"Missing         : {', '.join(val['missing']) if val['missing'] else '-'}",
            f"Reason          : {data['reason']}",
            "",
            "Folder kandidat yang dicek:",
        ]
        for c in data.get("candidates", [])[:8]:
            mark = "OK" if c.get("likely_valid") else ("PARTIAL" if c.get("has_files") else "empty/missing")
            lines.append(f"- {mark}: {c.get('path')}")
        lines.append("")
        if not data["ctranslate2"] or not data["sentencepiece"]:
            lines.append("Solusi: install optional Fast dependency dari Runtime & Tools atau requirements_fast_optional.txt.")
        if not val["likely_valid"]:
            lines.append("Solusi: salin/convert model CTranslate2 EN->ID ke folder model di atas. Dependency saja belum cukup.")
        if data["active"]:
            lines.append("Fast CT2 sudah ACTIVE. Model Fast tidak lagi fallback Argos.")
        else:
            lines.append("Fast tetap aman berjalan dengan fallback Argos, tetapi performanya belum Fast asli sampai model CT2 valid.")
        return "\n".join(lines)


def fast_engine_status_text(base_dir: str | os.PathLike[str] | None = None) -> str:
    data = FastModelManager(base_dir).status()
    val = data["model_validation"]
    lines = [
        f"Fast Engine = {data['state']}",
        f"active = {data['active']}",
        f"ctranslate2 = {data['ctranslate2']}",
        f"sentencepiece = {data['sentencepiece']}",
        f"model_likely_valid = {val['likely_valid']}",
        f"model_dir = {data['model_dir']}",
        f"model_dir_used = {data.get('model_dir_used','-')}",
        f"spm_dir_used = {data.get('spm_dir_used','-')}",
        f"path_conflict = {data.get('path_conflict',False)}",
        f"missing = {', '.join(val['missing']) if val['missing'] else '-'}",
        f"reason = {data['reason']}",
        f"setup_hint = {data['setup_hint']}",
    ]
    if not data.get("active"):
        lines.append("WARNING: Model Fast akan fallback Argos. Performa belum Fast asli sampai model CT2 valid.")
    return "\n".join(lines)


def prepare_fast_engine_folder(base_dir: str | os.PathLike[str] | None = None) -> str:
    return FastModelManager(base_dir).wizard_report()


def fast_engine_test_text(base_dir: str | os.PathLike[str] | None = None) -> str:
    return FastModelManager(base_dir).quick_translation_report()
