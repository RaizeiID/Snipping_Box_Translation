from __future__ import annotations

import argparse
import hashlib
import http.client
import ssl
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
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

REAZON_REVISION = "291488c8151be24d7da4bf7af26e533fad96e407"
REAZON_LOCAL_DIR = "reazonspeech-k2-v2"
REAZON_FILE_MANIFEST: dict[str, dict[str, Any]] = {
    "tokens.txt": {"size": 45754, "sha256": ""},
    "encoder-epoch-99-avg-1.int8.onnx": {
        "size": 154670139,
        "sha256": "2c7bd08a8a99f9ddd0d9e458456577b1f6279214e51426f114f9eced44c54e1d",
    },
    "decoder-epoch-99-avg-1.int8.onnx": {
        "size": 2959337,
        "sha256": "8f0bff94d38797b03b762634ed03211a8e303d06cc4603cdd0cf4199d6eb1485",
    },
    "decoder-epoch-99-avg-1.onnx": {
        "size": 11767836,
        "sha256": "58b18211ae06265466bfa17172dab574df94f76c8bcb61a3640c28ba860e4124",
    },
    "joiner-epoch-99-avg-1.int8.onnx": {
        "size": 2696970,
        "sha256": "49cc7ea1d3d35a40a27442db5e89996da64bf0e683a903dce76e99e57a12e4de",
    },
}
REAZON_DEVICE_FILES = {
    "cpu": (
        "tokens.txt",
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.int8.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
    ),
    "cuda": (
        "tokens.txt",
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
    ),
}


def configure_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    # Hugging Face defaults are intentionally conservative. Model files are
    # large, so use longer network timeouts and the regular HTTP cache path.
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
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




def _transient_download_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    needles = (
        "connectionreseterror", "winerror 10054", "remoteprotocolerror",
        "server disconnected", "connection aborted", "connection reset",
        "timed out", "timeout", "temporarily unavailable", "502", "503",
        "504", "rate limit", "429", "incompletesnapshoterror",
        "connecterror", "urlerror", "remotedisconnected", "sslerror",
        "connection refused", "network is unreachable",
    )
    return any(token in text for token in needles)


def _retry_delay(attempt: int) -> float:
    schedule = (2.0, 4.0, 8.0, 12.0, 20.0, 30.0, 45.0, 60.0)
    base = schedule[min(max(1, attempt) - 1, len(schedule) - 1)]
    return base + random.uniform(0.0, min(1.5, base * 0.1))


