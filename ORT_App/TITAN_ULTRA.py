# TITAN_ULTRA.py
# Ultra preset runner for TITAN Translator.
#
# What this does:
# - Tries to enable CT2 (CTranslate2) fast offline translation if the CT2 model folders exist.
# - If CT2 models are missing, it will NOT crash; it will fallback to normal TITANMAIN flow.
#
# Env overrides (optional):
#   - TITAN_CT2_EN_ID_DIR : path to CT2 en->id model directory
#   - TITAN_CT2_ZH_EN_DIR : path to CT2 zh->en model directory
#
# (c) TITAN project - open source friendly behavior

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

VERSION = "v1.1-CT2-FALLBACK"
DATE = "2026-01-06"


def _stdout_utf8() -> None:
    """Prevent Windows cp1252 crash when printing unicode icons."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _env_path(var: str, default: Path) -> str:
    v = os.environ.get(var, "").strip().strip('"')
    return v if v else str(default)


def _dir_ok(path: str) -> bool:
    try:
        p = Path(path)
        return p.is_dir() and any(p.iterdir())
    except Exception:
        return False


def _run_titanmain(base_dir: Path) -> int:
    """Run TITANMAIN in a way that works both as module and as script."""
    try:
        import TITANMAIN  # type: ignore

        if hasattr(TITANMAIN, "main"):
            return int(TITANMAIN.main())  # type: ignore[arg-type]
    except Exception:
        # fallback to run file
        pass

    titanmain_path = base_dir / "TITANMAIN.py"
    if titanmain_path.exists():
        runpy.run_path(str(titanmain_path), run_name="__main__")
        return 0

    print("[FATAL] TITANMAIN.py tidak ditemukan.")
    return 2


def main() -> int:
    _stdout_utf8()

    base_dir = Path(__file__).resolve().parent

    print("TITAN_ULTRA preset (CT2 best-effort) |", VERSION, "|", DATE)

    # Lazy imports so fallback still works if CT2 deps missing.
    fast_translator = None
    cfg = None

    try:
        from fast_mt_core_ct2 import CT2Config, FastCT2Translator  # type: ignore

        cfg = CT2Config(
            model_dir_en_id=_env_path("TITAN_CT2_EN_ID_DIR", base_dir / "models" / "ct2_opus_mt_en_id"),
            model_dir_zh_en=_env_path("TITAN_CT2_ZH_EN_DIR", base_dir / "models" / "ct2_opus_mt_zh_en"),
        )

        missing = []
        if not _dir_ok(cfg.model_dir_en_id):
            missing.append(f"en->id: {cfg.model_dir_en_id}")
        if not _dir_ok(cfg.model_dir_zh_en):
            missing.append(f"zh->en: {cfg.model_dir_zh_en}")

        if missing:
            print("[WARN] CT2 model folder tidak ditemukan:")
            for m in missing:
                print(" -", m)
            print("[WARN] Fallback: lanjut pakai engine default (tanpa CT2).")
            print("[HINT] Jika ingin CT2 aktif, taruh model CT2 di folder tersebut, atau set env TITAN_CT2_EN_ID_DIR / TITAN_CT2_ZH_EN_DIR ke lokasi model.")
        else:
            try:
                fast_translator = FastCT2Translator(cfg)
                import fast_translator_monkeypatch  # type: ignore

                fast_translator_monkeypatch.install(fast_translator)
                print("[OK] CT2 enabled: Fast offline translation aktif.")
            except Exception as e:
                print("[WARN] Gagal mengaktifkan CT2 (fallback ke default).")
                print("       Error:", repr(e))

    except Exception as e:
        # CT2 dependency not available; just fallback.
        print("[WARN] CT2 core tidak tersedia / error import (fallback ke default).")
        print("       Error:", repr(e))

    return _run_titanmain(base_dir)


if __name__ == "__main__":
    raise SystemExit(main())
