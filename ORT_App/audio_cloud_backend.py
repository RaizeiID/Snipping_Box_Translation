from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from app.audio.cloud_streaming import (
    normalize_audio_engine,
    normalize_audio_usage,
    normalize_source_locale,
    normalize_target_language,
    resolve_cloud_engine,
)


BASE_DIR = Path(__file__).resolve().parent
EVENT_PREFIX = "ORT_AUDIO_CLOUD_EVENT "
_PROBE_LOCK = threading.Lock()
_PROBE_CACHE: Dict[str, Any] = {}
_SETUP_LOCK = threading.Lock()


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def cloud_runtime_paths(base_dir: Path | str = BASE_DIR) -> Dict[str, Path]:
    base = Path(base_dir).resolve()
    runtime_cfg = _load_json(base / "runtime_paths.json")
    runtime_root = Path(runtime_cfg.get("runtime_root") or (base / "_runtime")).expanduser().resolve()
    ocr_python = Path(runtime_cfg.get("runtime_python") or _venv_python(runtime_root)).expanduser().resolve()
    cloud_root = runtime_root / "audio_cloud"
    return {
        "base_dir": base,
        "runtime_root": runtime_root,
        "ocr_python": ocr_python,
        "cloud_root": cloud_root,
        "cloud_python": _venv_python(cloud_root),
        "requirements": base / "requirements_audio_cloud.txt",
        "sidecar": base / "audio_cloud_sidecar.py",
        "config": cloud_root / "config.json",
        "spool_root": runtime_root / "audio_cloud_spool",
    }


def parse_cloud_events(text: str) -> list[dict]:
    events = []
    for line in str(text or "").splitlines():
        if not line.startswith(EVENT_PREFIX):
            continue
        try:
            payload = json.loads(line[len(EVENT_PREFIX):])
            if isinstance(payload, dict):
                events.append(payload)
        except Exception:
            continue
    return events


def _run(
    args: Iterable[str | Path],
    *,
    timeout: float = 60.0,
    cwd: Optional[Path] = None,
    input_text: str = "",
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(item) for item in args],
        cwd=str(cwd or BASE_DIR),
        input=input_text or None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )


def _probe_key(base_dir: Path | str, network_test: bool) -> str:
    return f"{Path(base_dir).resolve()}::{int(bool(network_test))}"


def clear_cloud_probe_cache() -> None:
    with _PROBE_LOCK:
        _PROBE_CACHE.clear()


def probe_cloud_runtime(
    force: bool = False,
    base_dir: Path | str = BASE_DIR,
    network_test: bool = False,
) -> dict:
    key = _probe_key(base_dir, network_test)
    now = time.monotonic()
    with _PROBE_LOCK:
        cached = _PROBE_CACHE.get(key)
        if not force and cached and now - float(cached.get("cached_at", 0.0)) < 8.0:
            return dict(cached["value"])
    paths = cloud_runtime_paths(base_dir)
    if not paths["cloud_python"].exists():
        value = {
            "provider": "azure",
            "installed": False,
            "ready": False,
            "sdk": False,
            "keyring": False,
            "credential_set": False,
            "region": str(_load_json(paths["config"]).get("region") or ""),
            "cloud_connected": False,
            "network_tested": bool(network_test),
            "message": "Runtime Azure belum dipasang.",
            "python": str(paths["cloud_python"]),
        }
    else:
        try:
            command: list[str | Path] = [
                paths["cloud_python"],
                paths["sidecar"],
                "--probe-json",
                "--config-path",
                paths["config"],
            ]
            if network_test:
                command.append("--network-test")
            result = _run(command, timeout=45.0 if not network_test else 90.0, cwd=paths["base_dir"])
            events = parse_cloud_events(result.stdout)
            probe = next((item for item in reversed(events) if item.get("type") == "probe"), {})
            value = {
                **probe,
                "provider": "azure",
                "installed": True,
                "python": str(paths["cloud_python"]),
                "returncode": int(result.returncode),
            }
            dependency_ready = bool(value.get("sdk") and value.get("keyring"))
            if os.name == "nt":
                dependency_ready = bool(dependency_ready and value.get("wasapi"))
            value["dependency_ready"] = dependency_ready
            value["ready"] = bool(value.get("ready"))
            if value["ready"]:
                value["message"] = "Azure Speech siap."
            elif dependency_ready and not value.get("credential_set"):
                value["message"] = "Runtime Azure siap; API key belum disimpan."
            elif dependency_ready and not value.get("region"):
                value["message"] = "Runtime Azure siap; region belum disimpan."
            else:
                value["message"] = "Dependensi Azure Speech belum siap."
            if not probe:
                value["errors"] = [result.stdout[-1800:]]
        except Exception as exc:
            value = {
                "provider": "azure",
                "installed": True,
                "ready": False,
                "dependency_ready": False,
                "credential_set": False,
                "cloud_connected": False,
                "network_tested": bool(network_test),
                "python": str(paths["cloud_python"]),
                "message": f"Probe Azure gagal: {exc}",
                "errors": [str(exc)],
            }
    with _PROBE_LOCK:
        _PROBE_CACHE[key] = {"cached_at": now, "value": dict(value)}
    return value