def _run_with_retry(label: str, operation, *, max_attempts: int = 8, provider: str = ""):
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except BaseException as exc:
            if attempt >= max_attempts or not _transient_download_error(exc):
                raise
            delay = _retry_delay(attempt)
            emit(
                "download_retry", provider=provider, label=label, attempt=attempt,
                max_attempts=max_attempts, delay_seconds=round(delay, 1),
                error=f"{type(exc).__name__}: {exc}",
            )
            print(
                f"[DOWNLOAD RETRY] {label} gagal ({attempt}/{max_attempts}): "
                f"{type(exc).__name__}: {exc}. Mencoba lagi dalam {delay:.1f}s.",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(f"Retry loop berakhir tanpa hasil: {label}")


def _runtime_probe(python: Path, device: str) -> tuple[bool, str]:
    expected_cuda = str(device).lower() == "cuda"
    script = (
        "import reazonspeech.k2.asr, sherpa_onnx; "
        "print(getattr(sherpa_onnx, '__version__', 'unknown'))"
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [str(python), "-c", script], capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, check=False, timeout=60,
    )
    output = ((result.stdout or "") + " " + (result.stderr or "")).strip()
    if result.returncode != 0:
        return False, output[-500:]
    if expected_cuda and "+cuda" not in output.lower():
        return False, f"sherpa-onnx masih build CPU: {output}"
    return True, output


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
    progress_hook=None,
) -> tuple[int, int, list[dict[str, Any]], str]:
    from huggingface_hub import get_token, hf_hub_download, snapshot_download
    from tqdm.auto import tqdm

    token = get_token()
    emit("hf_auth", provider=provider, authenticated=bool(token))
    if not token:
        print(
            "[HF] Unduhan tanpa autentikasi. Cache tetap didukung; login HF opsional "
            "untuk rate limit yang lebih longgar.", flush=True,
        )

    kwargs: dict[str, Any] = {
        "repo_id": repo_id,
        "dry_run": True,
        "max_workers": 1,
        "etag_timeout": 30,
        "token": token or None,
    }
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        kwargs["cache_dir"] = str(cache_dir)
    if local_dir is not None:
        local_dir.mkdir(parents=True, exist_ok=True)
        kwargs["local_dir"] = str(local_dir)

    entries = list(_run_with_retry(
        "membaca metadata model",
        lambda: snapshot_download(**kwargs),
        max_attempts=8,
        provider=provider,
    ))
    total = sum(int(item.file_size or 0) for item in entries)
    completed = sum(int(item.file_size or 0) for item in entries if item.is_cached)
    files: list[dict[str, Any]] = []
    for item in entries:
        if item.is_cached:
            path = Path(item.local_path)
            files.append({"path": str(path), "size": int(item.file_size or 0), "filename": item.filename})
    emit(
        "model_info", provider=provider, repo_id=repo_id, total_bytes=total,
        downloaded_bytes=completed, total_human=human_bytes(total),
        downloaded_human=human_bytes(completed),
        percent=round((completed / total * 100) if total else 0.0, 2),
    )
    if completed:
        emit(
            "cache_reuse", provider=provider, downloaded_bytes=completed,
            total_bytes=total, downloaded_human=human_bytes(completed),
            percent=round((completed / total * 100) if total else 0.0, 2),
        )
    if callable(progress_hook):
        progress_hook(total, completed, list(files), str(local_dir or cache_dir or ""))

    for item in entries:
        size = int(item.file_size or 0)
        if item.is_cached:
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
                        "download_progress", provider=provider, filename=item.filename,
                        total_bytes=total, downloaded_bytes=global_value,
                        total_human=human_bytes(total), downloaded_human=human_bytes(global_value),
                        percent=round((global_value / total * 100) if total else 0.0, 2),
                    )
                return result

        def download_one():
            download_kwargs: dict[str, Any] = {
                "repo_id": repo_id,
                "filename": item.filename,
                "tqdm_class": EventTqdm,
                "etag_timeout": 30,
                "token": token or None,
                "force_download": False,
            }
            if cache_dir is not None:
                download_kwargs["cache_dir"] = str(cache_dir)
            if local_dir is not None:
                download_kwargs["local_dir"] = str(local_dir)
            return hf_hub_download(**download_kwargs)

        downloaded_path = Path(_run_with_retry(
            f"mengunduh {item.filename}", download_one,
            max_attempts=8, provider=provider,
        ))
        completed += size
        files.append({"path": str(downloaded_path), "size": size, "filename": item.filename})
        if callable(progress_hook):
            progress_hook(total, completed, list(files), str(local_dir or downloaded_path.parent))
        emit(
            "download_progress", provider=provider, filename=item.filename,
            total_bytes=total, downloaded_bytes=min(completed, total),
            total_human=human_bytes(total), downloaded_human=human_bytes(min(completed, total)),
            percent=round((min(completed, total) / total * 100) if total else 100.0, 2),
        )

    # Verify every expected file from the dry-run manifest exists at full size.
    file_map = {str(item.get("filename")): item for item in files}
    missing: list[str] = []
    for entry in entries:
        item = file_map.get(str(entry.filename))
        path = Path(str((item or {}).get("path") or entry.local_path or ""))
        expected = int(entry.file_size or 0)
        if not path.is_file() or (expected and path.stat().st_size < expected):
            missing.append(str(entry.filename))
    if missing:
        raise RuntimeError("Snapshot model belum lengkap: " + ", ".join(missing[:8]))

    resolved = str(local_dir if local_dir is not None else (files[0]["path"] if files else cache_dir or ""))
    emit(
        "download_complete", provider=provider, total_bytes=total, downloaded_bytes=total,
        total_human=human_bytes(total), downloaded_human=human_bytes(total), percent=100.0,
    )
    return total, total, files, resolved



def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reazon_required_files(device: str) -> tuple[str, ...]:
    target = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    return tuple(REAZON_DEVICE_FILES[target])


