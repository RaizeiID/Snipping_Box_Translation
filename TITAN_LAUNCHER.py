# -*- coding: utf-8 -*-
"""
TITAN_LAUNCHER.py

UPDATE NOTES (2026-01-06)
- NEW: Terminal launcher menu untuk menjalankan semua model Titan secara interaktif.
  - Pilih model dengan nomor (bisa multi pilihan: "5,6,7").
  - Bisa juga pakai alias: v1, v2, v3a, v3b, v3c, v3litea, v4idn, dll.
  - Setelah program berhenti, launcher kembali ke menu (bisa jalankan model lain berurutan).
- NEW: Built-in help ringkas + link ke TITAN_MODELS_GUIDE.md untuk penjelasan lengkap.

Cara pakai:
- Jalankan:  python TITAN_LAUNCHER.py
- Atau:      Run_TITAN_LAUNCHER.cmd / .ps1

Catatan:
- Launcher ini tidak mengubah cara kerja model; hanya menjalankan file yang sudah ada.
- Jika sebuah file tidak ada, item itu otomatis ditandai "MISSING".
"""

from __future__ import annotations

import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE = Path(__file__).resolve().parent

@dataclass
class ModelEntry:
    key: str                 # unique id, used internally
    title: str               # display
    filename: str            # python file to run
    short: str               # short description
    aliases: Tuple[str, ...] # input aliases

def _exists(filename: str) -> bool:
    return (BASE / filename).exists()

def _py_exec() -> str:
    # Prefer current interpreter
    return sys.executable if sys.executable else "python"

def _clear() -> None:
    try:
        if os.name == "nt":
            os.system("cls")
        else:
            os.system("clear")
    except Exception:
        pass

def _print_header() -> None:
    print("="*78)
    print(" TITAN LAUNCHER  |  pilih model (V1..V4, V3Lite, IDN, Option A/B/C)")
    print(" (ketik 'help' untuk penjelasan singkat / 'guide' buka file panduan)")
    print("="*78)

def _models() -> List[ModelEntry]:
    # NOTE: update list here if you add new scripts
    return [
        ModelEntry("v1",        "Titan V1 (FAST)",                  "TitanMainV1.py",
                   "Sangat cepat, akurasi bisa lebih rendah.", ("v1","1")),
        ModelEntry("v1_idn",    "Titan V1_IDN (FAST + Natural)",    "TitanMainV1_IDN.py",
                   "V1 + naturalisasi Bahasa Indonesia.", ("v1idn","v1_idn","1idn")),

        ModelEntry("v2",        "Titan V2 (STABLE)",                "TitanMainV2.py",
                   "Stabil, lebih lengkap dari V1.", ("v2","2")),
        ModelEntry("v2_idn",    "Titan V2_IDN (STABLE + Natural)",  "TitanMainV2_IDN.py",
                   "V2 + naturalisasi Bahasa Indonesia.", ("v2idn","v2_idn","2idn")),

        ModelEntry("v3_base",   "Titan V3 (HYBRID BASE)",           "TitanMainV3.py",
                   "Hybrid core (base).", ("v3","v3base","3")),
        ModelEntry("v3a",       "Titan V3 Option A (MS+PING framed)","TitanMainV3_OptionA_FRAMED.py",
                   "MS+PING + engine detect (lebih lengkap).", ("v3a","3a","v3 a")),
        ModelEntry("v3b",       "Titan V3 Option B (MS only)",      "TitanMainV3_OptionB_FRAMED.py",
                   "MS only (lebih ringan).", ("v3b","3b","v3 b")),
        ModelEntry("v3c",       "Titan V3 Option C (A+B hybrid)",   "TitanMainV3_OptionC_FRAMED.py",
                   "Gabungan A+B (seimbang).", ("v3c","3c","v3 c")),
        ModelEntry("v3_idn",    "Titan V3_IDN (Hybrid + Natural)",  "TitanMainV3_IDN.py",
                   "V3 + naturalisasi Indonesia (default Option C).", ("v3idn","v3_idn")),

        ModelEntry("v3lite",    "Titan V3Lite (HYBRID LITE BASE)",  "TitanMainV3Lite.py",
                   "Hybrid lite (lebih ringan).", ("v3lite","3lite","v3l")),
        ModelEntry("v3litea",   "Titan V3Lite Option A (MS+PING)",  "TitanMainV3Lite_OptionA_FRAMED.py",
                   "MS+PING (framed).", ("v3litea","3litea","v3l a")),
        ModelEntry("v3liteb",   "Titan V3Lite Option B (MS only)",  "TitanMainV3Lite_OptionB_FRAMED.py",
                   "MS only (framed).", ("v3liteb","3liteb","v3l b")),
        ModelEntry("v3litec",   "Titan V3Lite Option C (A+B)",      "TitanMainV3Lite_OptionC_FRAMED.py",
                   "Gabungan A+B (framed).", ("v3litec","3litec","v3l c")),
        ModelEntry("v3lite_idn","Titan V3Lite_IDN (Lite + Natural)","TitanMainV3Lite_IDN.py",
                   "V3Lite + naturalisasi Indonesia.", ("v3liteidn","v3lite_idn","v3lidn")),

        ModelEntry("v4",        "Titan V4 (NEW)",                   "TitanMainV4.py",
                   "V4 (generasi baru/eksperimen).", ("v4","4")),
        ModelEntry("v4_idn",    "Titan V4_IDN (V4 + Natural)",      "TitanMainV4_IDN.py",
                   "V4 + naturalisasi Indonesia + MS/PING framed.", ("v4idn","v4_idn","4idn")),
    ]