def cloud_config_values(base_dir: Path | str = BASE_DIR) -> dict:
    paths = cloud_runtime_paths(base_dir)
    config = _load_json(paths["config"])
    probe = probe_cloud_runtime(False, base_dir, False)
    return {
        "provider": "azure",
        "region": str(config.get("region") or ""),
        "source_locale": normalize_source_locale(str(config.get("source_locale") or "ja-JP")),
        "target_language": normalize_target_language(str(config.get("target_language") or "id")),
        "credential_set": bool(probe.get("credential_set")),
        "installed": bool(probe.get("installed")),
        "ready": bool(probe.get("ready")),
    }


def save_cloud_config(
    region: str,
    api_key: str,
    source_locale: str = "ja-JP",
    target_language: str = "id",
    base_dir: Path | str = BASE_DIR,
    test_connection: bool = True,
) -> str:
    paths = cloud_runtime_paths(base_dir)
    if not paths["cloud_python"].exists():
        return "GAGAL: Siapkan runtime Azure terlebih dahulu."
    payload = json.dumps({
        "region": str(region or "").strip(),
        "api_key": str(api_key or "").strip(),
        "source_locale": normalize_source_locale(source_locale),
        "target_language": normalize_target_language(target_language),
    }, ensure_ascii=False, separators=(",", ":"))
    try:
        result = _run(
            [
                paths["cloud_python"],
                paths["sidecar"],
                "--save-config-json",
                "--config-path",
                paths["config"],
            ],
            timeout=45.0,
            cwd=paths["base_dir"],
            input_text=payload + "\n",
        )
        events = parse_cloud_events(result.stdout)
        error = next((item for item in reversed(events) if item.get("type") == "error"), {})
        if result.returncode != 0 or error:
            return "GAGAL menyimpan konfigurasi Azure: " + str(error.get("message") or "Credential Manager tidak tersedia.")
        clear_cloud_probe_cache()
        probe = probe_cloud_runtime(True, base_dir, bool(test_connection))
        lines = [
            "Konfigurasi Azure tersimpan aman di Windows Credential Manager.",
            f"region = {str(region or '').strip()}",
            f"source_locale = {normalize_source_locale(source_locale)}",
            f"target_language = {normalize_target_language(target_language)}",
            f"credential_set = {bool(probe.get('credential_set'))}",
            f"cloud_connected = {bool(probe.get('cloud_connected'))}" if test_connection else "cloud_connected = NOT_TESTED",
        ]
        if test_connection and not probe.get("cloud_connected"):
            details = " | ".join(str(item) for item in (probe.get("errors") or []))
            lines.append("connection_test = FAILED")
            if details:
                lines.append("detail = " + details[-1200:])
        else:
            lines.append("connection_test = PASSED" if test_connection else "connection_test = SKIPPED")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "GAGAL: Pengujian Azure melewati batas waktu. Periksa internet, region, dan firewall."
    except Exception as exc:
        return f"GAGAL menyimpan konfigurasi Azure: {type(exc).__name__}: {exc}"


