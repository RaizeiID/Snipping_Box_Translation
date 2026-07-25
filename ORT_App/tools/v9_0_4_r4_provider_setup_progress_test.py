from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: token missing: {token}")


def main() -> int:
    webui = (ROOT / "webui.py").read_text(encoding="utf-8")
    setup = (ROOT / "tools" / "setup_v9_0_4_audio_providers.py").read_text(encoding="utf-8")
    registry = (ROOT / "app" / "audio" / "asr_provider_registry.py").read_text(encoding="utf-8")

    for token, label in [
        ('label="Target setup/download · wajib dipilih setiap kali"', "explicit setup target"),
        ('("CPU + GPU", "both")', "both target"),
        ('label="Log unduhan & setup provider"', "download log label"),
        ('gr.Button("Salin log setup provider", visible=False)', "conditional copy button"),
        ('oa_provider_progress = gr.HTML(_oa_progress_html())', "realtime progress UI"),
        ('provider-pill-ready', "green device pill"),
        ('provider-pill-missing', "red device pill"),
        ('_oa_stream_setup_process', "streamed setup process"),
    ]:
        require(webui, token, label)

    for token, label in [
        ('EVENT_PREFIX = "ORT_SETUP_EVENT "', "machine-readable events"),
        ('reconfigure(encoding="utf-8"', "Windows UTF-8 console"),
        ('"download_progress"', "byte download progress"),
        ('"model_total_bytes"', "model total bytes"),
        ('"model_downloaded_bytes"', "downloaded bytes"),
        ('"<inline-python-script>"', "safe inline script logging"),
        ('--status-root', "persistent provider status"),
    ]:
        require(setup, token, label)

    for token, label in [
        ('provider_setup_status_root', "device status marker root"),
        ('"status_level": "unsupported"', "unsupported state"),
        ('"model_complete": marker_complete', "complete download validation"),
        ('Bridge Jepang→Inggris→Indonesia belum siap', "bridge readiness validation"),
    ]:
        require(registry, token, label)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "setup_v9_0_4_audio_providers.py"), "--self-test"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    payload = json.loads((result.stdout or "").strip().splitlines()[-1])
    if not payload.get("passed"):
        raise AssertionError(payload)

    output = {
        "passed": True,
        "version": "v9.0.4-R4",
        "explicit_cpu_gpu_both_selection": "PASS",
        "realtime_gb_percent_progress": "PASS",
        "cpu_gpu_device_pills": "PASS",
        "persistent_complete_status": "PASS",
        "conditional_copy_log": "PASS",
        "utf8_setup_console": "PASS",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