def _index(models: List[ModelEntry]) -> Dict[str, ModelEntry]:
    idx: Dict[str, ModelEntry] = {}
    for m in models:
        idx[m.key] = m
        for a in m.aliases:
            idx[a.strip().lower()] = m
    return idx

def _print_menu(models: List[ModelEntry]) -> None:
    print("")
    print("Daftar model:")
    print("-"*78)
    for i, m in enumerate(models, start=1):
        status = "OK" if _exists(m.filename) else "MISSING"
        tag = f"[{status}]"
        print(f"{i:>2}. {m.title:<38} {tag:<9}  -> {m.short}")
    print("-"*78)
    print("Input contoh:")
    print(" - 6            (jalankan item nomor 6)")
    print(" - 6,7,8        (jalankan berurutan 6 lalu 7 lalu 8)")
    print(" - v3a          (alias: jalankan V3 Option A)")
    print(" - v4idn        (alias: jalankan V4_IDN)")
    print(" - help         (penjelasan singkat)")
    print(" - guide        (buka TITAN_MODELS_GUIDE.md)")
    print(" - q            (keluar)")
    print("")

def _open_guide() -> None:
    guide = BASE / "TITAN_MODELS_GUIDE.md"
    if not guide.exists():
        print("[!] TITAN_MODELS_GUIDE.md tidak ditemukan.")
        return
    try:
        if os.name == "nt":
            os.startfile(str(guide))  # type: ignore[attr-defined]
        else:
            print(str(guide))
    except Exception:
        print(str(guide))

def _help() -> None:
    print("")
    print("Ringkas model:")
    print(" - V1: paling cepat, cocok untuk teks pendek / butuh low latency, akurasi bisa turun.")
    print(" - V2: stabil, fitur lebih matang dibanding V1.")
    print(" - V3: hybrid router (online/offline/cache), ada opsi A/B/C dan versi Lite.")
    print("   * Option A: MS+PING framed (lebih lengkap)")
    print("   * Option B: MS only (lebih ringan)")
    print("   * Option C: gabungan A+B (seimbang)")
    print(" - V4: versi eksperimen generasi baru (bisa berubah sesuai update).")
    print("Varian *_IDN: hasil terjemahan diproses agar lebih natural untuk pembaca Indonesia.")
    print("Baca detail: TITAN_MODELS_GUIDE.md")
    print("")

def _run_model(m: ModelEntry) -> int:
    script = BASE / m.filename
    if not script.exists():
        print(f"[!] File tidak ditemukan: {m.filename}")
        return 2

    cmd = [_py_exec(), "-u", str(script)]
    print("")
    print(f">>> RUN: {m.title}")
    print(">>> CMD:", " ".join(cmd))
    print("")

    try:
        p = subprocess.Popen(cmd, cwd=str(BASE))
        rc = p.wait()
        print("")
        print(f"<<< EXIT: {m.title} (code={rc})")
        return int(rc)
    except KeyboardInterrupt:
        print("\n[!] Dihentikan user (Ctrl+C).")
        return 130
    except Exception as e:
        print(f"[!] Gagal menjalankan: {e}")
        return 1

def _parse_multi_numbers(s: str) -> Optional[List[int]]:
    # "1,2,3" or "1 2 3"
    raw = s.replace(",", " ").strip()
    if not raw:
        return None
    parts = [p for p in raw.split() if p.strip()]
    if not parts:
        return None
    out: List[int] = []
    for p in parts:
        if not p.isdigit():
            return None
        out.append(int(p))
    return out

def main() -> int:
    models = _models()
    idx = _index(models)

    while True:
        _clear()
        _print_header()
        _print_menu(models)

        try:
            choice = input("Pilih model (nomor/alias): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0

        c = choice.strip().lower()
        if not c:
            continue
        if c in ("q","quit","exit"):
            return 0
        if c in ("help","h","?"):
            _help()
            input("Enter untuk kembali ke menu...")
            continue
        if c in ("guide","doc","docs"):
            _open_guide()
            input("Enter untuk kembali ke menu...")
            continue

        # multi number?
        nums = _parse_multi_numbers(c)
        if nums is not None:
            # run sequential
            for n in nums:
                if n < 1 or n > len(models):
                    print(f"[!] Nomor tidak valid: {n}")
                    input("Enter...")
                    break
                rc = _run_model(models[n-1])
                input("Enter untuk lanjut ke model berikut / kembali...")
            continue

        # alias
        m = idx.get(c, None)
        if m is None:
            print("[!] Input tidak dikenali. Ketik 'help' atau lihat menu.")
            input("Enter...")
            continue

        _run_model(m)
        input("Enter untuk kembali ke menu...")

if __name__ == "__main__":
    raise SystemExit(main())
