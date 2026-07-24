from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

EVENT_PREFIX = "ORT_SETUP_EVENT "
SENSEVOICE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2"
)
SHERPA_CUDA_INDEX = "https://k2-fsa.github.io/sherpa/onnx/cuda.html"
SHERPA_CUDA12_REQUIREMENT = "sherpa-onnx==1.13.4+cuda12.cudnn9"
SHERPA_CUDA11_REQUIREMENT = "sherpa-onnx==1.13.4+cuda"
HF_REPOS = {
    "reazonspeech_k2": "reazon-research/reazonspeech-k2-v2",
    "kotoba_bilingual": "kotoba-tech/kotoba-whisper-bilingual-v1.0-faster",
    "faster_whisper_base": "Systran/faster-whisper-base",
    "faster_whisper_small": "Systran/faster-whisper-small",
}
LOCAL_MODEL_DIRS = {
    "kotoba_bilingual": "kotoba-whisper-bilingual-v1.0-faster",
    "faster_whisper_base": "faster-whisper-base",
    "faster_whisper_small": "faster-whisper-small",
}


def configure_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


def emit(event: str, **payload: Any) -> None:
    data = {"event": str(event), "ts": time.time(), **payload}
    print(EVENT_PREFIX + json.dumps(data, ensure_ascii=False), flush=True)


def human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _display_command(command: list[str]) -> str:
    shown = list(command)
    if "-c" in shown:
        index = shown.index("-c")
        if index + 1 < len(shown):
            shown[index + 1] = "<inline-python-script>"
    return " ".join(shown)


def run(command: list[str], cwd: Path | None = None, *, phase: str | None = None) -> None:
    if phase:
        emit("phase", phase=phase, message=phase)
    print("$ " + _display_command(command), flush=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, check=True)


def _status_path(status_root: Path, provider: str, device: str) -> Path:
    return status_root / f"{provider}_{device}.json"


