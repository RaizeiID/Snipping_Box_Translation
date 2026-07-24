# TitanMiniHUD.py (v2)
# HUD kecil selalu-on-top menampilkan:
# - GAME (foreground process/title; pakai map json jika ada)
# - INTERVAL (ms)
# - MS (latensi translate terakhir, diparsing dari stdout model)
#
# Tanpa PING.

from __future__ import annotations
import os, sys, re, json, queue, threading, subprocess
from pathlib import Path
import tkinter as tk

MS_REGEX = re.compile(r'(?<!\d)(\d{1,5})\s*ms\b', re.IGNORECASE)

def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}

def _win_foreground():
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None, ""

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, ""

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value or ""

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value) if pid.value else None, title

def _pid_to_procname(pid):
    if not pid:
        return ""
    try:
        import psutil  # type: ignore
        return psutil.Process(pid).name()
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["cmd", "/c", f"wmic process where processid={pid} get name /value"],
            stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in out.splitlines():
            if line.lower().startswith("name="):
                return line.split("=", 1)[1].strip()
    except Exception:
        return ""
    return ""

def detect_game_label(root: Path):
    proc_map = _load_json(root / "titan_game_process_map.json")
    title_map = _load_json(root / "titan_game_title_map.json")
    proc_map = {str(k).lower(): str(v) for k, v in proc_map.items()}
    title_map = {str(k).lower(): str(v) for k, v in title_map.items()}

    ov = os.environ.get("TITAN_GAME_OVERRIDE", "").strip()
    if ov:
        return ov

    pid, title = _win_foreground()
    proc = _pid_to_procname(pid).lower().strip()
    title_l = (title or "").lower().strip()

    if proc and proc in proc_map:
        return proc_map[proc]

    if title_l:
        if title_l in title_map:
            return title_map[title_l]
        for k, v in title_map.items():
            if k and k in title_l:
                return v

    if proc:
        return proc
    if title:
        return title[:32]
    return "UNKNOWN"

class MiniHUD:
    def __init__(self, root_dir: Path, label: str, interval_ms: int):
        self.root_dir = root_dir
        self.label = label
        self.interval_ms = interval_ms
        self.last_ms = "-"
        self.game = "..."

        self._stop = threading.Event()
        self._tk = tk.Tk()
        self._tk.title("TITAN HUD (MS/INT/GAME)")
        self._tk.overrideredirect(True)
        self._tk.attributes("-topmost", True)
        try:
            self._tk.attributes("-alpha", 0.95)
        except Exception:
            pass

        frame = tk.Frame(self._tk, bd=2, relief="solid")
        frame.pack(fill="both", expand=True)

        f_big = ("Segoe UI", 10, "bold")
        f_mid = ("Segoe UI", 9)

        self._l1 = tk.Label(frame, text=f"MODEL: {self.label}", font=f_big, anchor="w")
        self._l2 = tk.Label(frame, text=f"GAME : {self.game}", font=f_mid, anchor="w")
        self._l3 = tk.Label(frame, text=f"INT  : {self.interval_ms} ms", font=f_mid, anchor="w")
        self._l4 = tk.Label(frame, text=f"MS   : {self.last_ms}", font=f_big, anchor="w")

        for w in (self._l1, self._l2, self._l3, self._l4):
            w.pack(fill="x", padx=8, pady=2)

        self._place()
        self._tk.after(250, self._tick)

    def _place(self):
        try:
            self._tk.update_idletasks()
            sw = self._tk.winfo_screenwidth()
            x = max(0, sw - 420)
            y = 10
            self._tk.geometry(f"410x110+{x}+{y}")
        except Exception:
            pass

    def set_last_ms(self, ms: str):
        self.last_ms = ms
        try:
            self._l4.config(text=f"MS   : {self.last_ms}")
        except Exception:
            pass

    def _tick(self):
        if self._stop.is_set():
            try:
                self._tk.destroy()
            except Exception:
                pass
            return
        try:
            self.game = detect_game_label(self.root_dir)
            self._l2.config(text=f"GAME : {self.game}")
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

    print(f"[HUD] ON  | MODEL={label} | INTERVAL={interval_ms}ms")
    hud = MiniHUD(root_dir=root_dir, label=label, interval_ms=interval_ms)

    q: "queue.Queue[str]" = queue.Queue()

    def reader(proc: subprocess.Popen):
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

    proc = subprocess.Popen(
        [sys.executable, str(Path(target_script).resolve())],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    threading.Thread(target=reader, args=(proc,), daemon=True).start()

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
    hud.loop()
    return int(proc.returncode or 0)
