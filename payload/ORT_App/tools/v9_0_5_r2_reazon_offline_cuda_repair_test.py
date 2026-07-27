from __future__ import annotations

import tempfile
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))


def main() -> int:
    setup_path = APP_ROOT / "tools" / "setup_v9_0_4_audio_providers.py"
    setup = setup_path.read_text(encoding="utf-8")
    assert 'SETUP_VERSION = "v9.0.5"' in setup
    assert "ORT-v9.0.5-r3-provider-setup" in setup
    assert "_download_reazon_static(" in setup
    assert "Mode manifest langsung aktif" in setup
    install_start = setup.index("def install_reazon(")
    install_end = setup.index("def install_sensevoice", install_start)
    install_section = setup[install_start:install_end]
    assert "_download_hf_repo(" not in install_section
    assert "_download_reazon_static(" in install_section
    assert "install_cuda_dependencies=True" in install_section
    assert "nvidia-cufft-cu12" in setup
    assert "nvidia-cudnn-cu12" in setup

    from app.audio.windows_dll_resolver import locate_dlls
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        for name in ("cufft64_11.dll", "cudnn64_9.dll"):
            (folder / name).write_bytes(b"test")
        found = locate_dlls(("cufft64_11.dll", "cudnn64_9.dll", "missing.dll"), [folder])
        assert found["cufft64_11.dll"].endswith("cufft64_11.dll")
        assert found["cudnn64_9.dll"].endswith("cudnn64_9.dll")
        assert "missing.dll" not in found

    offline_tool = (APP_ROOT / "tools" / "reazon_offline_model_tool.py").read_text(encoding="utf-8")
    assert "snapshot_download" not in offline_tool
    assert "_download_reazon_static" in offline_tool
    assert "import_from_directory" in offline_tool

    compat = (APP_ROOT / "app" / "audio" / "sherpa_compat.py").read_text(encoding="utf-8")
    assert "register_windows_dll_directories" in compat
    assert "cufft64_11.dll" in compat
    print("ORT_V9_0_5_R2_REAZON_OFFLINE_CUDA_REPAIR: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