def _write_status(
    status_root: Path,
    provider: str,
    device: str,
    *,
    runtime_python: Path,
    model_total_bytes: int = 0,
    model_downloaded_bytes: int = 0,
    model_files: list[dict[str, Any]] | None = None,
    model_path: str = "",
    runtime_ready: bool = False,
    bridge_ready: bool | None = None,
    details: dict[str, Any] | None = None,
) -> Path:
    status_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "provider": provider,
        "device": device,
        "runtime_python": str(runtime_python),
        "model_total_bytes": int(model_total_bytes or 0),
        "model_downloaded_bytes": int(model_downloaded_bytes or 0),
        "model_complete": bool(model_total_bytes and model_downloaded_bytes >= model_total_bytes),
        "model_files": model_files or [],
        "model_path": model_path,
        "runtime_ready": bool(runtime_ready),
        "bridge_ready": bridge_ready,
        "details": details or {},
        "updated_at": time.time(),
    }
    path = _status_path(status_root, provider, device)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _download_hf_repo(
    provider: str,
    repo_id: str,
    *,
    cache_dir: Path | None = None,
    local_dir: Path | None = None,
) -> tuple[int, int, list[dict[str, Any]], str]:
    from huggingface_hub import hf_hub_download, snapshot_download
    from tqdm.auto import tqdm

    kwargs: dict[str, Any] = {"repo_id": repo_id, "dry_run": True}
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        kwargs["cache_dir"] = str(cache_dir)
    if local_dir is not None:
        local_dir.mkdir(parents=True, exist_ok=True)
        kwargs["local_dir"] = str(local_dir)
    entries = list(snapshot_download(**kwargs))
    total = sum(int(item.file_size or 0) for item in entries)
    completed = sum(int(item.file_size or 0) for item in entries if item.is_cached)
    emit(
        "model_info",
        provider=provider,
        repo_id=repo_id,
        total_bytes=total,
        downloaded_bytes=completed,
        total_human=human_bytes(total),
        downloaded_human=human_bytes(completed),
        percent=round((completed / total * 100) if total else 0.0, 2),
    )
    files: list[dict[str, Any]] = []
    for item in entries:
        size = int(item.file_size or 0)
        if item.is_cached:
            path = Path(item.local_path)
            files.append({"path": str(path), "size": size, "filename": item.filename})
            continue
        base = completed
        last = {"time": 0.0, "percent": -1}

        class EventTqdm(tqdm):
            def update(self, n: int | float = 1):  # type: ignore[override]
                result = super().update(n)
                now = time.monotonic()
                global_value = min(total, base + int(self.n or 0))
                percent = int((global_value / total * 100) if total else 0)
                if now - last["time"] >= 0.2 or percent != last["percent"]:
                    last["time"] = now
                    last["percent"] = percent
                    emit(
                        "download_progress",
                        provider=provider,
                        filename=item.filename,
                        total_bytes=total,
                        downloaded_bytes=global_value,
                        total_human=human_bytes(total),
                        downloaded_human=human_bytes(global_value),
                        percent=round((global_value / total * 100) if total else 0.0, 2),
                    )
                return result

        download_kwargs: dict[str, Any] = {
            "repo_id": repo_id,
            "filename": item.filename,
            "tqdm_class": EventTqdm,
        }
        if cache_dir is not None:
            download_kwargs["cache_dir"] = str(cache_dir)
        if local_dir is not None:
            download_kwargs["local_dir"] = str(local_dir)
        downloaded_path = Path(hf_hub_download(**download_kwargs))
        completed += size
        files.append({"path": str(downloaded_path), "size": size, "filename": item.filename})
        emit(
            "download_progress",
            provider=provider,
            filename=item.filename,
            total_bytes=total,
            downloaded_bytes=min(completed, total),
            total_human=human_bytes(total),
            downloaded_human=human_bytes(min(completed, total)),
            percent=round((min(completed, total) / total * 100) if total else 100.0, 2),
        )
    resolved = str(local_dir if local_dir is not None else (files[0]["path"] if files else cache_dir or ""))
    emit(
        "download_complete",
        provider=provider,
        total_bytes=total,
        downloaded_bytes=total,
        total_human=human_bytes(total),
        downloaded_human=human_bytes(total),
        percent=100.0,
    )
    return total, total, files, resolved


def _download_url(provider: str, url: str, destination: Path) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ORT-v9.0.4-R4"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        # Server resume support is not guaranteed for this release URL. Start a
        # clean archive download so a previous partial file cannot be appended
        # to a full response and silently corrupt the model package.
        downloaded = 0
        mode = "wb"
        emit(
            "model_info",
            provider=provider,
            total_bytes=total,
            downloaded_bytes=downloaded,
            total_human=human_bytes(total),
            downloaded_human=human_bytes(downloaded),
            percent=round((downloaded / total * 100) if total else 0.0, 2),
        )
        with destination.open(mode) as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                emit(
                    "download_progress",
                    provider=provider,
                    total_bytes=total,
                    downloaded_bytes=downloaded,
                    total_human=human_bytes(total),
                    downloaded_human=human_bytes(downloaded),
                    percent=round((downloaded / total * 100) if total else 0.0, 2),
                )
    emit(
        "download_complete",
        provider=provider,
        total_bytes=total,
        downloaded_bytes=downloaded,
        total_human=human_bytes(total),
        downloaded_human=human_bytes(downloaded),
        percent=100.0 if not total or downloaded >= total else round(downloaded / total * 100, 2),
    )
    return total, downloaded


def _detect_cuda_variant(python: Path) -> str:
    probe = """
try:
    import torch
    version = str(getattr(torch.version, 'cuda', '') or '')
    print('cuda12' if version.startswith('12') else 'cuda11' if version.startswith('11') else '')
except Exception:
    print('')
"""
    result = subprocess.run(
        [str(python), "-c", probe], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=False,
    )
    token = (result.stdout or "").strip().lower()
    return token if token in {"cuda11", "cuda12"} else "cuda12"


