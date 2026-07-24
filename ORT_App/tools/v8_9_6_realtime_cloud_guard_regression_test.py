#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

import audio_cloud_backend
from build_info import APP_VERSION_TAG, RELEASE_NAME


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_release_identity() -> None:
    assert_true(APP_VERSION_TAG == "v8.9.6", f"unexpected version: {APP_VERSION_TAG}")
    assert_true(RELEASE_NAME == "Real-Time Cloud Enforcement Update", f"unexpected release: {RELEASE_NAME}")
    for path in (ROOT / "ORTCORE_VERSION.txt", ROOT / "TITANCORE_VERSION.txt", PROJECT_ROOT / "VERSION.txt"):
        assert_true(path.read_text(encoding="utf-8").strip() == APP_VERSION_TAG, f"version mismatch: {path}")


def test_network_test_controls_cloud_readiness() -> None:
    original = audio_cloud_backend.probe_cloud_runtime
    try:
        audio_cloud_backend.probe_cloud_runtime = lambda *_args, **_kwargs: {
            "installed": True,
            "sdk": True,
            "keyring": True,
            "wasapi": True,
            "credential_set": True,
            "region": "southeastasia",
            "ready": True,
            "network_tested": True,
            "cloud_connected": False,
        }
        blocked = audio_cloud_backend.resolve_audio_delivery(
            "azure_fallback", True, ROOT, force=True, network_test=True
        )
        assert_true(blocked["effective"] == "local_guard", f"unexpected disconnected decision: {blocked}")
        assert_true(not blocked["cloud_ready"], "disconnected Azure was treated as ready")

        audio_cloud_backend.probe_cloud_runtime = lambda *_args, **_kwargs: {
            "installed": True,
            "sdk": True,
            "keyring": True,
            "wasapi": True,
            "credential_set": True,
            "region": "southeastasia",
            "ready": True,
            "network_tested": True,
            "cloud_connected": True,
        }
        active = audio_cloud_backend.resolve_audio_delivery(
            "azure_fallback", True, ROOT, force=True, network_test=True
        )
        assert_true(active["effective"] == "azure", f"connected Azure was not selected: {active}")
        assert_true(active["cloud_ready"], "connected Azure was not ready")
    finally:
        audio_cloud_backend.probe_cloud_runtime = original


def test_launcher_refuses_startup_local_guard() -> None:
    source = (ROOT / "launcher_backend.py").read_text(encoding="utf-8")
    required = [
        "strict_realtime_cloud",
        "MODE LIVE MEDIA REAL-TIME TIDAK DIMULAI",
        "REALTIME BLOCKED",
        "network_test=strict_realtime_cloud",
        "Fallback lokal hanya digunakan apabila cloud terputus setelah sesi real-time sudah berjalan",
    ]
    for marker in required:
        assert_true(marker in source, f"missing launcher guard marker: {marker}")


def main() -> int:
    test_release_identity()
    test_network_test_controls_cloud_readiness()
    test_launcher_refuses_startup_local_guard()
    print("v8.9.6 Real-Time Cloud Guard regression PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
