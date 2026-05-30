# -*- coding: utf-8 -*-
"""TITAN_LAUNCHER.py - ORT Translation v7.8 terminal launcher.

Launcher ini memakai model_registry.py sebagai sumber tunggal daftar model.
Untuk penggunaan normal, jalankan Start_ORT_Translation.bat dan pilih model dari WebUI.
Launcher terminal ini disediakan untuk testing cepat tanpa membuka WebUI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from model_registry import GROUP_LABELS, available_model_choices, get_model_by_title, list_models
from v7_system_profile import env_from_settings, game_choices, recommendation_text

BASE = Path(__file__).resolve().parent


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _py_exec() -> str:
    return sys.executable or "python"


def _print_header() -> None:
    print("=" * 84)
    print(" ORT Translation v7.8 Terminal Launcher")
    print(" Model: Normal / Lite / IDN / Lite IDN / Fast | Game Profile: GFL2 / WUWA / Custom")
    print("=" * 84)


def _model_rows() -> List[str]:
    rows: List[str] = []
    n = 1
    for group_key, group_label in GROUP_LABELS.items():
        rows.append(f"\n[{group_label}]")
        for m in list_models(group_key):
            ok = "OK" if (BASE / m.script).exists() else "MISSING"
            rows.append(f" {n:>2}. {m.title:<24} [{ok}]  {m.summary}")
            n += 1
    return rows


def _flat_models():
    out = []
    for g in GROUP_LABELS:
        out.extend(list_models(g))
    return out


def _ask_game() -> str:
    choices = game_choices()
    print("\nPilih game profile:")
    for i, (label, key) in enumerate(choices, 1):
        print(f" {i}. {label} ({key})")
    raw = input("Game [1=GFL2, 2=WUWA, 3=Custom]: ").strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx][1]
    raw_u = raw.upper()
    valid = {key for _, key in choices}
    return raw_u if raw_u in valid else "GFL2_EXILIUM"


def _ask_policy(game: str) -> str:
    print("\nKebijakan performa:")
    print(" 1. Auto rekomendasi")
    print(" 2. Safe Game")
    print(" 3. Balanced")
    print(" 4. Normal override")
    raw = input("Policy [1]: ").strip()
    return {"2": "safe_game", "3": "balanced", "4": "normal"}.get(raw, "auto")


def _run_model(title: str, game: str, policy: str) -> int:
    model = get_model_by_title(title)
    script = BASE / model.script
    if not script.exists():
        print(f"[!] Target script tidak ditemukan: {script}")
        return 2

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["ORT_GAME_OVERRIDE"] = game
    env["ORT_BOOT_MODE"] = model.default_mode
    env["ORT_BOOT_ENGINE"] = model.default_engine
    env["ORT_BOOT_INTERVAL_MS"] = str(model.default_interval_ms)
    env["ORT_BOOT_OCR_RESOLUTION"] = str(model.ocr_resolution_percent)
    env.update(model.env_map())
    env.update(env_from_settings(game, model_key=model.key, policy_override=policy, ocr_resolution=model.ocr_resolution_percent))

    print("\n>>> RUN")
    print(f"Model  : {model.title}")
    print(f"Game   : {game}")
    print(f"Policy : {policy}")
    print(f"Script : {model.script}")
    print("-" * 84)
    return subprocess.call([_py_exec(), "-u", str(script)], cwd=str(BASE), env=env)


def main() -> int:
    flat = _flat_models()
    while True:
        _clear()
        _print_header()
        print("\n".join(_model_rows()))
        print("\nKetik nomor model, nama model, 'rec' untuk rekomendasi, atau 'q' untuk keluar.")
        raw = input("Pilih model: ").strip()
        if not raw:
            continue
        if raw.lower() in {"q", "quit", "exit"}:
            return 0
        if raw.lower() == "rec":
            game = _ask_game()
            policy = _ask_policy(game)
            print("\n" + recommendation_text(game, allow_normal=(policy == "normal")))
            input("\nEnter untuk kembali...")
            continue

        try:
            if raw.isdigit():
                idx = int(raw) - 1
                if not (0 <= idx < len(flat)):
                    raise ValueError("Nomor di luar daftar")
                title = flat[idx].title
            else:
                title = raw
                get_model_by_title(title)  # validate / alias support
        except Exception as exc:
            print(f"[!] Pilihan tidak valid: {exc}")
            input("Enter...")
            continue

        game = _ask_game()
        policy = _ask_policy(game)
        rc = _run_model(title, game, policy)
        print(f"\n<<< EXIT code={rc}")
        input("Enter untuk kembali...")


if __name__ == "__main__":
    raise SystemExit(main())