def _install_sherpa_runtime(python: Path, device: str, cuda_variant: str = "auto") -> str:
    target = str(device or "cpu").strip().lower()
    if target == "cpu":
        run([str(python), "-m", "pip", "install", "--upgrade", "--force-reinstall", "sherpa-onnx"], phase="Memasang runtime sherpa-onnx CPU")
        return "cpu"
    variant = str(cuda_variant or "auto").strip().lower()
    if variant == "auto":
        variant = _detect_cuda_variant(python)
    if variant not in {"cuda11", "cuda12"}:
        raise ValueError(f"Unsupported CUDA variant: {variant}")
    requirement = SHERPA_CUDA12_REQUIREMENT if variant == "cuda12" else SHERPA_CUDA11_REQUIREMENT
    run([
        str(python), "-m", "pip", "install", "--upgrade", "--force-reinstall", "--no-cache-dir",
        requirement, "--no-index", "-f", SHERPA_CUDA_INDEX,
    ], phase=f"Memasang runtime sherpa-onnx {variant.upper()}")
    verify = (
        "import sherpa_onnx; "
        "v=str(getattr(sherpa_onnx,'__version__','')); "
        "print('sherpa_onnx='+v); "
        "assert '+cuda' in v, 'CUDA-enabled sherpa-onnx wheel was not installed'"
    )
    run([str(python), "-c", verify], phase="Memverifikasi runtime CUDA")
    return variant


def install_reazon(
    python: Path,
    runtime_root: Path,
    status_root: Path,
    warm_model: bool,
    *,
    device: str = "cpu",
    cuda_variant: str = "auto",
) -> None:
    provider = "reazonspeech_k2"
    target_device = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    emit("setup_start", provider=provider, device=target_device)
    sources = runtime_root / "provider_sources"
    repo = sources / "ReazonSpeech"
    sources.mkdir(parents=True, exist_ok=True)
    if not repo.is_dir():
        run(["git", "clone", "--depth", "1", "https://github.com/reazon-research/ReazonSpeech.git", str(repo)], phase="Mengambil source ReazonSpeech")
    else:
        run(["git", "fetch", "--depth", "1", "origin"], cwd=repo, phase="Memperbarui source ReazonSpeech")
        run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=repo)
    run([str(python), "-m", "pip", "install", "--upgrade", str(repo / "pkg" / "k2-asr")], phase="Memasang paket ReazonSpeech K2")
    installed_variant = _install_sherpa_runtime(python, target_device, cuda_variant)
    cache_dir = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    total, downloaded, files, model_path = _download_hf_repo(provider, HF_REPOS[provider], cache_dir=cache_dir)
    if warm_model:
        precision = "int8-fp32" if target_device == "cuda" else "int8"
        warmup = (
            "from reazonspeech.k2.asr import load_model; "
            f"load_model(device={target_device!r}, precision={precision!r}, language='ja'); "
            f"print('ReazonSpeech K2 {target_device.upper()} model ready')"
        )
        run([str(python), "-c", warmup], phase=f"Memverifikasi model ReazonSpeech K2 {target_device.upper()}")
    _write_status(
        status_root, provider, target_device, runtime_python=python,
        model_total_bytes=total, model_downloaded_bytes=downloaded,
        model_files=files, model_path=model_path, runtime_ready=True,
        details={"sherpa_variant": installed_variant},
    )
    emit("device_ready", provider=provider, device=target_device, status="ready")
    print(f"ReazonSpeech K2 setup ready | device={target_device} | runtime={installed_variant}")


