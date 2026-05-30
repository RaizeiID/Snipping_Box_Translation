# TITAN_PATCH_BUILD_V5.py
# One-click patcher:
# - Creates Model V1..V5 (Normal/Lite/IDN)
# - Adds universal HUD indicators: GAME + INTERVAL + MS (no PING)
# - Updates TitanCore_V2.py into categorized table menu + descriptions
# - Outputs: AI_Translation_V5_Patched.zip
#
# Safe/Idempotent:
# - Will not overwrite legacy engines if already moved
# - Keeps old V3 router as TitanMainV3_LEGACY_ROUTER.py
# - Keeps old V4 online as TitanMainV4_LEGACY_ONLINE.py (used by V5 for now)

from __future__ import annotations

import os
import sys
import re
import json
import time
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent

OUT_ZIP = ROOT / "AI_Translation_V5_Patched.zip"
BACKUP_DIR = ROOT / f"_backup_before_v5_patch_{time.strftime('%Y%m%d_%H%M%S')}"

def log(msg: str) -> None:
    print(f"[PATCH] {msg}")

def safe_move(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    if dst.exists():
        return False
    src.rename(dst)
    return True

def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def backup_project() -> None:
    # lightweight backup: copy only .py/.json/.txt/.md/.bat/.ps1 and small assets
    log(f"Creating backup folder: {BACKUP_DIR.name}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    exts = {".py", ".json", ".txt", ".md", ".bat", ".ps1", ".ini", ".cfg"}
    for p in ROOT.rglob("*"):
        if p.is_dir():
            if p.name in {"__pycache__", ".git", BACKUP_DIR.name}:
                continue
            continue
        if BACKUP_DIR in p.parents:
            continue
        if p.suffix.lower() in exts:
            rel = p.relative_to(ROOT)
            dest = BACKUP_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
    log("Backup done.")

def ensure_hud_module() -> None:
    hud_path = ROOT / "TitanMiniHUD.py"
    if hud_path.exists():
        return

    write_text(hud_path, HUD_MODULE)
    log("Created TitanMiniHUD.py (HUD indicators: GAME + INTERVAL + MS)")

def ensure_new_models_and_legacy() -> None:
    """
    Strategy:
    - Preserve old V3 router: TitanMainV3.py -> TitanMainV3_LEGACY_ROUTER.py
    - Preserve old V3Lite if exists: TitanMainV3Lite.py -> TitanMainV3Lite_LEGACY.py
    - Preserve old V4 online: TitanMainV4.py -> TitanMainV4_LEGACY_ONLINE.py
    - Wrap V1 and V2 with HUD:
        TitanMainV1.py -> TitanMainV1_ENGINE.py ; new TitanMainV1.py wrapper runs ENGINE + HUD
        TitanMainV2.py -> TitanMainV2_ENGINE.py ; new TitanMainV2.py wrapper runs ENGINE + HUD
    - Create NEW:
        TitanMainV3.py  (heavy accuracy; runs TITAN_ULTRA if exists else V2_ENGINE)
        TitanMainV3Lite.py
        TitanMainV4.py  (hybrid placeholder; runs V2_ENGINE with env TITAN_HYBRID=1)
        TitanMainV4Lite.py
        TitanMainV5.py  (for now uses legacy V4 online engine as "V5 naturalization base")
        TitanMainV5Lite.py
      + IDN wrappers for V3/V4/V5 normal+lite
    """
    # Preserve old V3 router (if exists and not already preserved)
    v3 = ROOT / "TitanMainV3.py"
    if v3.exists() and not (ROOT / "TitanMainV3_LEGACY_ROUTER.py").exists():
        safe_move(v3, ROOT / "TitanMainV3_LEGACY_ROUTER.py")
        log("Moved TitanMainV3.py -> TitanMainV3_LEGACY_ROUTER.py (kept for reference)")

    v3lite = ROOT / "TitanMainV3Lite.py"
    if v3lite.exists() and not (ROOT / "TitanMainV3Lite_LEGACY.py").exists():
        safe_move(v3lite, ROOT / "TitanMainV3Lite_LEGACY.py")
        log("Moved TitanMainV3Lite.py -> TitanMainV3Lite_LEGACY.py (kept for reference)")

    # Preserve old V4 online (if exists and not already preserved)
    v4 = ROOT / "TitanMainV4.py"
    if v4.exists() and not (ROOT / "TitanMainV4_LEGACY_ONLINE.py").exists():
        safe_move(v4, ROOT / "TitanMainV4_LEGACY_ONLINE.py")
        log("Moved TitanMainV4.py -> TitanMainV4_LEGACY_ONLINE.py (used by V5 for now)")

    # Wrap V1
    v1 = ROOT / "TitanMainV1.py"
    if v1.exists() and not (ROOT / "TitanMainV1_ENGINE.py").exists():
        safe_move(v1, ROOT / "TitanMainV1_ENGINE.py")
        write_text(ROOT / "TitanMainV1.py", MODEL_WRAPPER_TEMPLATE.format(
            target="TitanMainV1_ENGINE.py",
            preset="V1",
            label="V1 FAST (Speed First)",
            interval=150,
            extra_env="{}",
        ))
        log("Wrapped TitanMainV1.py with HUD (engine moved to TitanMainV1_ENGINE.py)")

    # Wrap V2
    v2 = ROOT / "TitanMainV2.py"
    if v2.exists() and not (ROOT / "TitanMainV2_ENGINE.py").exists():
        safe_move(v2, ROOT / "TitanMainV2_ENGINE.py")
        write_text(ROOT / "TitanMainV2.py", MODEL_WRAPPER_TEMPLATE.format(
            target="TitanMainV2_ENGINE.py",
            preset="V2",
            label="V2 BALANCED (Speed + Accuracy)",
            interval=200,
            extra_env="{}",
        ))
        log("Wrapped TitanMainV2.py with HUD (engine moved to TitanMainV2_ENGINE.py)")

    # Create new V3/V4/V5 files (overwrites if already our wrapper; safe if not)
    # V3 heavy: prefer TITAN_ULTRA if exists, else V2_ENGINE.
    v3_target = "TITAN_ULTRA.py" if (ROOT / "TITAN_ULTRA.py").exists() else "TitanMainV2_ENGINE.py"
    write_text(ROOT / "TitanMainV3.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v3_target,
        preset="V3",
        label="V3 HEAVY (Accuracy First, Slow)",
        interval=300,
        extra_env=str({"TITAN_ACCURACY_FIRST": "1"}),
    ))
    # V3 Lite
    write_text(ROOT / "TitanMainV3Lite.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v3_target,
        preset="V3L",
        label="V3 LITE (Accuracy-ish, Lightweight)",
        interval=320,
        extra_env=str({"TITAN_LITE": "1", "TITAN_ACCURACY_FIRST": "1"}),
    ))

    # V4 hybrid placeholder: runs V2 engine with hybrid flags
    v2_engine = "TitanMainV2_ENGINE.py" if (ROOT / "TitanMainV2_ENGINE.py").exists() else "TitanMainV2.py"
    write_text(ROOT / "TitanMainV4.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v2_engine,
        preset="V4",
        label="V4 HYBRID (Fast First + Accurate Later) [Placeholder Flags]",
        interval=220,
        extra_env=str({"TITAN_HYBRID": "1"}),
    ))
    write_text(ROOT / "TitanMainV4Lite.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v2_engine,
        preset="V4L",
        label="V4 LITE (Hybrid-ish, Lightweight) [Placeholder Flags]",
        interval=240,
        extra_env=str({"TITAN_LITE": "1", "TITAN_HYBRID": "1"}),
    ))

    # V5 uses legacy V4 online engine for now (your request)
    v5_base = "TitanMainV4_LEGACY_ONLINE.py" if (ROOT / "TitanMainV4_LEGACY_ONLINE.py").exists() else v2_engine
    write_text(ROOT / "TitanMainV5.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v5_base,
        preset="V5",
        label="V5 NATURAL (Max IDN Naturalization) [Currently: Legacy V4 Base]",
        interval=220,
        extra_env=str({"TITAN_NATURALIZE_MAX": "1"}),
    ))
    write_text(ROOT / "TitanMainV5Lite.py", MODEL_WRAPPER_TEMPLATE.format(
        target=v5_base,
        preset="V5L",
        label="V5 LITE (Naturalization-ish, Lightweight) [Currently: Legacy V4 Base]",
        interval=240,
        extra_env=str({"TITAN_LITE": "1", "TITAN_NATURALIZE_MAX": "1"}),
    ))

    # Create IDN wrappers for V3/V4/V5 normal+lite
    for base_name in ["TitanMainV3", "TitanMainV3Lite", "TitanMainV4", "TitanMainV4Lite", "TitanMainV5", "TitanMainV5Lite"]:
        p = ROOT / f"{base_name}_IDN.py"
        write_text(p, IDN_WRAPPER_TEMPLATE.format(target=f"{base_name}.py"))

    log("Created/Updated: V3/V4/V5 model scripts + IDN variants (normal & lite).")

