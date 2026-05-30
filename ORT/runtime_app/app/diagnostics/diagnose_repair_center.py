from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return int(p.returncode), (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 999, str(exc)


def _runtime_python(base: Path) -> Path:
    cfg = base / "runtime_paths.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8-sig")) if cfg.exists() else {}
        root = Path(data.get("runtime_root") or base / "_runtime")
    except Exception:
        root = base / "_runtime"
    return root / ".venv" / "Scripts" / "python.exe"


def diagnose(base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    base = Path(base_dir or Path(__file__).resolve().parents[2]).resolve()
    py = _runtime_python(base)
    issues: List[Dict[str, str]] = []
    status: Dict[str, Any] = {
        "version": "v8.4",
        "timestamp": time.time(),
        "base_dir": str(base),
        "runtime_python": str(py),
        "runtime_python_exists": py.exists(),
        "python": platform.python_version(),
    }

    if not py.exists():
        issues.append({"severity": "CRITICAL", "problem": "Runtime Python tidak ditemukan", "cause": "Folder _runtime/.venv belum dibuat atau path runtime salah", "solution": "Jalankan Start_ORT_Translation.bat atau Repair Runtime Base."})
        status["issues"] = issues
        return status

    code = """
import json, importlib.util
out={}
mods=['torch','torchvision','torchaudio','easyocr','ctranslate2','sentencepiece']
for m in mods:
    try:
        mod=__import__(m)
        out[m]=getattr(mod,'__version__','OK')
    except Exception as e:
        out[m]='ERROR: '+repr(e)
try:
    import torch
    out['cuda_available']=bool(torch.cuda.is_available())
    out['cuda_device']=torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'
except Exception as e:
    out['cuda_available']='ERROR: '+repr(e)
print(json.dumps(out, ensure_ascii=False))
"""
    rc, out = _run([str(py), "-c", code], timeout=25)
    try:
        dep = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except Exception:
        dep = {"raw": out, "returncode": rc}
    status["dependency"] = dep

    for key in ["torch", "torchvision", "torchaudio", "easyocr"]:
        val = str(dep.get(key, "missing"))
        if val.startswith("ERROR") or val == "missing":
            issues.append({"severity": "CRITICAL", "problem": f"{key} bermasalah", "cause": val[:240], "solution": "Jalankan Repair_Torch_CUDA.bat untuk GPU/CUDA atau Repair_Torch_CPU.bat untuk CPU safe."})
    if dep.get("cuda_available") is not True:
        issues.append({"severity": "WARNING", "problem": "CUDA/GPU tidak aktif", "cause": str(dep.get("cuda_available")), "solution": "Jalankan Validate_Runtime_GPU.bat. Jika gagal, jalankan Repair_Torch_CUDA.bat."})

    ct2_dir = base / "models" / "ct2_opus_mt_en_id"
    status["ct2_model_dir"] = str(ct2_dir)
    status["ct2_model_exists"] = ct2_dir.exists()
    required_any = ["model.bin", "shared_vocabulary.json", "config.json", "source.spm", "target.spm"]
    missing = [x for x in required_any if not (ct2_dir / x).exists()]
    if not ct2_dir.exists() or missing:
        issues.append({"severity": "WARNING", "problem": "Model CT2 en-id belum lengkap", "cause": "Missing: " + ", ".join(missing), "solution": "Untuk Fast/Lite CT2, siapkan models/ct2_opus_mt_en_id atau jalankan Fast Engine Setup/Converter."})

    # Runtime status summaries.
    for name in ["runtime_health", "lite_gpu_guard", "fast_engine", "translation_engine", "benchmark_session"]:
        p = base / "status" / f"{name}.json"
        try:
            status[name] = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {"missing": True}
        except Exception as exc:
            status[name] = {"error": str(exc)}

    status["issues"] = issues
    return status


def diagnose_text(base_dir: str | os.PathLike[str] | None = None, export: bool = False) -> str:
    base = Path(base_dir or Path(__file__).resolve().parents[2]).resolve()
    data = diagnose(base)
    if export:
        report = base / "reports" / f"diagnostic_report_v8_4_{int(time.time())}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    issues = data.get("issues", []) or []
    lines = [
        "Diagnose & Repair Center v8.4",
        "===============================",
        f"runtime_python = {data.get('runtime_python')}",
        f"runtime_python_exists = {data.get('runtime_python_exists')}",
        "",
        "Dependency:",
    ]
    dep = data.get("dependency", {}) or {}
    for k in ["torch", "torchvision", "torchaudio", "easyocr", "ctranslate2", "sentencepiece", "cuda_available", "cuda_device"]:
        lines.append(f"- {k}: {dep.get(k, '-')}")
    lines += ["", "Masalah terdeteksi:"]
    if not issues:
        lines.append("- Tidak ada masalah kritis yang terdeteksi dari pemeriksaan cepat.")
    else:
        for i, item in enumerate(issues, 1):
            lines.append(f"{i}. [{item.get('severity')}] {item.get('problem')}")
            lines.append(f"   Penyebab: {item.get('cause')}")
            lines.append(f"   Solusi: {item.get('solution')}")
    lines += ["", "Status Lite/Fast:"]
    lg = data.get("lite_gpu_guard", {}) or {}
    fe = data.get("fast_engine", {}) or {}
    lines.append(f"- Lite GPU: {lg.get('profile', 'belum berjalan')} | {lg.get('reason', '-')}")
    lines.append(f"- Fast CT2: {fe.get('state', 'belum tersedia')} | active={fe.get('active', '-')}")
    if export:
        lines.append("")
        lines.append("Report JSON sudah diekspor ke folder reports/.")
    return "\n".join(lines)