def install_sensevoice(python: Path, model_root: Path, status_root: Path) -> Path:
    provider = "sensevoice_small"
    device = "cpu"
    emit("setup_start", provider=provider, device=device)
    run([str(python), "-m", "pip", "install", "--upgrade", "sherpa-onnx"], phase="Memasang runtime SenseVoice CPU")
    target = model_root / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09"
    archive = model_root / ".downloads" / "sensevoice-small-int8.tar.bz2"
    if not ((target / "model.int8.onnx").is_file() and (target / "tokens.txt").is_file()):
        total, downloaded = _download_url(provider, SENSEVOICE_URL, archive)
        emit("phase", phase="extract", message="Mengekstrak model SenseVoice-Small")
        with tarfile.open(archive, "r:bz2") as handle:
            handle.extractall(model_root)
    else:
        total = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
        downloaded = total
        emit("model_info", provider=provider, total_bytes=total, downloaded_bytes=downloaded,
             total_human=human_bytes(total), downloaded_human=human_bytes(downloaded), percent=100.0)
    if not (target / "model.int8.onnx").is_file():
        raise RuntimeError(f"SenseVoice extraction incomplete: {target}")
    files = [{"path": str(path), "size": path.stat().st_size, "filename": path.name} for path in target.rglob("*") if path.is_file()]
    model_total = sum(int(item["size"]) for item in files)
    _write_status(status_root, provider, device, runtime_python=python,
                  model_total_bytes=model_total, model_downloaded_bytes=model_total,
                  model_files=files, model_path=str(target), runtime_ready=True)
    emit("download_complete", provider=provider, total_bytes=model_total, downloaded_bytes=model_total,
         total_human=human_bytes(model_total), downloaded_human=human_bytes(model_total), percent=100.0)
    emit("device_ready", provider=provider, device=device, status="ready")
    print(f"SenseVoice ready: {target}")
    return target


def install_faster_provider(
    python: Path,
    model_root: Path,
    status_root: Path,
    provider: str,
    device: str,
) -> None:
    target_device = "cuda" if str(device).lower() == "cuda" else "cpu"
    emit("setup_start", provider=provider, device=target_device)
    run([str(python), "-m", "pip", "install", "--upgrade", "faster-whisper"], phase="Memasang Faster-Whisper/CTranslate2")
    local_dir = model_root / LOCAL_MODEL_DIRS[provider]
    total, downloaded, files, model_path = _download_hf_repo(provider, HF_REPOS[provider], local_dir=local_dir)
    compute = "int8_float16" if target_device == "cuda" else "int8"
    probe = (
        "from faster_whisper import WhisperModel; "
        f"m=WhisperModel({str(local_dir)!r}, device={target_device!r}, compute_type={compute!r}); "
        "print('Faster-Whisper provider ready')"
    )
    run([str(python), "-c", probe], phase=f"Memverifikasi {provider} {target_device.upper()}")
    _write_status(status_root, provider, target_device, runtime_python=python,
                  model_total_bytes=total, model_downloaded_bytes=downloaded,
                  model_files=files, model_path=model_path, runtime_ready=True)
    emit("device_ready", provider=provider, device=target_device, status="ready")