def patch_existing_idn_wrappers_pointing_to_old_v4() -> None:
    # If there are old IDN scripts referencing TitanMainV4.py, and we moved it,
    # rewrite those references to TitanMainV4_LEGACY_ONLINE.py.
    legacy_v4 = ROOT / "TitanMainV4_LEGACY_ONLINE.py"
    if not legacy_v4.exists():
        return

    pat = re.compile(r'(["\'])TitanMainV4\.py\1')
    for p in ROOT.glob("TitanMainV*_IDN.py"):
        try:
            txt = read_text(p)
        except Exception:
            continue
        if "TitanMainV4.py" in txt:
            new_txt = pat.sub(r'\1TitanMainV4_LEGACY_ONLINE.py\1', txt)
            if new_txt != txt:
                write_text(p, new_txt)
                log(f"Patched reference in {p.name}: TitanMainV4.py -> TitanMainV4_LEGACY_ONLINE.py")

def update_titancore_v2() -> None:
    core = ROOT / "TitanCore_V2.py"
    write_text(core, TITANCORE_V2_NEW)
    log("Updated TitanCore_V2.py (categorized table menu + descriptions).")

def build_zip() -> None:
    # Remove old output zip if exists
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    log(f"Building ZIP: {OUT_ZIP.name}")
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob("*"):
            if p.is_dir():
                if p.name in {"__pycache__", ".git", BACKUP_DIR.name}:
                    continue
                continue
            if p == OUT_ZIP:
                continue
            if BACKUP_DIR in p.parents:
                continue
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(ROOT)
            z.write(p, rel.as_posix())
    log("ZIP build complete.")

