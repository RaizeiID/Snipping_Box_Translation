from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from app.audio.model_store import inspect_local_model, model_problem_text
from app.audio.profiles import get_audio_profile
from app.audio.runtime_modes import ASRWorkerSpec, normalize_audio_mode, resolve_audio_plan


BASE_DIR = Path(__file__).resolve().parent
EVENT_PREFIX = "ORT_AUDIO_EVENT "
_PROBE_LOCK = threading.Lock()
_PROBE_CACHE: Dict[str, Dict[str, Any]] = {}
_SETUP_LOCK = threading.Lock()


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def audio_runtime_paths(base_dir: Path | str = BASE_DIR) -> Dict[str, Path]:
    base = Path(base_dir).resolve()
    cfg = _load_json(base / "runtime_paths.json")
    runtime_root = Path(cfg.get("runtime_root") or (base / "_runtime")).expanduser().resolve()
    default_python = _venv_python(runtime_root)
    ocr_python = Path(cfg.get("runtime_python") or default_python).expanduser().resolve()
    cpu_root = runtime_root / "audio_cpu"
    gpu_root = runtime_root / "audio_gpu"
    cpu_python = _venv_python(cpu_root)
    gpu_python = _venv_python(gpu_root)
    return {
        "base_dir": base,
        "runtime_root": runtime_root,
        "ocr_python": ocr_python,
        "cpu_root": cpu_root,
        "cpu_python": cpu_python,
        "gpu_root": gpu_root,
        "gpu_python": gpu_python,
        "model_root": cpu_root / "models",
        "spool_root": runtime_root / "audio_spool",
        "cpu_requirements": base / "requirements_audio_cpu.txt",
        "gpu_requirements": base / "requirements_audio_gpu.txt",
        "sidecar": base / "audio_asr_sidecar.py",
        "capture_sidecar": base / "audio_capture_sidecar.py",
        "audio_root": cpu_root,
        "audio_python": cpu_python,
        "requirements": base / "requirements_audio_cpu.txt",
    }


def parse_sidecar_events(text: str) -> list[dict]:
    events = []
    for line in str(text or "").splitlines():
        if not line.startswith(EVENT_PREFIX):
            continue
        try:
            event = json.loads(line[len(EVENT_PREFIX):])
            if isinstance(event, dict):
                events.append(event)
        except Exception:
            continue
    return events


def _run(args: Iterable[str | Path], timeout: float = 60.0, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(item) for item in args],
        cwd=str(cwd or BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )


def _probe_python(python_path: Path, device: str, paths: dict) -> dict:
    if not python_path.exists():
        return {
            "ready": False,
            "installed": False,
            "requested_device": device,
            "file_test": False,
            "live_loopback": False,
            "python": str(python_path),
            "message": "Runtime belum dipasang.",
        }
    try:
        result = _run(
            [python_path, paths["sidecar"], "--probe-json", "--asr-device", device],
            timeout=40.0,
            cwd=paths["base_dir"],
        )
        events = parse_sidecar_events(result.stdout)
        probe = next((item for item in reversed(events) if item.get("type") == "probe"), {})
        ready = bool(probe.get("ready")) and result.returncode == 0
        value = {
            **probe,
            "installed": True,
            "ready": ready,
            "returncode": result.returncode,
            "python": str(python_path),
            "message": "Runtime siap." if ready else "Dependensi atau perangkat runtime belum siap.",
        }
        if result.returncode != 0 and not probe:
            value["errors"] = [result.stdout[-1600:]]
        return value
    except Exception as exc:
        return {
            "ready": False,
            "installed": True,
            "requested_device": device,
            "file_test": False,
            "live_loopback": False,
            "python": str(python_path),
            "message": f"Probe Audio gagal: {exc}",
            "errors": [str(exc)],
        }


def _probe_cache_key(base_dir: Path | str, mode: str) -> str:
    return f"{Path(base_dir).resolve()}::{normalize_audio_mode(mode)}"


