#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


RUNTIME_APP = Path(__file__).resolve().parents[1]
PROJECT_ROOT = RUNTIME_APP.parents[1]
sys.path.insert(0, str(RUNTIME_APP))

VALIDATION_PREFIX = "ORT_GPU_VALIDATION_JSON "


NVIDIA_PACKAGES = (
    "nvidia-cublas-cu12==12.4.5.8",
    "nvidia-cudnn-cu12==9.1.0.70",
    "nvidia-cuda-runtime-cu12==12.4.127",
    "nvidia-cuda-nvrtc-cu12==12.4.127",
)


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _runtime_paths() -> dict[str, Path]:
    cfg = _load_json(RUNTIME_APP / "runtime_paths.json")
    runtime_root = Path(cfg.get("runtime_root") or (PROJECT_ROOT / "ORT_Runtime")).expanduser().resolve()
    gpu_root = runtime_root / "audio_gpu"
    gpu_python = gpu_root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return {
        "runtime_root": runtime_root,
        "gpu_root": gpu_root,
        "gpu_python": gpu_python,
        "model_root": runtime_root / "audio_cpu" / "models",
        "requirements": RUNTIME_APP / "requirements_audio_gpu.txt",
    }


def _run(args: list[str | Path], timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(item) for item in args],
        cwd=str(RUNTIME_APP),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _ensure_gpu_venv(paths: dict[str, Path]) -> None:
    if paths["gpu_python"].is_file():
        return
    paths["gpu_root"].mkdir(parents=True, exist_ok=True)
    result = _run([sys.executable, "-m", "venv", paths["gpu_root"] / ".venv"], timeout=600)
    if result.returncode != 0:
        raise RuntimeError("Gagal membuat runtime Audio GPU:\n" + result.stdout[-3000:])


def _site_packages(gpu_python: Path) -> Path:
    result = _run([gpu_python, "-c", "import site; print(site.getsitepackages()[0])"], timeout=60)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Tidak dapat menentukan site-packages GPU: " + result.stdout[-1000:])
    return Path(result.stdout.strip().splitlines()[-1]).resolve()


SITECUSTOMIZE = r'''# ORT v8.9.9 R2 CUDA DLL bootstrap
import os
import site
from pathlib import Path

_HANDLES = []
_candidates = []
for _root in [Path(p) for p in site.getsitepackages()]:
    _nvidia = _root / "nvidia"
    if not _nvidia.is_dir():
        continue
    for _component in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
        _base = _nvidia / _component
        _candidates.extend((_base / "bin", _base / "lib", _base / "lib" / "x64"))
_seen = set()
_dirs = []
for _path in _candidates:
    if _path.is_dir():
        _key = str(_path.resolve()).lower()
        if _key not in _seen:
            _seen.add(_key)
            _dirs.append(str(_path.resolve()))
_old = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
os.environ["PATH"] = os.pathsep.join(_dirs + [p for p in _old if p.lower() not in {d.lower() for d in _dirs}])
if os.name == "nt" and hasattr(os, "add_dll_directory"):
    for _directory in _dirs:
        try:
            _HANDLES.append(os.add_dll_directory(_directory))
        except Exception:
            pass
os.environ["ORT_AUDIO_CUDA_DLL_DIRS"] = os.pathsep.join(_dirs)
'''


def _write_sitecustomize(paths: dict[str, Path]) -> Path:
    target = _site_packages(paths["gpu_python"]) / "sitecustomize.py"
    existing = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    marker = "# ORT v8.9.9 R2 CUDA DLL bootstrap"
    if marker not in existing:
        content = existing.rstrip() + ("\n\n" if existing.strip() else "") + SITECUSTOMIZE.strip() + "\n"
        target.write_text(content, encoding="utf-8")
    return target


def _install_dependencies(paths: dict[str, Path]) -> None:
    python = paths["gpu_python"]
    result = _run([python, "-m", "pip", "install", "--upgrade", "pip", "wheel"], timeout=900)
    if result.returncode != 0:
        raise RuntimeError("Upgrade pip GPU gagal:\n" + result.stdout[-3000:])
    if paths["requirements"].is_file():
        result = _run([python, "-m", "pip", "install", "--upgrade-strategy", "only-if-needed", "-r", paths["requirements"]], timeout=3600)
        if result.returncode != 0:
            raise RuntimeError("Dependensi Faster-Whisper GPU gagal:\n" + result.stdout[-5000:])
    result = _run([python, "-m", "pip", "install", "--upgrade-strategy", "only-if-needed", *NVIDIA_PACKAGES], timeout=7200)
    if result.returncode != 0:
        raise RuntimeError("Paket CUDA/cuBLAS/cuDNN GPU gagal:\n" + result.stdout[-6000:])