def main() -> None:
    os.chdir(ROOT)

    log(f"Root: {ROOT}")
    backup_project()
    ensure_hud_module()
    ensure_new_models_and_legacy()
    patch_existing_idn_wrappers_pointing_to_old_v4()
    update_titancore_v2()
    build_zip()

    print("\nDONE ✅")
    print(f"- Backup folder: {BACKUP_DIR.name}")
    print(f"- Output ZIP: {OUT_ZIP.name}")
    print("\nJalankan menu:")
    print("  python TitanCore_V2.py")

# -------------------------- Embedded Modules --------------------------

MODEL_WRAPPER_TEMPLATE = r'''# Auto-generated wrapper by TITAN_PATCH_BUILD_V5.py
# Provides HUD indicators (GAME + INTERVAL + MS) for this model.

import os
import sys
from pathlib import Path

try:
    from TitanMiniHUD import run_with_hud
except Exception as e:
    print("[HUD] Failed to import TitanMiniHUD:", e)
    run_with_hud = None

def main():
    root = Path(__file__).resolve().parent

    target = "{target}"
    target_path = (root / target).resolve()
    if not target_path.exists():
        print("[MODEL] Target script not found:", target_path)
        print("[MODEL] Aborting.")
        raise SystemExit(1)

    env = os.environ.copy()
    env.setdefault("TITAN_MODEL_PRESET", "{preset}")
    env.setdefault("TITAN_MODEL_LABEL", "{label}")
    env.setdefault("TITAN_CAPTURE_INTERVAL_MS", str({interval}))
    extra = {extra_env}
    if isinstance(extra, dict):
        for k, v in extra.items():
            env[str(k)] = str(v)

    if run_with_hud is None:
        # fallback: just run the target
        import subprocess
        raise SystemExit(subprocess.call([sys.executable, str(target_path)], env=env))

    raise SystemExit(run_with_hud(
        target_script=str(target_path),
        env=env,
    ))

if __name__ == "__main__":
    main()
'''

