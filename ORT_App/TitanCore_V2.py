# TitanCore_V2.py (bracket keys + safe runner)
from __future__ import annotations
import os, sys, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parent

@dataclass
class Entry:
    key: str
    title: str
    script: str
    desc: str
    group: str

def exists(name: str) -> bool:
    return (ROOT / name).exists()

def run_script(script: str) -> int:
    p = (ROOT / script).resolve()
    if not p.exists():
        print(f"[CORE] File not found: {p}")
        return 1
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.call([sys.executable, str(p)], cwd=str(ROOT), env=env)

def build_entries() -> List[Entry]:
    entries: List[Entry] = []
    k = 1
    def add(group: str, title: str, script: str, desc: str):
        nonlocal k
        if exists(script):
            entries.append(Entry(str(k), title, script, desc, group))
            k += 1

    add("Model Versi 1 (FAST)", "V1 Normal", "TitanMainV1.py", "Speed-first.")
    add("Model Versi 1 (FAST)", "V1 Lite", "TitanMainV1Lite.py", "Lightweight speed-first.")
    add("Model Versi 1 (FAST)", "V1 IDN", "TitanMainV1_IDN.py", "IDN Naturalize MAX.")
    add("Model Versi 1 (FAST)", "V1 Lite IDN", "TitanMainV1Lite_IDN.py", "Lite + IDN Naturalize MAX.")

    # keep other models as-is if exist
    add("Model Versi 2 (BALANCED)", "V2 Normal", "TitanMainV2.py", "Balanced.")
    add("Model Versi 2 (BALANCED)", "V2 IDN", "TitanMainV2_IDN.py", "Balanced + IDN.")
    add("Model Versi 2 (BALANCED)", "V2 Lite", "TitanMainV2Lite.py", "Lite: ringan + speed optimized.")
    add("Model Versi 2 (BALANCED)", "V2 Lite IDN", "TitanMainV2Lite_IDN.py", "Lite + IDN: ringan + speed optimized.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Normal", "TitanMainV3.py", "Accuracy-first.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Lite", "TitanMainV3Lite.py", "Lite.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 IDN", "TitanMainV3_IDN.py", "IDN.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Lite IDN", "TitanMainV3Lite_IDN.py", "Lite IDN.")
    add("Model Versi 4 (HYBRID)", "V4 Normal", "TitanMainV4.py", "Hybrid.")
    add("Model Versi 4 (HYBRID)", "V4 Lite", "TitanMainV4Lite.py", "Lite.")
    add("Model Versi 4 (HYBRID)", "V4 IDN", "TitanMainV4_IDN.py", "IDN.")
    add("Model Versi 4 (HYBRID)", "V4 Lite IDN", "TitanMainV4Lite_IDN.py", "Lite IDN.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Normal", "TitanMainV5.py", "Naturalization.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Lite", "TitanMainV5Lite.py", "Lite.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 IDN", "TitanMainV5_IDN.py", "IDN.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Lite IDN", "V5 Lite IDN", "TitanMainV5Lite_IDN.py")

    for s, d in [
        ("TITANMAIN.py", "Entry utama."),
        ("TITAN_ULTRA.py", "Ultra preset."),
        ("MODE_DEBUG.py", "Debug core."),
        ("TITAN_DOCTOR.py", "Doctor."),
        ("TITAN_DEBUG_MAIN.py", "Debug runner."),
        ("TITAN_LAUNCHER.py", "Launcher."),
    ]:
        if exists(s):
            add("EXTRAS", s, s, d)

    return entries

def print_table(entries: List[Entry]) -> None:
    groups: Dict[str, List[Entry]] = {}
    for e in entries:
        groups.setdefault(e.group, []).append(e)

    print("\n" + "=" * 78)
    print(" TITANCORE V2 — MODEL SELECTOR (V1..V5)".ljust(77) + " ")
    print("=" * 78)
    print(" NOTE: Jalankan 'python TITAN_PATCH_V1_ENGINE_FULL.py' untuk patch indikator/hotkey V1.\n")

    for g in ["Model Versi 1 (FAST)", "Model Versi 2 (BALANCED)", "Model Versi 3 (HEAVY ACCURACY)",
              "Model Versi 4 (HYBRID)", "Model Versi 5 (NATURALIZATION MAX)", "EXTRAS"]:
        if g not in groups:
            continue
        print(f"[{g}]")
        print("-" * 78)
        print(f"{'Key':<6} {'Title':<22} {'Script':<28} Description")
        print("-" * 78)
        for e in groups[g]:
            print(f"[{e.key}]  {e.title:<22} {e.script:<28} {e.desc}")
        print("")

    print("Commands:")
    print("  - ketik angka lalu Enter untuk menjalankan")
    print("  - q = keluar\n")

def main() -> None:
    os.chdir(ROOT)
    entries = build_entries()
    while True:
        print_table(entries)
        c = input("Select> ").strip().lower()
        if c in {"q","quit","exit"}:
            break
        found = None
        for e in entries:
            if e.key == c:
                found = e
                break
        if not found:
            print("[CORE] Pilihan tidak valid.\n")
            continue
        print(f"\n[CORE] Running: {found.script}\n")
        code = run_script(found.script)
        print(f"\n[CORE] Process exited with code {code}\n")
        input("Press Enter to return to menu...")

if __name__ == "__main__":
    main()