def _valid_static_file(path: Path, entry: dict[str, Any], *, verify_hash: bool = True) -> bool:
    try:
        if not path.is_file() or path.stat().st_size != int(entry["size"]):
            return False
        expected_hash = str(entry.get("sha256") or "").strip().lower()
        return not (verify_hash and expected_hash) or _sha256_file(path).lower() == expected_hash
    except Exception:
        return False


def _reazon_cache_candidates(cache_dir: Path, filename: str) -> list[Path]:
    roots = [cache_dir, cache_dir / "hub"]
    candidates: list[Path] = []
    for root in roots:
        repo_cache = root / "models--reazon-research--reazonspeech-k2-v2"
        snapshots = repo_cache / "snapshots"
        if snapshots.is_dir():
            candidates.extend(sorted(snapshots.glob(f"*/{filename}"), reverse=True))
    return candidates


def _reuse_reazon_cache(cache_dir: Path, destination: Path, filename: str, entry: dict[str, Any]) -> bool:
    if _valid_static_file(destination, entry):
        return True
    for source in _reazon_cache_candidates(cache_dir, filename):
        if not _valid_static_file(source, entry):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(str(destination) + ".cache-copy")
        temporary.unlink(missing_ok=True)
        try:
            os.link(source, temporary)
        except Exception:
            shutil.copy2(source, temporary)
        temporary.replace(destination)
        emit("cache_file_reused", provider="reazonspeech_k2", filename=filename,
             bytes=int(entry["size"]), source=str(source), destination=str(destination))
        print(f"[CACHE] Menggunakan kembali {filename} dari cache Hugging Face.", flush=True)
        return True
    return False


def _hf_direct_url(repo_id: str, revision: str, filename: str) -> str:
    endpoint = str(os.environ.get("HF_ENDPOINT") or "https://huggingface.co").rstrip("/")
    return f"{endpoint}/{repo_id}/resolve/{revision}/{filename}?download=true"