def clear_cloud_credentials(base_dir: Path | str = BASE_DIR) -> str:
    paths = cloud_runtime_paths(base_dir)
    if not paths["cloud_python"].exists():
        return "Runtime Azure belum dipasang; tidak ada kredensial runtime yang dapat dihapus."
    try:
        result = _run(
            [
                paths["cloud_python"],
                paths["sidecar"],
                "--clear-credentials-json",
                "--config-path",
                paths["config"],
            ],
            timeout=30.0,
            cwd=paths["base_dir"],
        )
        events = parse_cloud_events(result.stdout)
        clear_cloud_probe_cache()
        error = next((item for item in reversed(events) if item.get("type") == "error"), {})
        partial = next((item for item in reversed(events) if item.get("type") == "credentials_partially_cleared"), {})
        cleared = next((item for item in reversed(events) if item.get("type") == "credentials_cleared"), {})
        if error:
            return "GAGAL menghapus kredensial Azure: " + str(error.get("message") or "Credential Manager menolak penghapusan.")
        if partial or result.returncode == 2:
            return str(partial.get("message") or "Credential Manager dibersihkan, tetapi API key dari environment masih aktif.")
        if result.returncode == 0 and cleared:
            return "Kredensial Azure berhasil dihapus dari Windows Credential Manager."
        return "GAGAL menghapus kredensial Azure: status sidecar tidak valid."
    except Exception as exc:
        return f"GAGAL menghapus kredensial Azure: {exc}"


def setup_cloud_runtime(base_dir: Path | str = BASE_DIR) -> str:
    if not _SETUP_LOCK.acquire(blocking=False):
        return "Setup Azure sedang berjalan. Tunggu proses aktif selesai."
    try:
        paths = cloud_runtime_paths(base_dir)
        if not paths["ocr_python"].exists():
            return "GAGAL: Runtime Python utama ORT tidak ditemukan. Jalankan Repair Runtime terlebih dahulu."
        if not paths["requirements"].is_file() or not paths["sidecar"].is_file():
            return "GAGAL: File paket Azure tidak lengkap. Terapkan ulang patch."
        paths["cloud_root"].mkdir(parents=True, exist_ok=True)
        steps = []
        if not paths["cloud_python"].exists():
            result = _run(
                [paths["ocr_python"], "-m", "venv", paths["cloud_root"] / ".venv"],
                timeout=300.0,
                cwd=paths["base_dir"],
            )
            steps.append(f"create_cloud_venv={result.returncode}")
            if result.returncode != 0:
                return "GAGAL membuat runtime Azure:\n" + result.stdout[-3000:]
        dependency_probe = probe_cloud_runtime(True, base_dir, False)
        if not dependency_probe.get("dependency_ready"):
            result = _run(
                [
                    paths["cloud_python"],
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    paths["requirements"],
                ],
                timeout=1200.0,
                cwd=paths["base_dir"],
            )
            steps.append(f"install_cloud_dependencies={result.returncode}")
            if result.returncode != 0:
                return "GAGAL memasang Azure Speech SDK:\n" + result.stdout[-5000:]
        self_test = _run(
            [paths["cloud_python"], paths["sidecar"], "--self-test-json"],
            timeout=45.0,
            cwd=paths["base_dir"],
        )
        steps.append(f"cloud_stream_self_test={self_test.returncode}")
        clear_cloud_probe_cache()
        final_probe = probe_cloud_runtime(True, base_dir, False)
        if not final_probe.get("dependency_ready"):
            return "Setup selesai sebagian, tetapi dependensi Azure belum lulus:\n" + cloud_runtime_summary_text(base_dir)
        return "\n".join([
            "Runtime Azure Live Media siap.",
            f"cloud_python = {paths['cloud_python']}",
            f"sdk_version = {final_probe.get('sdk_version', 'unknown')}",
            f"credential_set = {bool(final_probe.get('credential_set'))}",
            f"steps = {' | '.join(steps)}",
            "Masukkan region dan API key, lalu pilih Simpan & Uji Azure.",
        ])
    except subprocess.TimeoutExpired:
        return "GAGAL: Setup Azure melewati batas waktu. Periksa koneksi internet lalu coba kembali."
    except Exception as exc:
        return f"GAGAL setup Azure: {type(exc).__name__}: {exc}"
    finally:
        _SETUP_LOCK.release()