IDN_WRAPPER_TEMPLATE = r'''# Auto-generated IDN wrapper by TITAN_PATCH_BUILD_V5.py
# Forces IDN mode env flags, then runs the target model wrapper.

import os
import sys
from pathlib import Path
import subprocess

def main():
    root = Path(__file__).resolve().parent
    target = "{target}"
    target_path = (root / target).resolve()
    if not target_path.exists():
        print("[IDN] Target script not found:", target_path)
        raise SystemExit(1)

    env = os.environ.copy()
    env["TITAN_IDN_MODE"] = "1"
    env.setdefault("TITAN_IDN_HINT", "1")  # soft flag, engine may ignore

    raise SystemExit(subprocess.call([sys.executable, str(target_path)], env=env))

if __name__ == "__main__":
    main()
'''

HUD_MODULE = r'''# TitanMiniHUD.py
# Universal mini HUD (always-on-top) showing:
# - GAME (foreground process/title mapped via json maps if present)
# - INTERVAL (capture interval ms)
# - MS (last translation latency parsed from stdout logs)
#
# No ping, by design.

from __future__ import annotations

import os
import sys
import re
import time
import json
import queue
import threading
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

# Tkinter is stdlib on Windows.
import tkinter as tk

MS_REGEX = re.compile(r'(?<!\d)(\d{1,5})\s*ms\b', re.IGNORECASE)

@dataclass
class GameMaps:
    proc_map: Dict[str, str]
    title_map: Dict[str, str]

def _load_maps(root: Path) -> GameMaps:
    proc_map = {}
    title_map = {}
    p1 = root / "titan_game_process_map.json"
    p2 = root / "titan_game_title_map.json"
    try:
        if p1.exists():
            proc_map = json.loads(p1.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        proc_map = {}
    try:
        if p2.exists():
            title_map = json.loads(p2.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        title_map = {}
    # normalize keys
    proc_map = {str(k).lower(): str(v) for k, v in proc_map.items()}
    title_map = {str(k).lower(): str(v) for k, v in title_map.items()}
    return GameMaps(proc_map=proc_map, title_map=title_map)

def _win_foreground_process_title() -> Tuple[Optional[int], str]:
    # Windows-only: use ctypes (stdlib)
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None, ""

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, ""

    # title
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value or ""

    # pid
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value) if pid.value else None, title

def _pid_to_procname(pid: Optional[int]) -> str:
    if not pid:
        return ""
    # try psutil
    try:
        import psutil  # type: ignore
        return psutil.Process(pid).name()
    except Exception:
        pass
    # fallback: wmic
    try:
        import subprocess
        out = subprocess.check_output(
            ["cmd", "/c", f"wmic process where processid={pid} get name /value"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in out.splitlines():
            if line.lower().startswith("name="):
                return line.split("=", 1)[1].strip()
    except Exception:
        return ""
    return ""

def detect_game_label(root: Path, maps: GameMaps) -> str:
    pid, title = _win_foreground_process_title()
    proc = _pid_to_procname(pid).lower().strip()
    title_l = (title or "").lower().strip()

    # explicit override
    ov = os.environ.get("TITAN_GAME_OVERRIDE", "").strip()
    if ov:
        return ov

    # map by process
    if proc and proc in maps.proc_map:
        return maps.proc_map[proc]

    # map by title contains key
    if title_l:
        # exact key
        if title_l in maps.title_map:
            return maps.title_map[title_l]
        # substring keys
        for k, v in maps.title_map.items():
            if k and k in title_l:
                return v

    # fallback: show process or short title
    if proc:
        return proc
    if title:
        return title[:32]
    return "UNKNOWN"

class MiniHUD:
    def __init__(self, root_dir: Path, model_label: str, interval_ms: int):
        self.root_dir = root_dir
        self.maps = _load_maps(root_dir)
        self.model_label = model_label
        self.interval_ms = interval_ms
        self.last_ms = "-"
        self.game = "..."

        self._stop = threading.Event()

        self._tk = tk.Tk()
        self._tk.title("TITAN HUD")
        self._tk.overrideredirect(True)
        self._tk.attributes("-topmost", True)
        try:
            self._tk.attributes("-alpha", 0.92)
        except Exception:
            pass

        self._frame = tk.Frame(self._tk, bd=1, relief="solid")
        self._frame.pack(fill="both", expand=True)

        self._lbl_model = tk.Label(self._frame, text=f"MODEL: {self.model_label}", anchor="w")
        self._lbl_game  = tk.Label(self._frame, text=f"GAME:  {self.game}", anchor="w")
        self._lbl_int   = tk.Label(self._frame, text=f"INT:   {self.interval_ms}ms", anchor="w")
        self._lbl_ms    = tk.Label(self._frame, text=f"MS:    {self.last_ms}", anchor="w")

        for w in (self._lbl_model, self._lbl_game, self._lbl_int, self._lbl_ms):
            w.pack(fill="x", padx=6, pady=1)

        self._place_top_right()

        # periodic refresh
        self._tk.after(200, self._tick)

    def _place_top_right(self):
        # place at top-right with small margin
        try:
            self._tk.update_idletasks()
            sw = self._tk.winfo_screenwidth()
            x = sw - 360
            y = 10
            self._tk.geometry(f"350x90+{max(0, x)}+{y}")
        except Exception:
            pass

    def set_last_ms(self, ms: str):
        self.last_ms = ms
        try:
            self._lbl_ms.config(text=f"MS:    {self.last_ms}")
        except Exception:
            pass

    def _tick(self):
        if self._stop.is_set():
            try:
                self._tk.destroy()
            except Exception:
                pass
            return

        # update game
        try:
            self.game = detect_game_label(self.root_dir, self.maps)
            self._lbl_game.config(text=f"GAME:  {self.game}")
        except Exception:
            pass

        self._tk.after(500, self._tick)

    def stop(self):
        self._stop.set()

    def loop(self):
        self._tk.mainloop()

def run_with_hud(target_script: str, env: dict) -> int:
    root_dir = Path(target_script).resolve().parent
    label = env.get("TITAN_MODEL_LABEL", "TITAN")
    try:
        interval_ms = int(env.get("TITAN_CAPTURE_INTERVAL_MS", "200"))
    except Exception:
        interval_ms = 200

    hud = MiniHUD(root_dir=root_dir, model_label=label, interval_ms=interval_ms)

    q: "queue.Queue[str]" = queue.Queue()

    def reader_thread(proc: subprocess.Popen):
        # forward stdout + parse ms
        try:
            for line in proc.stdout:  # type: ignore
                try:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                except Exception:
                    pass

                m = MS_REGEX.search(line)
                if m:
                    q.put(m.group(1) + "ms")
        except Exception:
            pass

    # Start subprocess
    proc = subprocess.Popen(
        [sys.executable, str(Path(target_script).resolve())],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    t = threading.Thread(target=reader_thread, args=(proc,), daemon=True)
    t.start()

    def hud_updater():
        while proc.poll() is None:
            try:
                ms = q.get(timeout=0.5)
                hud.set_last_ms(ms)
            except queue.Empty:
                continue
            except Exception:
                continue
        hud.stop()

    threading.Thread(target=hud_updater, daemon=True).start()

    # Run HUD loop (blocks until process ends)
    hud.loop()

    return int(proc.returncode or 0)
'''