def _download_static_file(
    provider: str,
    repo_id: str,
    revision: str,
    filename: str,
    entry: dict[str, Any],
    destination: Path,
    *,
    token: str | None,
    aggregate_total: int,
    aggregate_complete_before: int,
    progress_hook=None,
    completed_files=None,
) -> Path:
    expected_size = int(entry["size"])
    expected_hash = str(entry.get("sha256") or "").strip().lower()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(str(destination) + ".part")
    if destination.exists() and not _valid_static_file(destination, entry):
        corrupt = Path(str(destination) + f".invalid-{int(time.time())}")
        destination.replace(corrupt)
        print(f"[VERIFY] File tidak valid dipindahkan: {corrupt.name}", flush=True)

    if _valid_static_file(destination, entry):
        return destination

    def attempt_download() -> Path:
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset > expected_size:
            partial.unlink(missing_ok=True)
            offset = 0
        headers = {
            "User-Agent": "ORT-v9.0.4-R5-F2/1.0",
            "Accept": "application/octet-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(_hf_direct_url(repo_id, revision, filename), headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and offset == expected_size:
                partial.replace(destination)
                return destination
            raise
        with response:
            status = int(getattr(response, "status", response.getcode()) or 200)
            append = bool(offset and status == 206)
            if offset and not append:
                print(f"[RESUME] Server tidak menerima Range untuk {filename}; mengulang file ini.", flush=True)
                offset = 0
            mode = "ab" if append else "wb"
            downloaded_file = offset
            last_emit = 0.0
            with partial.open(mode) as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    handle.flush()
                    downloaded_file += len(chunk)
                    aggregate_value = min(aggregate_total, aggregate_complete_before + downloaded_file)
                    now = time.monotonic()
                    if now - last_emit >= 0.15 or downloaded_file >= expected_size:
                        last_emit = now
                        emit(
                            "download_progress", provider=provider, filename=filename,
                            total_bytes=aggregate_total, downloaded_bytes=aggregate_value,
                            total_human=human_bytes(aggregate_total),
                            downloaded_human=human_bytes(aggregate_value),
                            percent=round((aggregate_value / aggregate_total * 100) if aggregate_total else 0.0, 2),
                            file_downloaded_bytes=downloaded_file, file_total_bytes=expected_size,
                            resumable=True,
                        )
                        if callable(progress_hook):
                            known = list(completed_files or [])
                            progress_hook(aggregate_total, aggregate_value, known, str(destination.parent))
        actual_size = partial.stat().st_size if partial.is_file() else 0
        if actual_size != expected_size:
            raise IOError(f"Ukuran {filename} belum lengkap: {actual_size}/{expected_size} byte")
        if expected_hash and _sha256_file(partial).lower() != expected_hash:
            bad = Path(str(partial) + f".sha256-failed-{int(time.time())}")
            partial.replace(bad)
            raise IOError(f"Checksum SHA-256 gagal untuk {filename}; file disimpan sebagai {bad.name}")
        partial.replace(destination)
        return destination

    return Path(_run_with_retry(
        f"mengunduh langsung {filename}", attempt_download,
        max_attempts=8, provider=provider,
    ))


def _download_reazon_static(
    *,
    device: str,
    model_root: Path,
    cache_dir: Path,
    progress_hook=None,
) -> tuple[int, int, list[dict[str, Any]], str]:
    provider = "reazonspeech_k2"
    repo_id = HF_REPOS[provider]
    target_device = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    required = _reazon_required_files(target_device)
    local_dir = model_root / REAZON_LOCAL_DIR
    local_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import get_token
        token = get_token()
    except Exception:
        token = None
    emit("hf_auth", provider=provider, authenticated=bool(token), metadata_preflight=False)
    print(
        "[HF] Mode manifest langsung aktif; snapshot dry-run/API metadata dilewati. "
        + ("Token ditemukan." if token else "Unduhan publik tanpa login."),
        flush=True,
    )

    total = sum(int(REAZON_FILE_MANIFEST[name]["size"]) for name in required)
    files: list[dict[str, Any]] = []
    completed = 0
    partial_bytes = 0
    for filename in required:
        entry = REAZON_FILE_MANIFEST[filename]
        destination = local_dir / filename
        if _reuse_reazon_cache(cache_dir, destination, filename, entry):
            completed += int(entry["size"])
            files.append({"path": str(destination), "size": int(entry["size"]), "filename": filename})
        else:
            part = Path(str(destination) + ".part")
            partial_bytes += min(part.stat().st_size if part.is_file() else 0, int(entry["size"]))
    visible_downloaded = min(total, completed + partial_bytes)
    emit(
        "model_info", provider=provider, repo_id=repo_id, revision=REAZON_REVISION,
        total_bytes=total, downloaded_bytes=visible_downloaded,
        total_human=human_bytes(total), downloaded_human=human_bytes(visible_downloaded),
        percent=round((visible_downloaded / total * 100) if total else 0.0, 2),
        required_files=list(required), metadata_preflight=False,
    )
    if visible_downloaded:
        emit("cache_reuse", provider=provider, downloaded_bytes=visible_downloaded,
             total_bytes=total, downloaded_human=human_bytes(visible_downloaded),
             percent=round(visible_downloaded / total * 100, 2))
    if callable(progress_hook):
        progress_hook(total, visible_downloaded, list(files), str(local_dir))

    completed = sum(int(item["size"]) for item in files)
    for filename in required:
        entry = REAZON_FILE_MANIFEST[filename]
        destination = local_dir / filename
        if _valid_static_file(destination, entry):
            continue
        downloaded_path = _download_static_file(
            provider, repo_id, REAZON_REVISION, filename, entry, destination,
            token=token, aggregate_total=total, aggregate_complete_before=completed,
            progress_hook=progress_hook, completed_files=files,
        )
        completed += int(entry["size"])
        files.append({"path": str(downloaded_path), "size": int(entry["size"]), "filename": filename})
        if callable(progress_hook):
            progress_hook(total, completed, list(files), str(local_dir))

    missing = [name for name in required if not _valid_static_file(local_dir / name, REAZON_FILE_MANIFEST[name])]
    if missing:
        raise RuntimeError("Model Reazon lokal belum lengkap: " + ", ".join(missing))
    emit("download_complete", provider=provider, total_bytes=total, downloaded_bytes=total,
         total_human=human_bytes(total), downloaded_human=human_bytes(total), percent=100.0,
         model_path=str(local_dir), metadata_preflight=False)
    return total, total, files, str(local_dir)


def _reazon_local_warmup_script(model_dir: Path, device: str) -> str:
    target = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    decoder = "decoder-epoch-99-avg-1.onnx" if target == "cuda" else "decoder-epoch-99-avg-1.int8.onnx"
    return (
        "import sherpa_onnx; "
        f"root={str(model_dir)!r}; "
        "from pathlib import Path; p=Path(root); "
        "m=sherpa_onnx.OfflineRecognizer.from_transducer("
        "tokens=str(p/'tokens.txt'), "
        "encoder=str(p/'encoder-epoch-99-avg-1.int8.onnx'), "
        f"decoder=str(p/{decoder!r}), "
        "joiner=str(p/'joiner-epoch-99-avg-1.int8.onnx'), "
        "num_threads=1, sample_rate=16000, feature_dim=80, "
        f"decoding_method='greedy_search', provider={target!r}); "
        f"print('ReazonSpeech K2 local {target.upper()} model ready')"
    )


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
    model_root: Path,
    status_root: Path,
    warm_model: bool,
    *,
    device: str = "cpu",
    cuda_variant: str = "auto",
) -> None:
    provider = "reazonspeech_k2"
    target_device = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    emit("setup_start", provider=provider, device=target_device)

    runtime_ready, runtime_detail = _runtime_probe(python, target_device)
    installed_variant = runtime_detail.strip() or target_device
    if runtime_ready:
        emit("runtime_reuse", provider=provider, device=target_device, detail=runtime_detail)
        print(
            f"ReazonSpeech K2 runtime {target_device.upper()} sudah siap; "
            "melewati git/pip reinstall.", flush=True,
        )
    else:
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
        runtime_ready, runtime_detail = _runtime_probe(python, target_device)
        if not runtime_ready:
            raise RuntimeError(f"Runtime ReazonSpeech {target_device.upper()} belum siap: {runtime_detail}")

    cache_dir = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")

    def persist_partial(total: int, downloaded: int, files: list[dict[str, Any]], model_path: str) -> None:
        _write_status(
            status_root, provider, target_device, runtime_python=python,
            model_total_bytes=total, model_downloaded_bytes=downloaded,
            model_files=files, model_path=model_path, runtime_ready=True,
            details={
                "sherpa_variant": installed_variant,
                "download_resumable": True,
                "download_state": "complete" if total and downloaded >= total else "partial",
            },
        )

    total, downloaded, files, model_path = _download_reazon_static(
        device=target_device, model_root=model_root, cache_dir=cache_dir,
        progress_hook=persist_partial,
    )
    if warm_model:
        warmup = _reazon_local_warmup_script(Path(model_path), target_device)
        run([str(python), "-c", warmup], phase=f"Memverifikasi model lokal ReazonSpeech K2 {target_device.upper()}")
    _write_status(
        status_root, provider, target_device, runtime_python=python,
        model_total_bytes=total, model_downloaded_bytes=downloaded,
        model_files=files, model_path=model_path, runtime_ready=True,
        details={
            "sherpa_variant": installed_variant,
            "download_resumable": True,
            "download_state": "complete",
            "download_strategy": "direct_static_manifest",
            "revision": REAZON_REVISION,
            "required_files": list(_reazon_required_files(target_device)),
        },
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
    assert _transient_download_error(ConnectionResetError(10054, "reset"))
    assert _transient_download_error(RuntimeError("Server disconnected without sending a response"))
    assert not _transient_download_error(ValueError("invalid provider"))
    assert _retry_delay(1) >= 2.0
    assert os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT") == "120"
    assert _reazon_required_files("cpu")[2].endswith("int8.onnx")
    assert _reazon_required_files("cuda")[2] == "decoder-epoch-99-avg-1.onnx"
    assert sum(REAZON_FILE_MANIFEST[name]["size"] for name in _reazon_required_files("cpu")) == 160372200
    assert sum(REAZON_FILE_MANIFEST[name]["size"] for name in _reazon_required_files("cuda")) == 169180699
    assert "snapshot_download" not in _download_reazon_static.__code__.co_names
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
    print(json.dumps({
        "passed": True, "version": "v9.0.4-R5",
        "utf8_console": "PASS", "progress_events": "PASS",
        "hf_single_worker_retry": "PASS", "partial_manifest": "PASS",
        "runtime_reuse": "PASS", "reazon_static_manifest": "PASS",
        "reazon_local_direct_load": "PASS",
    }))
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
            install_reazon(python, runtime_root, model_root, status_root, not args.skip_model_warmup,
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