def cloud_runtime_summary_text(base_dir: Path | str = BASE_DIR) -> str:
    paths = cloud_runtime_paths(base_dir)
    probe = probe_cloud_runtime(False, base_dir, False)
    config = _load_json(paths["config"])
    lines = [
        f"status = {'READY' if probe.get('ready') else 'SETUP_REQUIRED'}",
        "provider = azure",
        f"cloud_runtime = {paths['cloud_python']}",
        f"sdk_ready = {bool(probe.get('sdk'))}",
        f"sdk_version = {probe.get('sdk_version', 'unknown')}",
        f"credential_store = {'READY' if probe.get('keyring') else 'NOT_READY'}",
        f"credential_set = {bool(probe.get('credential_set'))}",
        f"credential_source = {str(probe.get('credential_source') or 'none')}",
        f"region = {str(config.get('region') or probe.get('region') or '-')}",
        f"source_locale = {normalize_source_locale(str(config.get('source_locale') or 'ja-JP'))}",
        f"target_language = {normalize_target_language(str(config.get('target_language') or 'id'))}",
        f"wasapi_loopback = {bool(probe.get('wasapi'))}",
        f"cloud_connected = {bool(probe.get('cloud_connected'))}",
        f"network_tested = {bool(probe.get('network_tested'))}",
    ]
    for error in probe.get("errors") or []:
        lines.append("problem = " + str(error)[-1200:])
    return "\n".join(lines)


def cloud_device_choices(
    base_dir: Path | str = BASE_DIR,
    force: bool = False,
) -> Tuple[list[tuple[str, str]], str, str]:
    probe = probe_cloud_runtime(force, base_dir, False)
    paths = cloud_runtime_paths(base_dir)
    if not probe.get("dependency_ready"):
        return [("Default output · siapkan Azure dahulu", "-1")], "-1", str(probe.get("message") or "Runtime Azure belum siap.")
    if os.name != "nt":
        return [("WASAPI hanya tersedia di Windows", "-1")], "-1", "Audio internal Azure memerlukan Windows."
    try:
        result = _run(
            [paths["cloud_python"], paths["sidecar"], "--list-devices-json"],
            timeout=35.0,
            cwd=paths["base_dir"],
        )
        events = parse_cloud_events(result.stdout)
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
            return [("Default output (deteksi otomatis)", "-1")], "-1", "Perangkat spesifik belum ditemukan."
        if selected == "-1":
            selected = choices[0][1]
        return choices, selected, f"{len(choices)} perangkat WASAPI loopback ditemukan melalui runtime Azure."
    except Exception as exc:
        return [("Default output (deteksi otomatis)", "-1")], "-1", f"Deteksi perangkat Azure gagal: {exc}"


def resolve_audio_delivery(
    audio_engine: str,
    local_ready: bool,
    base_dir: Path | str = BASE_DIR,
    force: bool = False,
    network_test: bool = False,
) -> dict:
    requested = normalize_audio_engine(audio_engine)
    cloud_probe = probe_cloud_runtime(force, base_dir, bool(network_test)) if requested != "local" else {
        "ready": False,
        "cloud_connected": False,
        "network_tested": False,
        "message": "Azure tidak diperiksa pada mode Local.",
    }
    cloud_ready = bool(cloud_probe.get("ready"))
    if network_test:
        cloud_ready = bool(cloud_ready and cloud_probe.get("network_tested") and cloud_probe.get("cloud_connected"))
    decision = resolve_cloud_engine(requested, cloud_ready, bool(local_ready))
    return {
        **decision.as_dict(),
        "usage": normalize_audio_usage("live_media"),
        "network_test_required": bool(network_test),
        "cloud": cloud_probe,
    }
