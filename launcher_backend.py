import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from data_processing_backend import record_runtime_line, get_candidates, load_settings, clear_candidates
from gpu_runtime import gpu_summary_text, install_or_repair_gpu

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_CFG = BASE_DIR / "runtime_paths.json"
PREFS_PATH = BASE_DIR / "webui_prefs.json"


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_runtime_config():
    cfg = _load_json(RUNTIME_CFG, {})
    runtime_root = cfg.get("runtime_root") or str(BASE_DIR / "_runtime")
    project_root = cfg.get("project_root") or str(BASE_DIR)
    runtime_python = str(Path(runtime_root) / ".venv" / "Scripts" / "python.exe")
    valid = Path(runtime_python).exists()
    storage_mode = "custom" if Path(runtime_root).resolve() != (BASE_DIR / "_runtime").resolve() else "local"
    return {
        "project_root": project_root,
        "runtime_root": runtime_root,
        "runtime_python": runtime_python if valid else "-",
        "storage_mode": storage_mode,
        "last_runtime_valid": valid,
    }


def runtime_summary_text():
    cfg = get_runtime_config()
    return "\n".join([
        f"project_root = {cfg['project_root']}",
        f"runtime_root = {cfg['runtime_root']}",
        f"runtime_python = {cfg['runtime_python']}",
        f"storage_mode = {cfg['storage_mode']}",
        f"last_runtime_valid = {str(cfg['last_runtime_valid'])}",
    ])


def load_prefs():
    return _load_json(PREFS_PATH, {
        "model": "ORTCore V5 Lv1",
        "model_group": "basic",
        "game": "GFL2_EXILIUM",
        "mode": "freeze",
        "engine": "gpu",
        "interval_ms": 80,
    })


def save_prefs(model, game, mode, engine, interval_ms, model_group=None):
    data = load_prefs()
    data.update({
        "model": model,
        "game": game,
        "mode": mode,
        "engine": engine,
        "interval_ms": int(interval_ms),
    })
    if model_group:
        data["model_group"] = model_group
    _save_json(PREFS_PATH, data)
    return data


MODEL_MAP = {
    "ORTCore V1": "TitanMainV1.py",
    "ORTCore V1 Lite": "TitanMainV1Lite.py",
    "ORTCore V1 IDN": "TitanMainV1_IDN.py",
    "ORTCore V1 Lite IDN": "TitanMainV1Lite_IDN.py",
    "ORTCore V2": "TitanMainV2.py",
    "ORTCore V2 Lite": "TitanMainV2Lite.py",
    "ORTCore V2 IDN": "TitanMainV2_IDN.py",
    "ORTCore V2 Lite IDN": "TitanMainV2Lite_IDN.py",
    "ORTCore V3": "TitanMainV3.py",
    "ORTCore V3 Lite": "TitanMainV3Lite.py",
    "ORTCore V3 IDN": "TitanMainV3_IDN.py",
    "ORTCore V3 Lite IDN": "TitanMainV3Lite_IDN.py",
    "ORTCore V4": "TitanMainV4.py",
    "ORTCore V4 Lite": "TitanMainV4Lite.py",
    "ORTCore V4 IDN": "TitanMainV4_IDN.py",
    "ORTCore V4 Lite IDN": "TitanMainV4Lite_IDN.py",
    "ORTCore V5": "TitanMainV5.py",
    "ORTCore V5 Lite": "TitanMainV5Lite.py",
    "ORTCore V5 IDN": "TitanMainV5_IDN.py",
    "ORTCore V5 Lite IDN": "TitanMainV5Lite_IDN.py",
    "ORTCore V5 Lv1": "ORTCore_V5_Lv1.py",
    "ORTCore V5 Lv1 Lite": "ORTCore_V5_Lv1_Lite.py",
    "ORTCore V5 Lv2": "ORTCore_V5_Lv2.py",
    "ORTCore V5 Lv2 Lite": "ORTCore_V5_Lv2_Lite.py",
    "ORTCore V5 Lv3": "ORTCore_V5_Lv3.py",
    "ORTCore V5 Lv3 Lite": "ORTCore_V5_Lv3_Lite.py",
    "ORTCore V5 Lv4": "ORTCore_V5_Lv4.py",
    "ORTCore V5 Lv4 Lite": "ORTCore_V5_Lv4_Lite.py",
}


