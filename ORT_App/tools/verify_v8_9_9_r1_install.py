from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
EXPECTED_VERSION = "v8.9.9"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").strip() if path.is_file() else ""


def main() -> int:
    versions = {
        "root": read_text(PROJECT_ROOT / "VERSION.txt"),
        "ortcore": read_text(ROOT / "ORTCORE_VERSION.txt"),
        "titancore": read_text(ROOT / "TITANCORE_VERSION.txt"),
    }
    audio = read_text(ROOT / "audio_main.py")
    sidecar = read_text(ROOT / "audio_realtime_local_sidecar.py")
    build = read_text(ROOT / "build_info.py")
    launcher = read_text(ROOT / "launcher_backend.py")
    checks = {
        "versions_match_v899": all(value == EXPECTED_VERSION for value in versions.values()),
        "preview_visible_default": 'ORT_AUDIO_SHOW_SOURCE", "1"' in audio,
        "preview_label": "Preview EN:" in audio,
        "launcher_preview_enabled": 'ORT_AUDIO_SHOW_SOURCE"] = "1"' in launcher,
        "dual_stream": "JAPANESE_DUAL_STREAM_ACTIVE" in sidecar,
        "fast_preview_model": "FAST_PREVIEW_MODEL_READY" in sidecar,
        "background_correction_opt_in": "ORT_AUDIO_BACKGROUND_SPECIALIST_CORRECTION" in sidecar,
        "r1_build_channel": "v8-9-9-r1-preview-cpu-dual-stream" in build,
    }
    payload = {"passed": all(checks.values()), "versions": versions, "checks": checks}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