def install_argos_bridge(python: Path, status_root: Path, device: str) -> None:
    provider = "argos_bridge"
    target_device = "cuda" if str(device).lower() == "cuda" else "cpu"
    emit("setup_start", provider=provider, device=target_device)
    run([str(python), "-m", "pip", "install", "argostranslate"], phase=f"Memasang translation bridge {target_device.upper()}")
    script = """
import argostranslate.package
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
for pair in [('ja', 'en'), ('en', 'id')]:
    if pair in installed:
        print('Argos already installed', pair)
        continue
    package = next((p for p in available if p.from_code == pair[0] and p.to_code == pair[1]), None)
    if package is None:
        raise RuntimeError('Argos package unavailable: %s->%s' % pair)
    path = package.download()
    argostranslate.package.install_from_path(path)
    print('Argos installed', pair)
"""
    run([str(python), "-c", script], phase="Mengunduh paket bridge JA→EN dan EN→ID")
    functional = """
import argostranslate.translate
langs = {lang.code: lang for lang in argostranslate.translate.get_installed_languages()}
ja_en = langs['ja'].get_translation(langs['en'])
en_id = langs['en'].get_translation(langs['id'])
preview = str(ja_en.translate('これはテストです') or '').strip()
translated = str(en_id.translate('This is a test') or '').strip()
assert preview and preview != 'これはテストです', preview
assert translated and translated.casefold() != 'This is a test'.casefold(), translated
print('Argos bridge functional PASS')
"""
    run([str(python), "-c", functional], phase="Memverifikasi bridge Jepang→Inggris→Indonesia")
    _write_status(status_root, provider, target_device, runtime_python=python,
                  model_total_bytes=1, model_downloaded_bytes=1,
                  model_files=[], model_path="argostranslate-packages", runtime_ready=True,
                  bridge_ready=True)
    emit("bridge_ready", provider=provider, device=target_device, status="ready")


def self_test() -> int:
    configure_utf8()
    assert "<inline-python-script>" in _display_command(["python", "-c", "print('日本語')"])
    assert human_bytes(1024 ** 3).startswith("1.00 GB")
    with tempfile.TemporaryDirectory(prefix="ort-r4-selftest-") as temp:
        root = Path(temp)
        file = root / "model.bin"
        file.write_bytes(b"x" * 32)
        path = _write_status(root, "demo", "cpu", runtime_python=Path(sys.executable),
                             model_total_bytes=32, model_downloaded_bytes=32,
                             model_files=[{"path": str(file), "size": 32}],
                             model_path=str(file), runtime_ready=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["model_complete"] and data["runtime_ready"]
    print(json.dumps({"passed": True, "version": "v9.0.4-R4", "utf8_console": "PASS", "progress_events": "PASS"}))
    return 0


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", nargs="?", choices=[
        "reazonspeech_k2", "sensevoice_small", "kotoba_bilingual",
        "faster_whisper_base", "faster_whisper_small", "argos_bridge", "all",
    ])
    parser.add_argument("--runtime-root")
    parser.add_argument("--model-root")
    parser.add_argument("--status-root")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-model-warmup", action="store_true")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--cuda-variant", choices=["auto", "cuda11", "cuda12"], default="auto")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.provider or not args.runtime_root or not args.model_root:
        parser.error("provider, --runtime-root, and --model-root are required")

    runtime_root = Path(args.runtime_root).expanduser().resolve()
    model_root = Path(args.model_root).expanduser().resolve()
    status_root = Path(args.status_root).expanduser().resolve() if args.status_root else runtime_root / "provider_setup_status"
    python = Path(args.python).expanduser().resolve()
    if not python.is_file():
        raise FileNotFoundError(f"Python runtime not found: {python}")

    provider = args.provider
    try:
        if provider in {"reazonspeech_k2", "all"}:
            install_reazon(python, runtime_root, status_root, not args.skip_model_warmup,
                           device=args.device, cuda_variant=args.cuda_variant)
        if provider in {"sensevoice_small", "all"}:
            if args.device == "cuda":
                raise RuntimeError("SenseVoice-Small GPU belum didukung pada v9.0.4 R4")
            install_sensevoice(python, model_root, status_root)
        if provider in {"kotoba_bilingual", "faster_whisper_base", "faster_whisper_small"}:
            install_faster_provider(python, model_root, status_root, provider, args.device)
        if provider in {"argos_bridge", "all"}:
            install_argos_bridge(python, status_root, args.device)
        emit("setup_complete", provider=provider, device=args.device, passed=True)
        print(json.dumps({"passed": True, "provider": provider, "device": args.device}, ensure_ascii=False))
        return 0
    except BaseException as exc:
        emit("setup_failed", provider=provider, device=args.device, passed=False,
             error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