class ProcessManager:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.lines = []
        self.status = "IDLE"
        self.last_error = ""
        self.lock = threading.Lock()
        self.current_game = "GFL2_EXILIUM"
        self.stop_requested = False
        self.stop_at = 0.0
        self.pending_candidate_notice = ""

    def _push(self, text: str):
        clean = text.rstrip("\n")
        with self.lock:
            self.lines.append(clean)
            if len(self.lines) > 700:
                self.lines = self.lines[-700:]
        try:
            record_runtime_line(self.current_game, clean)
        except Exception:
            pass

    def get_log(self):
        with self.lock:
            return "\n".join(self.lines)

    def get_status_text(self):
        err = f"\nLAST_ERROR: {self.last_error}" if self.last_error else ""
        return f"STATUS: {self.status}{err}"

    def _reader(self):
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            self._push(line)
        code = self.proc.wait()
        if self.stop_requested:
            self.status = "STOP"
            self.stop_at = time.time()
            self._prepare_candidate_notice()
        elif code == 0:
            # clean exit, often from ESC / normal close
            self.status = "STOP"
            self.stop_at = time.time()
            self._prepare_candidate_notice()
        else:
            self.status = "ERROR"
            if not self.last_error:
                self.last_error = f"Process exited with code {code}"
            self._push(f"[WEBUI] Process selesai dengan code {code}")

    def _prepare_candidate_notice(self):
        settings = load_settings()
        items, counts = get_candidates(self.current_game)
        items = [x for x in items if counts.get(x, 0) >= 1][:20]
        if items and settings.get('popup_on_stop', True):
            top = ", ".join(items[:6])
            self.pending_candidate_notice = (
                f"Nama/Kata baru tercatat ({len(items)}): {top}. "
                f"Buka tab Pengolahan Data untuk olah atau skip."
            )
        else:
            self.pending_candidate_notice = ""

    def candidate_notice(self):
        return self.pending_candidate_notice

    def start(self, model, game, mode, engine, interval_ms):
        if self.proc and self.proc.poll() is None:
            return self.get_status_text(), self.get_log(), "Model masih berjalan. Stop dulu sebelum start baru.", self.pending_candidate_notice

        save_prefs(model, game, mode, engine, interval_ms)
        if load_settings().get("auto_reset_candidates", False):
            try:
                clear_candidates(game)
            except Exception:
                pass
        cfg = get_runtime_config()
        runtime_python = Path(cfg["runtime_python"])
        if not runtime_python.exists():
            self.status = "ERROR"
            self.last_error = f"Runtime Python tidak ditemukan: {runtime_python}"
            self._push(f"[WEBUI] {self.last_error}")
            return self.get_status_text(), self.get_log(), self.last_error, self.pending_candidate_notice

        script_name = MODEL_MAP.get(model, "TitanMainV1.py")
        script_path = BASE_DIR / script_name
        try:
            if script_path.exists() and script_path.name.lower() == "titanmainv1.py":
                preview = script_path.read_text(encoding="utf-8", errors="replace")[:120]
                if "PATCH NOTE ONLY" in preview:
                    script_name = "TITANMAIN.py"
                    script_path = BASE_DIR / script_name
        except Exception:
            pass
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["ORT_RUNTIME_ROOT"] = cfg["runtime_root"]
        env["ORT_BOOT_MODE"] = str(mode).lower()
        env["ORT_BOOT_ENGINE"] = str(engine).lower()
        env["ORT_BOOT_INTERVAL_MS"] = str(int(interval_ms))
        env["ORT_GAME_OVERRIDE"] = str(game)

        self.lines = []
        self.last_error = ""
        self.pending_candidate_notice = ""
        self.current_game = str(game)
        self.status = "RUNNING"
        self.stop_requested = False
        self._push(f"[WEBUI] START {model} | game={game} | mode={mode} | engine={engine} | interval={interval_ms}ms")
        self._push(f"[WEBUI] runtime_python={runtime_python}")
        self._push(f"[WEBUI] script={script_name}")

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        self.proc = subprocess.Popen(
            [str(runtime_python), str(script_path)],
            cwd=str(BASE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        return self.get_status_text(), self.get_log(), f"Menjalankan {model}...", self.pending_candidate_notice

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.stop_requested = True
            self.status = "STOP"
            self.stop_at = time.time()
            try:
                if os.name == 'nt':
                    subprocess.run([
                        'taskkill', '/PID', str(self.proc.pid), '/T', '/F'
                    ], capture_output=True, text=True, timeout=10)
                else:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=5)
                    except Exception:
                        self.proc.kill()
            except Exception as e:
                self.last_error = str(e)
            self._push("[WEBUI] STOP requested. OCR / translation dihentikan keras.")
            self._prepare_candidate_notice()
        else:
            self.status = "IDLE"
        return self.get_status_text(), self.get_log(), "Stop selesai.", self.pending_candidate_notice

    def refresh(self):
        if self.status == "STOP" and (not self.proc or self.proc.poll() is not None):
            if time.time() - self.stop_at > 1.2:
                self.status = "IDLE"
        return self.get_status_text(), self.get_log(), self.last_error or "", self.pending_candidate_notice


MANAGER = ProcessManager()


def start_model(model, game, mode, engine, interval_ms):
    return MANAGER.start(model, game, mode, engine, interval_ms)


def stop_model():
    return MANAGER.stop()


def refresh_state():
    return MANAGER.refresh()


def finish_start():
    return MANAGER.refresh()


def gpu_doctor_text():
    return gpu_summary_text()


def repair_gpu_runtime():
    return install_or_repair_gpu()