def _model_location(model_root: Path, model_size: str) -> Path:
    for candidate in (model_root / f"faster-whisper-{model_size}", model_root / model_size):
        if candidate.is_dir() and (candidate / "model.bin").is_file():
            return candidate
    raise FileNotFoundError(f"Model faster-whisper-{model_size} belum tersedia di {model_root}.")


def _validate_gpu(model_root: Path, model_size: str = "small") -> dict[str, Any]:
    import numpy as np
    from app.audio.cuda_bootstrap import cuda_runtime_report

    report = cuda_runtime_report()
    if not report.get("passed"):
        raise RuntimeError("CUDA DLL/CTranslate2 belum siap: " + json.dumps(report, ensure_ascii=False))

    from faster_whisper import WhisperModel

    location = _model_location(model_root, model_size)
    started = time.perf_counter()
    model = WhisperModel(str(location), device="cuda", compute_type="int8_float16", cpu_threads=2, num_workers=1)
    load_ms = int((time.perf_counter() - started) * 1000)
    t = np.arange(16000, dtype=np.float32) / 16000.0
    audio = (0.006 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
    timings = []
    for _ in range(2):
        tick = time.perf_counter()
        segments, _info = model.transcribe(
            audio,
            language="en",
            task="transcribe",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=True,
        )
        list(segments)
        timings.append(int((time.perf_counter() - tick) * 1000))
    return {
        "ready": True,
        "model": model_size,
        "device": "cuda",
        "compute_type": "int8_float16",
        "model_path": str(location),
        "python": sys.executable,
        "load_ms": load_ms,
        "warmup_ms": timings[0],
        "steady_ms": timings[1],
        "cuda": report,
        "validated_at": time.time(),
        "detail": "real_gpu_inference_passed",
    }


def _write_marker(paths: dict[str, Path], result: dict[str, Any]) -> Path:
    marker = paths["gpu_root"] / f"validated_cuda_{result['model']}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def _validate_child(args: argparse.Namespace) -> int:
    try:
        payload = _validate_gpu(Path(args.model_root).resolve(), args.model_size)
        print(VALIDATION_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as exc:
        payload = {"ready": False, "error": str(exc), "python": sys.executable}
        print(VALIDATION_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-child", action="store_true")
    parser.add_argument("--model-root", default="")
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.validate_child:
        return _validate_child(args)

    paths = _runtime_paths()
    try:
        _ensure_gpu_venv(paths)
        if not args.check_only:
            _install_dependencies(paths)
        sitecustomize = _write_sitecustomize(paths)
        command = [
            paths["gpu_python"],
            Path(__file__).resolve(),
            "--validate-child",
            "--model-root", paths["model_root"],
            "--model-size", args.model_size,
        ]
        result = _run(command, timeout=900)
        payload: dict[str, Any] = {}
        for line in reversed(result.stdout.splitlines()):
            if line.startswith(VALIDATION_PREFIX):
                try:
                    payload = json.loads(line[len(VALIDATION_PREFIX):])
                except Exception:
                    payload = {}
                break
        if not payload:
            payload = {"ready": False, "error": result.stdout[-5000:]}
        if result.returncode != 0 or not payload.get("ready"):
            raise RuntimeError(str(payload.get("error") or result.stdout[-5000:]))
        marker = _write_marker(paths, payload)
        print(json.dumps({
            "passed": True,
            "gpu_python": str(paths["gpu_python"]),
            "sitecustomize": str(sitecustomize),
            "validation_marker": str(marker),
            "model": payload.get("model"),
            "load_ms": payload.get("load_ms"),
            "warmup_ms": payload.get("warmup_ms"),
            "steady_ms": payload.get("steady_ms"),
            "message": "GPU Audio siap. Tutup dan buka ulang WebUI sebelum pengujian.",
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        marker = paths["gpu_root"] / f"validated_cuda_{args.model_size}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "ready": False,
            "model": args.model_size,
            "device": "cuda",
            "compute_type": "int8_float16",
            "python": str(paths["gpu_python"]),
            "validated_at": time.time(),
            "detail": str(exc),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "passed": False,
            "error": str(exc),
            "gpu_python": str(paths["gpu_python"]),
            "recommendation": "Perbarui driver NVIDIA, lalu jalankan installer ini kembali. CPU Normal tetap dapat digunakan secara realtime.",
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