def probe_audio_runtime(force: bool = False, base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> dict:
    requested = normalize_audio_mode(mode)
    key = _probe_cache_key(base_dir, requested)
    now = time.monotonic()
    with _PROBE_LOCK:
        cached = _PROBE_CACHE.get(key)
        if not force and cached and now - float(cached.get("cached_at", 0.0)) < 8.0:
            return dict(cached["value"])
    paths = audio_runtime_paths(base_dir)
    cpu = _probe_python(paths["cpu_python"], "cpu", paths)
    gpu = _probe_python(paths["gpu_python"], "cuda", paths) if requested in {"gpu", "hybrid"} else {
        "ready": False,
        "installed": paths["gpu_python"].exists(),
        "requested_device": "cuda",
        "python": str(paths["gpu_python"]),
        "message": "CUDA tidak diperiksa pada mode CPU.",
    }
    if requested == "cpu":
        ready = bool(cpu.get("ready"))
        effective = "cpu"
        capture = paths["cpu_python"]
        reason = "CPU_RUNTIME_READY" if ready else "CPU_RUNTIME_NOT_READY"
    elif requested == "gpu":
        ready = bool(gpu.get("ready"))
        effective = "gpu"
        capture = paths["gpu_python"]
        reason = "GPU_RUNTIME_READY" if ready else "GPU_RUNTIME_NOT_READY"
    else:
        ready = bool(cpu.get("ready"))
        effective = "hybrid" if gpu.get("ready") and ready else "cpu_guard"
        capture = paths["cpu_python"] if cpu.get("ready") else paths["gpu_python"]
        reason = "HYBRID_RUNTIME_READY" if effective == "hybrid" else "GPU_RUNTIME_NOT_READY"
    value = {
        "requested_mode": requested,
        "effective_mode": effective,
        "ready": ready,
        "cpu": cpu,
        "gpu": gpu,
        "capture_python": str(capture),
        "file_test": bool((cpu if requested != "gpu" else gpu).get("file_test")),
        "live_loopback": bool((cpu if requested != "gpu" else gpu).get("live_loopback")),
        "reason": reason,
        "message": (
            "Runtime Audio siap."
            if ready and effective != "cpu_guard"
            else "Hybrid siap melalui CPU Guard; GPU belum tersedia."
            if ready
            else "Runtime Audio belum siap."
        ),
    }
    with _PROBE_LOCK:
        _PROBE_CACHE[key] = {"cached_at": now, "value": dict(value)}
    return value


def _clear_probe_cache() -> None:
    with _PROBE_LOCK:
        _PROBE_CACHE.clear()


def _gpu_validation_path(paths: dict, spec: ASRWorkerSpec) -> Path:
    safe_model = "".join(character for character in spec.model_size if character.isalnum() or character in {"-", "_"})
    return paths["gpu_root"] / f"validated_cuda_{safe_model}.json"


def _record_gpu_validation(paths: dict, spec: ASRWorkerSpec, ready: bool, detail: str = "") -> None:
    path = _gpu_validation_path(paths, spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ready": bool(ready),
        "model": spec.model_size,
        "device": spec.device,
        "compute_type": spec.compute_type,
        "python": str(paths["gpu_python"]),
        "validated_at": time.time(),
        "detail": str(detail or "")[-1200:],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _gpu_model_validated(paths: dict, spec: ASRWorkerSpec) -> bool:
    data = _load_json(_gpu_validation_path(paths, spec))
    return bool(
        data.get("ready")
        and data.get("model") == spec.model_size
        and data.get("device") == "cuda"
        and data.get("compute_type") == spec.compute_type
        and data.get("python") == str(paths["gpu_python"])
    )


def audio_runtime_available(base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> bool:
    return bool(probe_audio_runtime(base_dir=base_dir, mode=mode).get("ready"))


def audio_model_status(profile_key: str = "normal", base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> dict:
    paths = audio_runtime_paths(base_dir)
    plan = resolve_audio_plan(mode, profile_key)
    primary = inspect_local_model(paths["model_root"], plan.primary.model_size)
    fallback = inspect_local_model(paths["model_root"], plan.fallback.model_size) if plan.fallback else None
    if plan.requested_mode == "hybrid":
        ready = bool(fallback and fallback.ready)
        fully_ready = bool(primary.ready and fallback and fallback.ready)
    else:
        ready = primary.ready
        fully_ready = primary.ready
    return {
        "requested_mode": plan.requested_mode,
        "profile": plan.profile_key,
        "ready": ready,
        "fully_ready": fully_ready,
        "primary_ready": primary.ready,
        "fallback_ready": bool(fallback and fallback.ready),
        "primary": primary.as_dict(),
        "fallback": fallback.as_dict() if fallback else None,
        "required_models": list(plan.required_model_sizes),
        "model": primary.model,
        "path": primary.path,
        "missing_files": list(primary.missing_files),
        "invalid_files": list(primary.invalid_files),
    }


def audio_model_ready(profile_key: str = "normal", base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> bool:
    return bool(audio_model_status(profile_key, base_dir, mode).get("ready"))


def resolve_effective_audio_mode(mode: str, profile_key: str, base_dir: Path | str = BASE_DIR, force: bool = False) -> dict:
    requested = normalize_audio_mode(mode)
    plan = resolve_audio_plan(requested, profile_key)
    runtime = probe_audio_runtime(force=force, base_dir=base_dir, mode=requested)
    models = audio_model_status(profile_key, base_dir, requested)
    gpu_probe = runtime.get("gpu") or {}
    free_vram = int(gpu_probe.get("vram_free_mb", 0) or 0)
    reserve = int(plan.primary.minimum_free_vram_mb or 0)
    reserve_met = not free_vram or free_vram >= reserve
    gpu_model_validated = _gpu_model_validated(audio_runtime_paths(base_dir), plan.primary) if requested in {"gpu", "hybrid"} else False
    if requested == "cpu":
        ready = bool(runtime.get("ready") and models.get("primary_ready"))
        effective = "cpu"
        reason = "CPU_READY" if ready else "CPU_RUNTIME_OR_MODEL_NOT_READY"
    elif requested == "gpu":
        ready = bool(runtime.get("ready") and models.get("primary_ready") and reserve_met and gpu_model_validated)
        effective = "gpu"
        reason = "GPU_READY" if ready else "VRAM_RESERVE_NOT_MET" if not reserve_met else "GPU_MODEL_NOT_VALIDATED" if not gpu_model_validated else "GPU_RUNTIME_OR_MODEL_NOT_READY"
    else:
        fallback_ready = bool((runtime.get("cpu") or {}).get("ready") and models.get("fallback_ready"))
        gpu_ready = bool((runtime.get("gpu") or {}).get("ready") and models.get("primary_ready") and reserve_met and gpu_model_validated)
        ready = fallback_ready
        effective = "hybrid" if gpu_ready and fallback_ready else "cpu_guard"
        reason = "HYBRID_READY" if effective == "hybrid" else "VRAM_RESERVE_NOT_MET" if not reserve_met else "GPU_MODEL_NOT_VALIDATED" if not gpu_model_validated else "GPU_RUNTIME_OR_MODEL_NOT_READY"
    return {
        "ready": ready,
        "requested_mode": requested,
        "effective_mode": effective,
        "reason": reason,
        "plan": plan.as_dict(),
        "runtime": runtime,
        "models": models,
        "free_vram_mb": free_vram,
        "minimum_free_vram_mb": reserve,
        "vram_reserve_met": reserve_met,
        "gpu_model_validated": gpu_model_validated,
    }


def audio_runtime_summary_text(profile_key: str = "normal", base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> str:
    paths = audio_runtime_paths(base_dir)
    resolution = resolve_effective_audio_mode(mode, profile_key, base_dir)
    plan = resolve_audio_plan(mode, profile_key)
    primary = resolution["models"]["primary"]
    fallback = resolution["models"].get("fallback")
    lines = [
        f"status = {'READY' if resolution['ready'] else 'SETUP_REQUIRED'}",
        f"requested_mode = {resolution['requested_mode']}",
        f"effective_mode = {resolution['effective_mode']}",
        f"reason = {resolution['reason']}",
        f"profile = {get_audio_profile(profile_key).label}",
        f"primary_asr = {plan.primary.model_size}:{plan.primary.device}:{plan.primary.compute_type}",
        f"primary_model_ready = {bool(primary.get('ready'))}",
        f"cpu_runtime = {paths['cpu_python']}",
        f"gpu_runtime = {paths['gpu_python']}",
        f"shared_model_root = {paths['model_root']}",
        f"file_test = {bool(resolution['runtime'].get('file_test'))}",
        f"wasapi_loopback = {bool(resolution['runtime'].get('live_loopback'))}",
    ]
    if plan.fallback:
        lines.append(f"fallback_asr = {plan.fallback.model_size}:{plan.fallback.device}:{plan.fallback.compute_type}")
        lines.append(f"fallback_model_ready = {bool(fallback and fallback.get('ready'))}")
    if resolution.get("free_vram_mb"):
        lines.append(f"vram_free_mb = {resolution['free_vram_mb']}")
        lines.append(f"vram_reserve_mb = {resolution['minimum_free_vram_mb']}")
    if plan.requested_mode in {"gpu", "hybrid"}:
        lines.append(f"gpu_model_validated = {bool(resolution.get('gpu_model_validated'))}")
    for label, state in (("primary", primary), ("fallback", fallback)):
        if state and not state.get("ready"):
            problem = []
            if state.get("missing_files"):
                problem.append("missing=" + ",".join(state["missing_files"]))
            if state.get("invalid_files"):
                problem.append("invalid=" + ",".join(state["invalid_files"]))
            if problem:
                lines.append(f"{label}_model_problem = " + " | ".join(problem))
    return "\n".join(lines)


def audio_device_choices(base_dir: Path | str = BASE_DIR, force: bool = False, mode: str = "cpu") -> Tuple[list[tuple[str, str]], str, str]:
    probe = probe_audio_runtime(force=force, base_dir=base_dir, mode=mode)
    if not probe.get("ready"):
        return [("Default output · siapkan Audio dahulu", "-1")], "-1", str(probe.get("message") or "Runtime Audio belum siap.")
    if not probe.get("live_loopback"):
        return [("WASAPI hanya tersedia di Windows", "-1")], "-1", "Uji file audio tersedia; loopback langsung memerlukan Windows."
    paths = audio_runtime_paths(base_dir)
    python_path = Path(str(probe.get("capture_python") or ""))
    try:
        result = _run([python_path, paths["sidecar"], "--list-devices-json"], timeout=35.0, cwd=paths["base_dir"])
        events = parse_sidecar_events(result.stdout)
        payload = next((item for item in reversed(events) if item.get("type") == "devices"), {})
        devices = payload.get("devices") or []
        choices: list[tuple[str, str]] = []
        selected = "-1"
        for item in devices:
            index = str(int(item.get("index", -1)))
            label = str(item.get("name") or f"WASAPI Loopback {index}")
            if item.get("is_default"):
                label = "Default · " + label
                selected = index
            choices.append((label, index))
        if not choices:
            return [("Default output (deteksi otomatis)", "-1")], "-1", "Perangkat spesifik belum terdeteksi; ORT akan mencoba output default."
        if selected == "-1":
            selected = choices[0][1]
        return choices, selected, f"{len(choices)} perangkat WASAPI loopback ditemukan."
    except Exception as exc:
        return [("Default output (deteksi otomatis)", "-1")], "-1", f"Deteksi perangkat gagal: {exc}"


def _ensure_runtime(kind: str, paths: dict, steps: list[str]) -> tuple[bool, str]:
    root = paths[f"{kind}_root"]
    python_path = paths[f"{kind}_python"]
    requirements = paths[f"{kind}_requirements"]
    if not requirements.is_file() or not paths["sidecar"].is_file() or not paths["capture_sidecar"].is_file():
        return False, "File paket Audio tidak lengkap. Terapkan ulang patch sebelum setup."
    root.mkdir(parents=True, exist_ok=True)
    if not python_path.exists():
        result = _run([paths["ocr_python"], "-m", "venv", root / ".venv"], timeout=300.0, cwd=paths["base_dir"])
        steps.append(f"create_{kind}_venv={result.returncode}")
        if result.returncode != 0:
            return False, result.stdout[-3000:]
    base_probe = _probe_python(python_path, "cpu", paths)
    if base_probe.get("ready"):
        steps.append(f"{kind}_dependencies=already_ready")
    else:
        result = _run(
            [python_path, "-m", "pip", "install", "--disable-pip-version-check", "-r", requirements],
            timeout=1200.0,
            cwd=paths["base_dir"],
        )
        steps.append(f"install_{kind}_dependencies={result.returncode}")
        if result.returncode != 0:
            return False, result.stdout[-5000:]
    return True, ""


def _prepare_model(python_path: Path, paths: dict, profile_key: str, spec: ASRWorkerSpec, *, download_only: bool = False) -> tuple[bool, str]:
    command: list[str | Path] = [
        python_path,
        paths["sidecar"],
        "--prepare-model",
        "--profile",
        profile_key,
        "--model-size",
        spec.model_size,
        "--asr-device",
        spec.device,
        "--compute-type",
        spec.compute_type,
        "--model-root",
        paths["model_root"],
        "--retry-count",
        "3",
    ]
    if download_only:
        command.append("--download-only")
    result = _run(command, timeout=2400.0, cwd=paths["base_dir"])
    if result.returncode == 0:
        return True, result.stdout[-1200:]
    events = parse_sidecar_events(result.stdout)
    final_error = next((item for item in reversed(events) if item.get("type") == "error"), {})
    return False, str(final_error.get("message") or result.stdout[-2400:]).strip()


def _setup_audio_runtime_locked(profile_key: str = "normal", base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> str:
    paths = audio_runtime_paths(base_dir)
    requested = normalize_audio_mode(mode)
    plan = resolve_audio_plan(requested, profile_key)
    if not paths["ocr_python"].exists():
        return "GAGAL: Runtime Python utama ORT tidak ditemukan. Jalankan/repair Runtime ORT terlebih dahulu."
    steps: list[str] = []
    try:
        if requested in {"cpu", "hybrid"}:
            ok, detail = _ensure_runtime("cpu", paths, steps)
            if not ok:
                return "GAGAL menyiapkan runtime Audio CPU:\n" + detail
        if requested in {"gpu", "hybrid"}:
            ok, detail = _ensure_runtime("gpu", paths, steps)
            if not ok:
                if requested == "gpu":
                    return "GAGAL menyiapkan runtime Audio GPU:\n" + detail
                steps.append("gpu_runtime=unavailable")

        if requested == "cpu":
            ok, detail = _prepare_model(paths["cpu_python"], paths, plan.profile_key, plan.primary)
            steps.append(f"prepare_{plan.primary.model_size}_cpu={int(ok)}")
            if not ok:
                return f"Model ASR {plan.primary.model_size} belum siap. Tidak ada cache yang dihapus.\nDetail: {detail}"
        elif requested == "gpu":
            gpu_probe = _probe_python(paths["gpu_python"], "cuda", paths)
            if not gpu_probe.get("ready"):
                return (
                    "GAGAL: Runtime GPU belum dapat memuat CUDA ASR. GPU mode tidak dialihkan diam-diam ke CPU.\n"
                    + " | ".join(str(item) for item in (gpu_probe.get("errors") or [gpu_probe.get("message")]))
                )
            ok, detail = _prepare_model(paths["gpu_python"], paths, plan.profile_key, plan.primary)
            steps.append(f"prepare_{plan.primary.model_size}_gpu={int(ok)}")
            _record_gpu_validation(paths, plan.primary, ok, detail)
            if not ok:
                return f"Model ASR GPU {plan.primary.model_size} belum siap.\nDetail: {detail}"
        else:
            assert plan.fallback is not None
            ok, detail = _prepare_model(paths["cpu_python"], paths, plan.profile_key, plan.fallback)
            steps.append(f"prepare_{plan.fallback.model_size}_cpu_fallback={int(ok)}")
            if not ok:
                return f"GAGAL: CPU fallback Hybrid belum siap.\nDetail: {detail}"
            gpu_probe = _probe_python(paths["gpu_python"], "cuda", paths)
            if gpu_probe.get("ready"):
                ok, detail = _prepare_model(paths["gpu_python"], paths, plan.profile_key, plan.primary)
                steps.append(f"prepare_{plan.primary.model_size}_gpu={int(ok)}")
                _record_gpu_validation(paths, plan.primary, ok, detail)
                if not ok:
                    download_ok, download_detail = _prepare_model(paths["cpu_python"], paths, plan.profile_key, plan.primary, download_only=True)
                    steps.append(f"cache_{plan.primary.model_size}_for_gpu={int(download_ok)}")
                    detail = detail or download_detail
            else:
                _record_gpu_validation(paths, plan.primary, False, "CUDA probe belum siap; Hybrid memakai CPU Guard.")
                ok, detail = _prepare_model(paths["cpu_python"], paths, plan.profile_key, plan.primary, download_only=True)
                steps.append(f"cache_{plan.primary.model_size}_for_gpu={int(ok)}")
                steps.append("gpu_validation=cpu_guard")

        _clear_probe_cache()
        resolution = resolve_effective_audio_mode(requested, plan.profile_key, base_dir, force=True)
        marker_root = paths["cpu_root"] if requested != "gpu" else paths["gpu_root"]
        marker = marker_root / f"prepared_{requested}_{plan.profile_key}.json"
        marker.write_text(json.dumps({
            "requested_mode": requested,
            "effective_mode": resolution["effective_mode"],
            "profile": plan.profile_key,
            "primary": plan.primary.as_dict(),
            "fallback": plan.fallback.as_dict() if plan.fallback else None,
            "prepared_at": time.time(),
            "model_root": str(paths["model_root"]),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if not resolution.get("ready"):
            return "Setup selesai sebagian, tetapi pemeriksaan akhir belum lulus:\n" + audio_runtime_summary_text(plan.profile_key, base_dir, requested)
        return "\n".join([
            f"Audio {requested.upper()} siap.",
            f"requested_mode = {requested}",
            f"effective_mode = {resolution['effective_mode']}",
            f"primary_asr = {plan.primary.model_size}:{plan.primary.device}:{plan.primary.compute_type}",
            f"fallback_asr = {plan.fallback.model_size}:cpu:int8" if plan.fallback else "fallback_asr = disabled",
            f"steps = {' | '.join(steps)}",
            "Model dan cache R6 yang sudah ada tetap dipertahankan.",
        ])
    except subprocess.TimeoutExpired:
        return "GAGAL: Setup Audio melewati batas waktu. Periksa koneksi internet lalu jalankan setup sekali lagi."
    except Exception as exc:
        return f"GAGAL setup Audio {requested.upper()}: {type(exc).__name__}: {exc}"


def setup_audio_runtime(profile_key: str = "normal", base_dir: Path | str = BASE_DIR, mode: str = "cpu") -> str:
    if not _SETUP_LOCK.acquire(blocking=False):
        return "Setup Audio sedang berjalan. Tunggu proses aktif selesai; jangan menjalankan dua unduhan model bersamaan."
    try:
        return _setup_audio_runtime_locked(profile_key, base_dir, mode)
    finally:
        _SETUP_LOCK.release()
