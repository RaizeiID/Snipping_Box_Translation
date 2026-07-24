from __future__ import annotations
from pathlib import Path
import json, time

def recovery_report(base_dir=None) -> str:
    base = Path(base_dir or Path(__file__).resolve().parents[2])
    logs = sorted((base/"logs").glob("session_*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    lines = ["Session Recovery v8.0", "===================="]
    if not logs:
        lines.append("Tidak ada session log ditemukan.")
    else:
        lines.append(f"Last session artifact: {logs[0].name}")
        lines.append("Jika program ditutup paksa, jalankan Analyze Last Session untuk membaca log parsial.")
    (base/"status").mkdir(exist_ok=True)
    (base/"status"/"session_recovery.txt").write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)