TITANCORE_V2_NEW = r'''# TitanCore_V2.py (Rebuilt by TITAN_PATCH_BUILD_V5.py)
# - Categorized menu table for Model V1..V5 (Normal/Lite/IDN)
# - Extras grouped and explained
# - Simple shortcuts (type number + Enter)

from __future__ import annotations

import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple

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
    return subprocess.call([sys.executable, str(p)], env=env)

def build_entries() -> List[Entry]:
    entries: List[Entry] = []
    k = 1

    def add(group: str, title: str, script: str, desc: str):
        nonlocal k
        if exists(script):
            entries.append(Entry(str(k), title, script, desc, group))
            k += 1

    # ------------------ Model Definitions (User-Friendly) ------------------
    # V1: speed-first
    # V2: balanced, slightly accuracy leaning
    # V3: heavy accuracy, slow (prefers TITAN_ULTRA if available)
    # V4: hybrid placeholder flags (fast first + accurate later)
    # V5: naturalization max (currently uses legacy V4 base per user request)
    add("Model Versi 1 (FAST)", "V1 Normal", "TitanMainV1.py",
        "Kecepatan paling tinggi. Akurasi lebih rendah. Cocok untuk gameplay cepat.")
    add("Model Versi 1 (FAST)", "V1 Lite", "TitanMainV1Lite.py",
        "Versi ringan (jika tersedia di project).")
    add("Model Versi 1 (FAST)", "V1 IDN", "TitanMainV1_IDN.py",
        "V1 + IDN mode (naturalization/glossary bila engine mendukung).")
    add("Model Versi 1 (FAST)", "V1 Lite IDN", "TitanMainV1Lite_IDN.py",
        "V1 Lite + IDN (jika tersedia).")

    add("Model Versi 2 (BALANCED)", "V2 Normal", "TitanMainV2.py",
        "Seimbang. Lebih condong ke akurasi dibanding V1, masih cukup cepat.")
    add("Model Versi 2 (BALANCED)", "V2 Lite", "TitanMainV2Lite.py",
        "V2 versi ringan (jika tersedia di project).")
    add("Model Versi 2 (BALANCED)", "V2 IDN", "TitanMainV2_IDN.py",
        "V2 + IDN mode (naturalization/glossary bila engine mendukung).")
    add("Model Versi 2 (BALANCED)", "V2 Lite IDN", "TitanMainV2Lite_IDN.py",
        "V2 Lite + IDN (jika tersedia).")

    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Normal", "TitanMainV3.py",
        "Akurasi sangat tinggi, proses lebih lambat. Jika ada TITAN_ULTRA, akan diprioritaskan.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Lite", "TitanMainV3Lite.py",
        "V3 versi ringan: tetap condong akurasi, tapi lebih ringan.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 IDN", "TitanMainV3_IDN.py",
        "V3 + IDN mode.")
    add("Model Versi 3 (HEAVY ACCURACY)", "V3 Lite IDN", "TitanMainV3Lite_IDN.py",
        "V3 Lite + IDN mode.")

    add("Model Versi 4 (HYBRID)", "V4 Normal", "TitanMainV4.py",
        "Hybrid (fast first + accurate later). Saat ini menggunakan flag placeholder (engine bisa mengabaikan).")
    add("Model Versi 4 (HYBRID)", "V4 Lite", "TitanMainV4Lite.py",
        "V4 versi ringan.")
    add("Model Versi 4 (HYBRID)", "V4 IDN", "TitanMainV4_IDN.py",
        "V4 + IDN mode (jika wrapper ada).")
    add("Model Versi 4 (HYBRID)", "V4 Lite IDN", "TitanMainV4Lite_IDN.py",
        "V4 Lite + IDN mode.")

    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Normal", "TitanMainV5.py",
        "Maksimalkan naturalisasi IDN. Saat ini masih memakai basis legacy V4 online (sesuai request).")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Lite", "TitanMainV5Lite.py",
        "V5 versi ringan.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 IDN", "TitanMainV5_IDN.py",
        "V5 + IDN mode.")
    add("Model Versi 5 (NATURALIZATION MAX)", "V5 Lite IDN", "TitanMainV5Lite_IDN.py",
        "V5 Lite + IDN mode.")

    # ------------------ EXTRAS (auto-discovered important Titan scripts) ------------------
    extras = [
        ("TITANMAIN.py", "Entry utama engine (jika kamu biasa start dari sini)."),
        ("TITAN_ULTRA.py", "Preset Ultra (biasanya offline/CT2 jika tersedia)."),
        ("MODE_DEBUG.py", "Debug core init/sync untuk cek modul yang gagal."),
        ("TITAN_DOCTOR.py", "Doctor/repair tool (hati-hati karena bisa overwrite file)."),
        ("TITAN_DEBUG_MAIN.py", "Debug runner (jika ada)."),
        ("TITAN_LAUNCHER.py", "Launcher menu alternatif (jika ada)."),
        ("TitanMainV3_LEGACY_ROUTER.py", "Legacy V3 router (disimpan untuk referensi)."),
        ("TitanMainV4_LEGACY_ONLINE.py", "Legacy V4 online (basis V5 saat ini)."),
    ]
    for s, d in extras:
        if exists(s):
            add("EXTRAS", s, s, d)

    return entries

def print_table(entries: List[Entry]) -> None:
    # Group and print
    groups: Dict[str, List[Entry]] = {}
    for e in entries:
        groups.setdefault(e.group, []).append(e)

    print("\n" + "=" * 78)
    print(" TITANCORE V2 — MODEL SELECTOR (V1..V5)".ljust(77) + " ")
    print("=" * 78)
    print(" Indikator HUD aktif di wrapper model: GAME + INTERVAL + MS (tanpa PING)\n")

    for g in [
        "Model Versi 1 (FAST)",
        "Model Versi 2 (BALANCED)",
        "Model Versi 3 (HEAVY ACCURACY)",
        "Model Versi 4 (HYBRID)",
        "Model Versi 5 (NATURALIZATION MAX)",
        "EXTRAS",
    ]:
        if g not in groups:
            continue
        print(f"[{g}]")
        print("-" * 78)
        print(f"{'Key':<4}  {'Title':<24}  {'Script':<28}  Description")
        print("-" * 78)
        for e in groups[g]:
            print(f"{e.key:<4}  {e.title:<24}  {e.script:<28}  {e.desc}")
        print("")

    print("Commands:")
    print("  - ketik angka lalu Enter untuk menjalankan")
    print("  - q = keluar\n")

def main() -> None:
    os.chdir(ROOT)
    entries = build_entries()
    if not entries:
        print("[CORE] Tidak ada entry yang ditemukan. Pastikan kamu menjalankan di root project.")
        raise SystemExit(1)

    while True:
        print_table(entries)
        choice = input("Select> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            break
        found = None
        for e in entries:
            if e.key == choice:
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
'''

# -------------------------- Run --------------------------
if __name__ == "__main__":
    main()
