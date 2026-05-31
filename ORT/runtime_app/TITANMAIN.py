# TITANMAIN.py
# ==============================================================================
# TITAN X v6.3+  (MAIN based on TitanMainV2)
#
# UPDATE FULL CODE (requested):
# Focus: CAS downgrade -> MUCH faster (less accurate) while keeping:
# - Shift+F9 hotkey preserved
# - CAS progress percentage preserved (overlay label "CAS xx%")
#
# NOTE:
# - Non-CAS modes (STABLE/FREEZE/HIGH_LATENCY) behavior is kept the same as V2.
# - Translation fix (Argos ID output) remains (same as V2).
# - Only CAS pipeline is changed: remove ULTRA refine/second-pass, use fast downscale+1-pass.
# ==============================================================================

import os
import sys
import time
import json
import re
import gc
import ctypes
import warnings
import threading
import queue
from collections import Counter, deque
from datetime import datetime
import subprocess
import signal

# -------------------- PERF ENV (set early) --------------------
CPU_THREADS = int(os.environ.get("TITAN_CPU_THREADS", str(os.cpu_count() or 24)))
os.environ.setdefault("OMP_NUM_THREADS", str(CPU_THREADS))
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(CPU_THREADS))
os.environ.setdefault("MKL_NUM_THREADS", str(CPU_THREADS))
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", str(CPU_THREADS))
os.environ.setdefault("NUMEXPR_NUM_THREADS", str(CPU_THREADS))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

warnings.filterwarnings("ignore")

# DPI aware (Windows)
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

import numpy as np
import cv2
import mss
import easyocr
import keyboard
import torch
import argostranslate.translate

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QRubberBand,
    QVBoxLayout, QHBoxLayout
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPoint, QRect, QObject, QTimer
)
from PyQt5.QtGui import (
    QGuiApplication, QPainter, QColor, QFont, QImage, QPixmap, QFontMetrics, QCursor
)

# -------------------- Screen helper (multi-monitor) --------------------
def _get_active_screen():
    """Pick the screen under the current cursor (fallback to primary)."""
    try:
        scr = QGuiApplication.screenAt(QCursor.pos())
        if scr is not None:
            return scr
    except Exception:
        pass
    try:
        return QGuiApplication.primaryScreen()
    except Exception:
        return None


# -------------------- OpenCV/Torch tuning --------------------
try:
    cv2.setUseOptimized(True)
    cv2.setNumThreads(min(CPU_THREADS, 24))
except Exception:
    pass

try:
    torch.set_num_threads(min(CPU_THREADS, 24))
    torch.set_num_interop_threads(max(1, min(CPU_THREADS // 2, 8)))
    torch.backends.cudnn.benchmark = True
except Exception:
    pass

# ==============================================================================
# LOGGING
# ==============================================================================
def _ts():
    return time.strftime("%H:%M:%S")

def log(msg: str):
    print(f"[{_ts()}] {msg}", flush=True)

# ==============================================================================
# PATHS + VERSION
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VERSION = "ORT Translation v8.8.3 - TITANMAIN (GFL2 Recording Stability & Overlay Commit Gate)"
CACHE_FILE = os.path.join(BASE_DIR, "translation_memory.json")
NPC_FILE = os.path.join(BASE_DIR, "npc_database.json")
UNIQUE_FILE = os.path.join(BASE_DIR, "unique_terms.json")
PUNCT_FILE = os.path.join(BASE_DIR, "punctuation_stats.json")
TRAIN_LOG_FILE = os.path.join(BASE_DIR, "training_log.jsonl")

# ==============================================================================
# STATE
# ==============================================================================
CURRENT_ENGINE_MODE = "AUTO_GPU"   # AUTO_GPU -> FORCE_GPU -> FORCE_CPU
AUTO_GPU_FALLBACK_CPU = False
IS_USING_GPU = False

OCR_LOCK = threading.RLock()
GLOBAL_READER = None

# Capture modes: 0=STABLE, 1=FREEZE, 2=HIGH_LATENCY
CAPTURE_MODE = 0

# UI toggles
IS_PAUSED = False
CURRENT_POS_MODE = "FLOATING"   # FLOATING / COVER
CURRENT_VISUAL_ID = 2           # 0 phantom, 1 solid, 2 glass-ish
CURRENT_FONT_SIZE = 22
CURRENT_WIDTH_SCALE = 1.0

# AUTO snapshot (F11)
AUTO_SNAPSHOT_ON = False
AUTO_SNAPSHOT_INTERVAL_MS = int(os.environ.get("TITAN_AUTO_SNAPSHOT_MS", "180"))
# v8.4: restore the normal safe interval floor to 90ms.
# Experimental values below 90ms should not be applied by the default WebUI path.
AUTO_SNAPSHOT_MIN_MS = int(os.environ.get("TITAN_AUTO_SNAPSHOT_MIN_MS", "90"))
AUTO_SNAPSHOT_INTERVAL_MS = max(AUTO_SNAPSHOT_MIN_MS, AUTO_SNAPSHOT_INTERVAL_MS)
LAST_TRANSLATE_MS = 0
LAST_TRANSLATION_META = {}
ORT_GAME_OVERRIDE = os.environ.get("ORT_GAME_OVERRIDE", "GFL2_EXILIUM").strip().upper()

# v7 profile-aware runtime knobs. These are injected by WebUI/launcher_backend.py.
ORT_V7_ENABLED = os.environ.get("ORT_V7_ENABLED", "0") == "1"
ORT_PERFORMANCE_POLICY = os.environ.get("ORT_PERFORMANCE_POLICY", "balanced").strip().lower()
ORT_MODEL_KEY = os.environ.get("ORT_MODEL_KEY", "").strip().lower()
ORT_MODEL_GROUP = os.environ.get("ORT_MODEL_GROUP", "normal").strip().lower()
ORT_OCR_RESOLUTION_PERCENT = max(35, min(120, int(os.environ.get("ORT_OCR_RESOLUTION_PERCENT", os.environ.get("ORT_BOOT_OCR_RESOLUTION", "100")))))
ORT_OCR_SCALE = max(0.35, min(1.20, ORT_OCR_RESOLUTION_PERCENT / 100.0))
# Runtime health can lower this while the game is under pressure.
ORT_RUNTIME_OCR_RESOLUTION_PERCENT = ORT_OCR_RESOLUTION_PERCENT
ORT_RUNTIME_OCR_SCALE = ORT_OCR_SCALE
ORT_SCAN_SLEEP_GPU_MS = max(5, int(os.environ.get("TITAN_SCAN_SLEEP_GPU_MS", "18")))
ORT_SCAN_SLEEP_CPU_MS = max(10, int(os.environ.get("TITAN_SCAN_SLEEP_CPU_MS", "45")))
ORT_HEAVY_GAME_SAFE = os.environ.get("TITAN_HEAVY_GAME_SAFE", "0") == "1"
ORT_RUNTIME_STRATEGY_ENABLED = os.environ.get("ORT_RUNTIME_STRATEGY", "1") != "0"
ORT_RUNTIME_CONTROL_ENABLED = os.environ.get("ORT_RUNTIME_CONTROL", "1") != "0"
ORT_RUNTIME_STATUS_ENABLED = os.environ.get("ORT_RUNTIME_STATUS", "1") != "0"
ORT_STOP_REQUEST_FILE = os.environ.get("ORT_STOP_REQUEST_FILE", os.path.join(BASE_DIR, "runtime_stop_request.json"))
_SHUTDOWN_DONE = False
ORT_CORE_PROFILE = os.environ.get("ORT_CORE_PROFILE", "balanced").strip().lower()
ORT_ENGINE_POLICY = os.environ.get("ORT_ENGINE_POLICY", "offline").strip().lower()
ORT_LITE_EFFICIENT = os.environ.get("ORT_LITE_GPU_EFFICIENT", "0") == "1" or "lite" in ORT_MODEL_GROUP or ORT_MODEL_KEY.startswith("lite")
ORT_LITE_WIDE_DIALOG_FILTER = os.environ.get("ORT_LITE_WIDE_DIALOG_FILTER", "0") == "1"
ORT_OCR_NOISE_REJECT = os.environ.get("ORT_OCR_NOISE_REJECT", "0") == "1"
ORT_LITE_ADAPTIVE_OCR = os.environ.get("ORT_LITE_ADAPTIVE_OCR", "0") == "1"
ORT_ADAPTIVE_READABILITY_GUARD = os.environ.get("ORT_ADAPTIVE_READABILITY_GUARD", "0") == "1"
ORT_OCR_STORY_MIN_PERCENT = max(40, min(80, int(os.environ.get("ORT_OCR_STORY_MIN_PERCENT", "50"))))
ORT_NAME_ROI_MIN_PERCENT = max(40, min(80, int(os.environ.get("ORT_NAME_ROI_MIN_PERCENT", "50"))))
ORT_GFL2_EXACT_FALLBACK_ONLY = os.environ.get("ORT_GFL2_EXACT_FALLBACK_ONLY", "1") != "0"
ORT_NUMERIC_DUAL_PASS = os.environ.get("ORT_NUMERIC_DUAL_PASS", "1") != "0"
ORT_NUMERIC_DUAL_PASS_MIN_MS = max(250, int(os.environ.get("ORT_NUMERIC_DUAL_PASS_MIN_MS", "900")))
ORT_NUMERIC_ROI_ONLY = os.environ.get("ORT_NUMERIC_ROI_ONLY", "1") != "0"
# v8.7: dedicated Girls' Frontline (first game) compact-dialog pipeline.
ORT_GFL_LAYOUT = os.environ.get("ORT_GFL_LAYOUT", "0") == "1" or ORT_GAME_OVERRIDE in {"GFL", "GIRLS_FRONTLINE", "GFL1"}
ORT_GFL_FOOTER_MASK = os.environ.get("ORT_GFL_FOOTER_MASK", "1" if ORT_GFL_LAYOUT else "0") == "1"
ORT_GFL_DIALOG_PRESENCE_GUARD = os.environ.get("ORT_GFL_DIALOG_PRESENCE_GUARD", "1" if ORT_GFL_LAYOUT else "0") == "1"
ORT_GFL_SPEAKER_ROI = os.environ.get("ORT_GFL_SPEAKER_ROI", "1" if ORT_GFL_LAYOUT else "0") == "1"
ORT_GFL2_SPEAKER_GATE = os.environ.get("ORT_GFL2_SPEAKER_GATE", "0") == "1" or ORT_GAME_OVERRIDE in {"GFL2", "GFL2_EXILIUM"}
ORT_RESPONSIVE_STORY_MODE = os.environ.get("ORT_RESPONSIVE_STORY_MODE", "0") == "1"
ORT_TURN_SAFE_OVERLAY = os.environ.get("ORT_TURN_SAFE_OVERLAY", "1") == "1"
ORT_SCENE_EXIT_GUARD = os.environ.get("ORT_SCENE_EXIT_GUARD", "1") == "1"
try:
    from app.runtime.turn_safe_overlay import TurnSafeOverlayController, is_scene_exit_text
except Exception:
    TurnSafeOverlayController = None
    def is_scene_exit_text(_text, speaker=""):
        return False
try:
    from app.runtime.dialogue_stability import DialogueTurnAccumulator
except Exception:
    DialogueTurnAccumulator = None
try:
    from app.runtime.overlay_commit_gate import OverlayCommitGate
except Exception:
    OverlayCommitGate = None
try:
    from app.runtime.recording_telemetry import RecordingTelemetry
except Exception:
    RecordingTelemetry = None
ORT_LATEST_FRAME_WINS = os.environ.get("ORT_LATEST_FRAME_WINS", "0") == "1"
ORT_ENTITY_SPAN_PIPELINE = os.environ.get("ORT_ENTITY_SPAN_PIPELINE", "0") == "1"
ORT_SPEAKER_TRANSITION_GUARD = os.environ.get("ORT_SPEAKER_TRANSITION_GUARD", "1") != "0"
ORT_IDN_ACCURACY_QUALITY_LOCK = os.environ.get("ORT_IDN_ACCURACY_QUALITY_LOCK", "0") == "1"
_QUALITY_LOCK_WARNING_COUNT = 0
_QUALITY_LOCK_LAST_WARNING_TS = 0.0
LATEST_SPEAKER_EPOCH = 0
LATEST_SPEAKER_NAME = ""
ORT_GFL2_SPEAKER_ROI = os.environ.get("ORT_GFL2_SPEAKER_ROI", "1" if ORT_GFL2_SPEAKER_GATE else "0") == "1"

# WebUI boot preset (v6.5 sync patch)
ORT_BOOT_MODE = os.environ.get("ORT_BOOT_MODE", "").strip().lower()
ORT_BOOT_ENGINE = os.environ.get("ORT_BOOT_ENGINE", "").strip().lower()

def _apply_webui_boot_preset():
    global CURRENT_ENGINE_MODE, CAPTURE_MODE, AUTO_SNAPSHOT_ON, AUTO_SNAPSHOT_INTERVAL_MS
    if ORT_BOOT_ENGINE in ("gpu", "force_gpu"):
        CURRENT_ENGINE_MODE = "FORCE_GPU"
    elif ORT_BOOT_ENGINE in ("cpu", "force_cpu"):
        CURRENT_ENGINE_MODE = "FORCE_CPU"
    elif ORT_BOOT_ENGINE in ("hybrid", "auto", "auto_gpu"):
        CURRENT_ENGINE_MODE = "AUTO_GPU"

    if ORT_BOOT_MODE in ("freeze", "paused", "jeda"):
        CAPTURE_MODE = 1
        AUTO_SNAPSHOT_ON = False
    elif ORT_BOOT_MODE in ("interval", "auto_snapshot"):
        CAPTURE_MODE = 1
        AUTO_SNAPSHOT_ON = True
    elif ORT_BOOT_MODE in ("auto", "stable"):
        CAPTURE_MODE = 0
        AUTO_SNAPSHOT_ON = False

    try:
        env_ms = int(os.environ.get("ORT_BOOT_INTERVAL_MS", os.environ.get("TITAN_AUTO_SNAPSHOT_MS", str(AUTO_SNAPSHOT_INTERVAL_MS))))
        AUTO_SNAPSHOT_INTERVAL_MS = max(AUTO_SNAPSHOT_MIN_MS, env_ms)
    except Exception:
        pass

    if ORT_HEAVY_GAME_SAFE:
        # Safe Game harus lebih konservatif agar game berat tetap diprioritaskan.
        AUTO_SNAPSHOT_INTERVAL_MS = max(AUTO_SNAPSHOT_INTERVAL_MS, 350)

    if ORT_BOOT_MODE or ORT_BOOT_ENGINE or ORT_V7_ENABLED:
        print(f"[BOOT] WebUI/v8 preset | mode={ORT_BOOT_MODE or '-'} | engine={ORT_BOOT_ENGINE or '-'} | auto_ms={AUTO_SNAPSHOT_INTERVAL_MS}ms | ocr={ORT_OCR_RESOLUTION_PERCENT}% | policy={ORT_PERFORMANCE_POLICY}")

_apply_webui_boot_preset()

# ==============================================================================
# RUNTIME BRIDGE
# ==============================================================================
RUNTIME_BRIDGE_ENABLED = os.environ.get("ORT_RUNTIME_BRIDGE", os.environ.get("ORT_V71_CORE_PIPELINE", "1")) != "0"
RUNTIME_BRIDGE = None

def _get_runtime_bridge():
    """Lazy-load canonical runtime bridge."""
    global RUNTIME_BRIDGE
    if not RUNTIME_BRIDGE_ENABLED:
        return None
    if RUNTIME_BRIDGE is None:
        try:
            from runtime_bridge import RuntimeBridge
            RUNTIME_BRIDGE = RuntimeBridge(base_dir=BASE_DIR, logger=log)
            log(RUNTIME_BRIDGE.status_line())
        except Exception as e:
            RUNTIME_BRIDGE = False
            log(f"[RUNTIME] Runtime bridge disabled: {e}")
    return RUNTIME_BRIDGE if RUNTIME_BRIDGE is not False else None

# ==============================================================================
# RUNTIME ACTIONS
# ==============================================================================
RUNTIME_ACTIONS = None

def _get_runtime_actions():
    global RUNTIME_ACTIONS
    if not ORT_RUNTIME_CONTROL_ENABLED:
        return None
    if RUNTIME_ACTIONS is None:
        try:
            from runtime_actions import RuntimeActions
            RUNTIME_ACTIONS = RuntimeActions(BASE_DIR, logger=log)
            log("[RUNTIME] Runtime actions active.")
        except Exception as exc:
            RUNTIME_ACTIONS = False
            log(f"[RUNTIME] Runtime actions disabled: {exc}")
    return RUNTIME_ACTIONS if RUNTIME_ACTIONS is not False else None

def _set_runtime_ocr_resolution(percent: int, reason: str = "runtime_health"):
    global ORT_RUNTIME_OCR_RESOLUTION_PERCENT, ORT_RUNTIME_OCR_SCALE, _QUALITY_LOCK_WARNING_COUNT, _QUALITY_LOCK_LAST_WARNING_TS
    try:
        percent = max(35, min(120, int(percent)))
    except Exception:
        percent = ORT_OCR_RESOLUTION_PERCENT
    lowering = percent < ORT_RUNTIME_OCR_RESOLUTION_PERCENT
    transient_warning = "cpu/ram warning" in str(reason or "").lower() or "warning" in str(reason or "").lower()
    if ORT_IDN_ACCURACY_QUALITY_LOCK and lowering and transient_warning:
        now = time.time()
        _QUALITY_LOCK_WARNING_COUNT = (_QUALITY_LOCK_WARNING_COUNT + 1) if (now - _QUALITY_LOCK_LAST_WARNING_TS) < 10.0 else 1
        _QUALITY_LOCK_LAST_WARNING_TS = now
        if _QUALITY_LOCK_WARNING_COUNT < 2:
            try:
                from translation_event_logger import append_event
                append_event("IDN_QUALITY_LOCK_HELD", {"kept_percent": ORT_RUNTIME_OCR_RESOLUTION_PERCENT, "requested_downscale": percent, "reason": reason, "warning_count": _QUALITY_LOCK_WARNING_COUNT}, source_module="TITANMAIN")
            except Exception:
                pass
            return
    elif not lowering:
        _QUALITY_LOCK_WARNING_COUNT = 0
    if percent != ORT_RUNTIME_OCR_RESOLUTION_PERCENT:
        previous = ORT_RUNTIME_OCR_RESOLUTION_PERCENT
        ORT_RUNTIME_OCR_RESOLUTION_PERCENT = percent
        ORT_RUNTIME_OCR_SCALE = max(0.35, min(1.20, percent / 100.0))
        log(f"[RUNTIME] OCR resolution {previous}% -> {percent}% | reason={reason}")
        try:
            from translation_event_logger import append_event
            append_event("OCR_RESOLUTION_CHANGED", {"from": previous, "to": percent, "reason": reason, "quality_lock": bool(ORT_IDN_ACCURACY_QUALITY_LOCK)}, source_module="TITANMAIN")
        except Exception:
            pass

def _apply_runtime_actions():
    """Apply health directives with cooldown; safe to call from workers."""
    global AUTO_GPU_FALLBACK_CPU, _last_vram_switch_ts, CURRENT_ENGINE_MODE
    if not ORT_RUNTIME_CONTROL_ENABLED:
        return 0
    bridge = _get_runtime_bridge()
    applier = _get_runtime_actions()
    if not bridge or not applier or not hasattr(bridge, "health"):
        return 0
    try:
        health = bridge.health.snapshot(queue_size=OCR_TEXT_QUEUE.qsize(), queue_max=OCR_TO_TRANSLATE_MAX)
        directives = applier.decide(health, current_engine_mode=CURRENT_ENGINE_MODE, is_using_gpu=IS_USING_GPU)
        _set_runtime_ocr_resolution(directives.ocr_resolution_percent, getattr(directives, "reason", "runtime_health"))
        if directives.disable_online:
            os.environ["ORT_ONLINE_DISABLED"] = "1"
        else:
            os.environ.pop("ORT_ONLINE_DISABLED", None)
        if getattr(directives, "temporary_fast_mode", False):
            os.environ["ORT_TEMP_FAST_MODE"] = "1"
        else:
            os.environ.pop("ORT_TEMP_FAST_MODE", None)
        if directives.should_reload_cpu and IS_USING_GPU:
            log(f"[RUNTIME] Health action: staged OCR CPU fallback | {directives.reason}")
            AUTO_GPU_FALLBACK_CPU = True
            _last_vram_switch_ts = time.time()
            reload_ocr_engine("FORCE_CPU")
        elif directives.should_restore_engine:
            target = applier.previous_engine or "AUTO_GPU"
            log(f"[RUNTIME] Health action: restore OCR engine -> {target}")
            AUTO_GPU_FALLBACK_CPU = False
            _last_vram_switch_ts = time.time()
            reload_ocr_engine(target)
        return int(directives.extra_sleep_ms or 0)
    except Exception as exc:
        log(f"[RUNTIME] Health action ignored: {exc}")
        return 0


# ==============================================================================
# V7.4 GRACEFUL SHUTDOWN
# ==============================================================================
def _runtime_stop_requested():
    try:
        from graceful_shutdown import read_stop_request
        return read_stop_request(BASE_DIR)
    except Exception:
        try:
            if ORT_STOP_REQUEST_FILE and os.path.exists(ORT_STOP_REQUEST_FILE):
                return {"reason": "stop_file_present"}
        except Exception:
            pass
    return None


def _finalize_runtime_shutdown(reason="exit"):
    """Flush v8 cache/bridge/session state once before process exits."""
    global _SHUTDOWN_DONE
    if _SHUTDOWN_DONE:
        return
    _SHUTDOWN_DONE = True
    try:
        from graceful_shutdown import write_shutdown_status
        write_shutdown_status(BASE_DIR, "FLUSHING", reason)
    except Exception:
        pass
    try:
        save_cache(reason)
    except Exception as exc:
        try:
            log(f"[V8.1] shutdown save_cache ignored: {exc}")
        except Exception:
            pass
    try:
        from session_log_manager import close_session
        close_session(reason)
    except Exception:
        pass
    try:
        from graceful_shutdown import clear_stop_request, write_shutdown_status
        write_shutdown_status(BASE_DIR, "CLOSED", reason)
        clear_stop_request(BASE_DIR)
    except Exception:
        pass


def _signal_shutdown_handler(signum, frame):
    try:
        log(f"[V8.1] OS signal {signum}; graceful shutdown requested.")
    except Exception:
        pass
    _finalize_runtime_shutdown(f"signal_{signum}")
    try:
        app = QApplication.instance()
        if app is not None:
            app.quit()
    except Exception:
        pass



# VRAM monitor thresholds (AUTO_GPU only)
VRAM_LOW_GB = float(os.environ.get("TITAN_VRAM_LOW_GB", "0.65"))
VRAM_CRITICAL_GB = float(os.environ.get("TITAN_VRAM_CRITICAL_GB", "0.38"))
VRAM_RECOVER_GB = float(os.environ.get("TITAN_VRAM_RECOVER_GB", "1.6"))
VRAM_CHECK_INTERVAL_MS = int(os.environ.get("TITAN_VRAM_CHECK_MS", "2500"))
VRAM_COOLDOWN_SEC = float(os.environ.get("TITAN_VRAM_COOLDOWN_SEC", "12.0"))
_last_vram_switch_ts = 0.0
_vram_low_count = 0

# Queues
OCR_TO_TRANSLATE_MAX = int(os.environ.get("TITAN_QUEUE_MAX", "250"))
OCR_TEXT_QUEUE = queue.Queue(maxsize=OCR_TO_TRANSLATE_MAX)

# Learning
TRANSLATION_MEMORY = {}
NPC_DATABASE = {"known": [], "counts": {}}
UNIQUE_TERMS = {"known": []}
PUNCT_STATS = {"counts": {}}
_unique_counts = Counter()
SPEAKER_PROMOTE_HITS = int(os.environ.get("TITAN_SPEAKER_PROMOTE_HITS", "3"))

# CAS (Capture All Screen)
CAS_ACTIVE = False
CAS_IN_PROGRESS = False

# CAS progress (overlay)
CAS_PROGRESS = 0  # 0..100

# ------------------------------------------------------------------------------
# CAS FAST knobs (less accurate, faster)  [only CAS changed]
# ------------------------------------------------------------------------------
# Target width for detection pass (downscale aggressively for speed)
CAS_FAST_DETECT_W = int(os.environ.get("TITAN_CAS_FAST_DETECT_W", "1280"))
CAS_FAST_CANVAS = int(os.environ.get("TITAN_CAS_FAST_CANVAS", "1100"))

# Confidence filtering (looser than V2 accurate mode)
CAS_FAST_DET_MIN_CONF = float(os.environ.get("TITAN_CAS_FAST_DET_MIN_CONF", "0.25"))
CAS_FAST_MIN_CONF = float(os.environ.get("TITAN_CAS_FAST_MIN_CONF", "0.35"))

# Keep fewer blocks (speed)
CAS_FAST_MAX_LINES = int(os.environ.get("TITAN_CAS_FAST_MAX_LINES", "80"))
CAS_FAST_MIN_H = int(os.environ.get("TITAN_CAS_FAST_MIN_H", "14"))
CAS_FAST_MIN_W = int(os.environ.get("TITAN_CAS_FAST_MIN_W", "140"))

# EasyOCR settings (fast)
CAS_FAST_BATCH_GPU = int(os.environ.get("TITAN_CAS_FAST_BATCH_GPU", "28"))
CAS_FAST_BATCH_CPU = int(os.environ.get("TITAN_CAS_FAST_BATCH_CPU", "6"))

# Optional: quick de-dup
CAS_FAST_DEDUPE = bool(int(os.environ.get("TITAN_CAS_FAST_DEDUPE", "1")))

# ==============================================================================
# SAFE JSON I/O (atomic write)
# ==============================================================================
def _safe_load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _safe_save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log(f"[IO] save failed: {os.path.basename(path)} | {e}")
        return False

def load_all_learning():
    global TRANSLATION_MEMORY, NPC_DATABASE, UNIQUE_TERMS, PUNCT_STATS
    # v8.1: scoped per-game/model cache is primary. Legacy translation_memory.json is OFF by default.
    if os.environ.get("ORT_LEGACY_CACHE_WARMUP", "0") == "1":
        TRANSLATION_MEMORY = _safe_load_json(CACHE_FILE, {})
    else:
        TRANSLATION_MEMORY = {}

    raw_npc = _safe_load_json(NPC_FILE, {"known": []})
    if isinstance(raw_npc, dict):
        known = raw_npc.get("known", [])
        counts = raw_npc.get("counts", {})
        NPC_DATABASE = {"known": list(known), "counts": dict(counts)}
    elif isinstance(raw_npc, list):
        NPC_DATABASE = {"known": raw_npc, "counts": {}}
    else:
        NPC_DATABASE = {"known": [], "counts": {}}

    # v8.7.1: merge canonical GFL2 speaker seeds without replacing the user's NPC database file.
    if ORT_GAME_OVERRIDE in {"GFL2", "GFL2_EXILIUM"}:
        seeded_gfl2 = {"DP-12", "KSVK"}
        NPC_DATABASE["known"] = sorted(set(NPC_DATABASE.get("known", [])) | seeded_gfl2, key=len, reverse=True)

    UNIQUE_TERMS = _safe_load_json(UNIQUE_FILE, {"known": []})
    PUNCT_STATS = _safe_load_json(PUNCT_FILE, {"counts": {}})

    for t in UNIQUE_TERMS.get("known", []):
        _unique_counts[t] += 2

    log(f"[BOOT] Learning loaded | mem={len(TRANSLATION_MEMORY)} npc={len(NPC_DATABASE.get('known', []))} unique={len(UNIQUE_TERMS.get('known', []))}")

def save_cache(reason="manual"):
    # v8.1: do not rewrite the giant legacy translation_memory.json by default.
    # Scoped cache_store/translation_engine handles current-session translations.
    if os.environ.get("ORT_WRITE_LEGACY_CACHE", "0") == "1":
        _safe_save_json(CACHE_FILE, TRANSLATION_MEMORY)
    _safe_save_json(NPC_FILE, NPC_DATABASE)
    _safe_save_json(UNIQUE_FILE, UNIQUE_TERMS)
    _safe_save_json(PUNCT_FILE, PUNCT_STATS)
    bridge = _get_runtime_bridge()
    if bridge:
        try:
            bridge.flush(reason)
        except Exception:
            pass
    try:
        eng = _get_translation_engine() if ORT_RUNTIME_STRATEGY_ENABLED else None
        if eng:
            eng.flush()
    except Exception:
        pass
    log(f"[CACHE] Saved ({reason}) | legacy_mem={len(TRANSLATION_MEMORY)} npc={len(NPC_DATABASE.get('known', []))} unique={len(UNIQUE_TERMS.get('known', []))} | scoped_cache=primary")

def training_log_record(mode: str, src: str, out: str, meta=None):
    """v8.1: legacy root training_log.jsonl is OFF by default.

    Training samples are written as structured session events instead. Enable the
    old root file only for manual debugging with ORT_WRITE_LEGACY_TRAINING_LOG=1.
    """
    if not src or not out:
        return
    item = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "src": src,
        "out": out,
        "meta": meta or {},
    }
    try:
        from translation_event_logger import append_event
        append_event("TRAINING_SAMPLE", item, source_module="TITANMAIN")
    except Exception:
        pass
    try:
        from legacy_log_control import legacy_training_log_enabled
        if not legacy_training_log_enabled():
            return
    except Exception:
        return
    try:
        with open(TRAIN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ==============================================================================
# TRANSLATOR (Argos + cache)  [FIX: robust language-code + warn once]
# ==============================================================================
_ARGOS_LANGS = None
_ARGOS_TRANSLATORS = {}
_ARGOS_WARN_ONCE = set()

def _argos_refresh_langs():
    global _ARGOS_LANGS
    try:
        _ARGOS_LANGS = argostranslate.translate.get_installed_languages()
    except Exception:
        _ARGOS_LANGS = []
    return _ARGOS_LANGS

def _argos_find_lang(code: str):
    """
    Argos kadang pakai code varian (mis: id_ID, zh_CN).
    Cari exact dulu, lalu prefix match.
    """
    if not code:
        return None
    langs = _ARGOS_LANGS if _ARGOS_LANGS is not None else _argos_refresh_langs()

    for l in langs:
        if getattr(l, "code", None) == code:
            return l

    for l in langs:
        c = getattr(l, "code", "") or ""
        if c.startswith(code):
            return l
    return None

def _argos_get_translator(src_code: str, dst_code: str):
    src = _argos_find_lang(src_code)
    dst = _argos_find_lang(dst_code)
    if not src or not dst:
        raise RuntimeError(f"Argos language missing: {src_code}->{dst_code}")

    key = (src.code, dst.code)
    tr = _ARGOS_TRANSLATORS.get(key)
    if tr is None:
        tr = src.get_translation(dst)
        if tr is None:
            raise RuntimeError(f"Argos translation missing: {src.code}->{dst.code}")
        _ARGOS_TRANSLATORS[key] = tr
    return tr

def _argos_translate(text: str, src: str, dst: str) -> str:
    tr = _argos_get_translator(src, dst)
    return tr.translate(text)

def _argos_warn_once(tag: str, msg: str):
    if tag in _ARGOS_WARN_ONCE:
        return
    _ARGOS_WARN_ONCE.add(tag)
    log(msg)

def argos_print_status():
    langs = _argos_refresh_langs()
    codes = [getattr(l, "code", "?") for l in langs]
    log(f"[ARGOS] Installed languages: {codes}")

    def _has_pair(a, b):
        try:
            _ = _argos_get_translator(a, b)
            return True
        except Exception:
            return False

    ok_en_id = _has_pair("en", "id")
    ok_zh_en = _has_pair("zh", "en")
    ok_zh_id = _has_pair("zh", "id")

    log(f"[ARGOS] Pairs: en->id={'OK' if ok_en_id else 'MISSING'} | zh->en={'OK' if ok_zh_en else 'MISSING'} | zh->id={'OK' if ok_zh_id else 'MISSING'}")


# ------------------------------------------------------------------------------
# v8.1 translation engine adapter
# ------------------------------------------------------------------------------
TRANSLATION_ENGINE = None

def _argos_translate_direct(text: str) -> str:
    """Pure Argos path used by translation_engine.py, intentionally no cache/bridge recursion."""
    if not text:
        return ""
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in text)
    if has_cjk:
        try:
            return _argos_translate(text, "zh", "id")
        except Exception:
            temp = _argos_translate(text, "zh", "en")
            return _argos_translate(temp, "en", "id")
    return _argos_translate(text, "en", "id")


def _get_translation_engine():
    global TRANSLATION_ENGINE
    if TRANSLATION_ENGINE is None:
        try:
            from translation_engine import get_engine
            TRANSLATION_ENGINE = get_engine(BASE_DIR, _argos_translate_direct, logger=log)
            log("[TRANSLATION] Engine initialized.")
        except Exception as e:
            TRANSLATION_ENGINE = False
            log(f"[TRANSLATION] Engine disabled -> legacy Argos path: {e}")
    return TRANSLATION_ENGINE if TRANSLATION_ENGINE is not False else None


def offline_translate_ram(text: str) -> str:
    global LAST_TRANSLATION_META
    LAST_TRANSLATION_META = {}
    # Always output to Bahasa Indonesia (id). v8.1 delegates strategy/cache/fast/online logic
    # to translation_engine.py, while keeping this public function for the existing TranslatorWorker.
    if not text:
        return ""

    bridge = _get_runtime_bridge()
    engine = _get_translation_engine() if ORT_RUNTIME_STRATEGY_ENABLED else None
    if engine:
        try:
            out, meta = engine.translate(text, bridge=bridge)
            if bridge and isinstance(meta, dict) and meta.get("ms") is not None:
                try:
                    bridge.observe_translate_ms(float(meta.get("ms") or 0))
                except Exception:
                    pass
            if out:
                LAST_TRANSLATION_META = dict(meta or {})
                # Maintain small legacy in-memory map for UI cache-hit display without forcing giant JSON writes.
                if len(TRANSLATION_MEMORY) < int(os.environ.get("ORT_LEGACY_MEM_MAX", "1200")) or text in TRANSLATION_MEMORY:
                    TRANSLATION_MEMORY[text] = out
                return out
        except Exception as e:
            _argos_warn_once("TRANSLATION_ENGINE_FAIL", f"[TRANSLATION] Engine FAIL -> legacy Argos path: {e}")

    # Legacy fallback kept intact and safe.
    if bridge:
        try:
            text = bridge.pre_translate_text(text)
        except Exception:
            pass
    if not text:
        return ""

    cache_allowed = True
    if bridge:
        try:
            cache_allowed = bridge.should_cache(text)
        except Exception:
            cache_allowed = True

    if text in TRANSLATION_MEMORY:
        return TRANSLATION_MEMORY[text]

    if bridge and cache_allowed:
        try:
            vault_hit = bridge.vault_get(text)
            if vault_hit:
                TRANSLATION_MEMORY[text] = vault_hit
                return vault_hit
        except Exception:
            pass

    try:
        out = (_argos_translate_direct(text) or "").strip()
        if bridge and out:
            try:
                out = bridge.post_translate_text(text, out, context_tags=[ORT_GAME_OVERRIDE, ORT_MODEL_GROUP, ORT_MODEL_KEY, ORT_CORE_PROFILE])
            except Exception:
                pass
        if out:
            if cache_allowed:
                TRANSLATION_MEMORY[text] = out
                if bridge:
                    try:
                        bridge.vault_store(text, out)
                    except Exception:
                        pass
            return out
        return text
    except Exception as e:
        _argos_warn_once("ARGOS_FAIL", f"[ARGOS] Translate FAIL (cek model en->id / zh->en): {e}")
        if bridge:
            try:
                return bridge.failover_translate(text)
            except Exception:
                pass
        return text

# ==============================================================================
# TEXT CLEAN / WRAP
# ==============================================================================
_ZWSP = "\u200b"

def _soft_wrap_long_tokens(s: str, max_run: int = 18) -> str:
    if not s:
        return s
    out = []
    for tok in s.split(" "):
        if len(tok) > max_run and not re.search(r"[\/\\]", tok):
            chunks = [tok[i:i+max_run] for i in range(0, len(tok), max_run)]
            out.append(_ZWSP.join(chunks))
        else:
            out.append(tok)
    return " ".join(out)

def _strip_ocr_digit_noise(s: str) -> str:
    if not s:
        return s
    # v8.4.5: do not remove meaningful single digits blindly.  Older logic
    # stripped standalone numbers and hurt lines such as "1.5 meters" or
    # "2 ELIDs".  Only remove high-confidence UI numeric garbage.
    try:
        from app.ocr.number_guard import strip_numeric_ui_noise, normalize_numeric_ocr
        s = normalize_numeric_ocr(s)
        s = strip_numeric_ui_noise(s)
    except Exception:
        s = re.sub(r"^\s*(?:\d+\]|\d+\)|\d+\||\(\@|\@\)|\[\d+\])", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def normalize_ocr_text(raw: str) -> str:
    if raw is None:
        return ""
    s = raw.replace("\t", " ").strip()
    s = re.sub(r"\s{2,}", " ", s)
    # v8.1: normalize common OCR noise before speaker detection/cache/translation.
    try:
        from app.ocr.ocr_noise_normalizer import normalize_ocr_noise
        s = normalize_ocr_noise(s)
    except Exception:
        pass
    try:
        from app.ocr.number_guard import normalize_numeric_ocr
        s = normalize_numeric_ocr(s)
    except Exception:
        pass
    if ORT_GFL_LAYOUT:
        try:
            from app.games.gfl_profile import normalize_gfl_text
            s = normalize_gfl_text(s)
        except Exception:
            pass
    return s


def _should_reject_ocr_pipeline_text(text: str) -> tuple[bool, str]:
    if not ORT_OCR_NOISE_REJECT:
        return False, "disabled"
    try:
        from app.ocr.ocr_noise_normalizer import should_reject_ocr_text
        return should_reject_ocr_text(text)
    except Exception:
        return False, "unavailable"

# ==============================================================================
# DIALOG/MONOLOG + SPEAKER CORE (noise-safe)
# ==============================================================================
STOP_FIRST = {
    "the","a","an","in","on","at","by","for","from","to","of","as","and","or","but",
    "if","then","when","while","under","over","with","without","this","that","these","those",
    "i","we","you","he","she","they","it","not","no","yes","even","so","because","there",
    "contrary","seemingly","unsure","seeing","suddenly","however","meanwhile","perhaps","maybe",
}
VERB_BLOCK = {"was","is","are","were","be","been","being","do","did","does","have","has","had","will","would","should","could"}
ROLE_HINTS = [
    "news presenter","presenter","announcer","narrator","operator system","operator",
    "system","judge","reporter","broadcast","speaker",
]

_RX_UNIQUE = re.compile(
    r"\b(?:[A-Z]\.){2,}[A-Z]?\b"
    r"|\b[A-Z]{2,}(?:-[0-9A-Z]{1,})+\b"
    r"|\b[0-9]{2,}\.[A-Z]\b"
    r"|\b[A-Z]{3,}[0-9]{1,}\b"
)
_RX_SPEAKER_COLON = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\-'\s]{1,32})\s*[:：\-]\s*(.+)$")

def _canonical_title(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    parts = s.split()
    out = []
    for p in parts:
        if p.isupper() and len(p) <= 6:
            out.append(p)
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return " ".join(out)

def _is_monolog_like(raw: str) -> bool:
    if not raw:
        return False
    t = raw.strip()
    return t.startswith(("(", "（"))

def _is_unique_like(name: str) -> bool:
    if not name:
        return False
    if _RX_UNIQUE.search(name):
        return True
    if re.search(r"\d", name):
        return True
    return False

def _looks_noise_token(tok: str) -> bool:
    if not tok:
        return True
    t = tok.strip()
    if len(t) <= 1:
        return True
    if all(c in "Il|1'" for c in t):
        return True
    if len(t) <= 6 and len(set(t)) <= 2 and (("I" in t) or ("l" in t) or ("1" in t) or ("|" in t)):
        return True
    return False

def _is_speaker_candidate_colon(sp: str) -> bool:
    if not sp:
        return False
    if ORT_GFL_SPEAKER_ROI:
        try:
            from app.games.gfl_profile import canonical_speaker
            if canonical_speaker(sp):
                return True
        except Exception:
            pass
    toks = sp.strip().split()
    if not (1 <= len(toks) <= 3):
        return False
    for t in toks:
        tl = t.lower().strip("'-_")
        if not tl:
            return False
        if tl in STOP_FIRST or tl in VERB_BLOCK:
            return False
        if _is_unique_like(t):
            return False
        if _looks_noise_token(t):
            return False
        if t.isupper() and len(t) <= 6:
            continue
        if not t[:1].isalpha() or not t[:1].isupper():
            return False
    return True

def _learn_speaker(name: str):
    if not name:
        return
    name = name.strip()
    if len(name) < 2:
        return
    gfl_seeded = False
    if ORT_GFL_SPEAKER_ROI:
        try:
            from app.games.gfl_profile import canonical_speaker
            canonical = canonical_speaker(name)
            if canonical:
                name = canonical
                gfl_seeded = True
        except Exception:
            pass
    if _is_unique_like(name) and not gfl_seeded:
        return
    if _looks_noise_token(name) and not gfl_seeded:
        return

    low = name.lower()
    if low in STOP_FIRST or low in VERB_BLOCK:
        return
    try:
        from app.translation.speaker_candidate_gate import is_valid_speaker_candidate, record_candidate
        ok, why = is_valid_speaker_candidate(name)
        record_candidate(PROJECT_ROOT, name, context="speaker_learn")
        if not ok:
            log(f"[LEARN] Speaker candidate held: {name} | reason={why}")
            return
    except Exception:
        pass

    try:
        from app.learning.learning_quarantine import should_promote_learning
        ok_promote, q_reason = should_promote_learning(PROJECT_ROOT, "speaker", name, min_hits=int(os.environ.get("ORT_LEARNING_QUARANTINE_SPEAKER_HITS", "2")), context="speaker_learn")
        if not ok_promote:
            log(f"[LEARN] Speaker candidate quarantined: {name} | reason={q_reason}")
            return
    except Exception:
        pass

    counts = NPC_DATABASE.setdefault("counts", {})
    counts[name] = int(counts.get(name, 0)) + 1

    if counts[name] < SPEAKER_PROMOTE_HITS:
        return

    known = set(NPC_DATABASE.get("known", []))
    if name in known:
        return
    known.add(name)
    NPC_DATABASE["known"] = sorted(known, key=len, reverse=True)

    _safe_save_json(NPC_FILE, NPC_DATABASE)
    log(f"[LEARN] npc_database saved (promote_speaker) | known={len(NPC_DATABASE['known'])}")
    log(f"[LEARN] New speaker learned: {name}")

def split_speaker_and_dialog(raw_text: str):
    if not raw_text:
        return "DIALOG", None, ""

    raw = normalize_ocr_text(raw_text)

    if _is_monolog_like(raw):
        dlg = _strip_ocr_digit_noise(raw)
        return "MONOLOG", None, dlg

    s = raw
    s = re.sub(r"^[^A-Za-z]+", "", s).strip()
    s = _strip_ocr_digit_noise(s)

    if not s:
        return "DIALOG", None, ""

    # v8.7.6 P0: GFL2 fallback speaker labeling is exact-only.  Name ROI is
    # authoritative; when it is unavailable for an enqueued frame we may still
    # accept an official/approved exact prefix, but never promote generic
    # hyphen/colon text such as ``DP-'5 an`` into a false ``DP`` speaker.
    if ORT_GFL2_SPEAKER_GATE and ORT_GFL2_EXACT_FALLBACK_ONLY:
        try:
            from app.identity.speaker_registry import speaker_exact_names
            exact_names = speaker_exact_names("GFL2_EXILIUM")
        except Exception:
            exact_names = []
        low_s = s.lower()
        for nm in sorted(exact_names, key=len, reverse=True):
            name = str(nm or "").strip()
            if not name:
                continue
            low_name = name.lower()
            if low_s == low_name:
                return "DIALOG", name, ""
            if low_s.startswith(low_name):
                tail = s[len(name):]
                if tail and (tail[0].isspace() or tail[0] in ":：|–—"):
                    dlg = re.sub(r"^[\|\.\-–—:：\s]+", "", tail).strip()
                    dlg = _strip_ocr_digit_noise(dlg)
                    return "DIALOG", name, dlg
        if _RX_SPEAKER_COLON.match(s):
            try:
                from translation_event_logger import append_event
                append_event("GFL2_FALLBACK_SPEAKER_REJECTED", {"raw_text": s[:180], "reason": "not_exact_official_or_approved"}, source_module="TITANMAIN")
                append_event("FALSE_SPEAKER_BLOCKED", {"raw_text": s[:180], "game": "GFL2_EXILIUM"}, source_module="TITANMAIN")
            except Exception:
                pass
        return "DIALOG", None, s

    m = _RX_SPEAKER_COLON.match(s)
    if m:
        sp_raw = m.group(1).strip()
        dlg = (m.group(2) or "").strip()
        if _is_speaker_candidate_colon(sp_raw):
            sp = _canonical_title(sp_raw)
            if ORT_GFL_SPEAKER_ROI:
                try:
                    from app.games.gfl_profile import canonical_speaker
                    sp = canonical_speaker(sp_raw) or sp
                except Exception:
                    pass
            dlg = re.sub(r"^[\|\.\-–—:：\s]+", "", dlg).strip()
            dlg = _strip_ocr_digit_noise(dlg)
            if sp:
                _learn_speaker(sp)
            return "DIALOG", sp, dlg
        return "DIALOG", None, s

    try:
        from app.identity.speaker_registry import speaker_exact_names
        known = speaker_exact_names(ORT_GAME_OVERRIDE) if ORT_GAME_OVERRIDE in {"GFL2", "GFL2_EXILIUM", "GFL", "WUWA"} else NPC_DATABASE.get("known", [])
    except Exception:
        known = NPC_DATABASE.get("known", [])
    for nm in sorted(known, key=len, reverse=True):
        if not nm:
            continue
        if s.lower().startswith(nm.lower() + " "):
            dlg = s[len(nm):].strip()
            dlg = re.sub(r"^[\|\.\-–—:：\s]+", "", dlg).strip()
            dlg = _strip_ocr_digit_noise(dlg)
            return "DIALOG", nm, dlg
        if s.lower() == nm.lower():
            return "DIALOG", nm, ""

    low = s.lower()
    for role in sorted(ROLE_HINTS, key=len, reverse=True):
        if low.startswith(role + " "):
            sp = _canonical_title(role)
            dlg = s[len(role):].strip()
            dlg = re.sub(r"^[\|\.\-–—:：\s]+", "", dlg).strip()
            dlg = _strip_ocr_digit_noise(dlg)
            _learn_speaker(sp)
            return "DIALOG", sp, dlg
        if low == role:
            sp = _canonical_title(role)
            _learn_speaker(sp)
            return "DIALOG", sp, ""

    # v8.7: GFL narration has no speaker row.  Never promote the first word of
    # a GFL body/narration line as NPC; real speakers are emitted by Name ROI
    # or already-known explicit prefix processing above.
    if ORT_GFL_SPEAKER_ROI or ORT_GFL2_SPEAKER_GATE:
        # v8.7.1: GFL/GFL2 only display/learn speakers from seeded-known prefixes or explicit validated slots.
        # This blocks narrative starts such as Betterto/Hereyes/Tillthe from becoming NPC names.
        return "DIALOG", None, s

    tokens = s.split()
    if tokens:
        first_raw = tokens[0]
        first = re.sub(r"[^A-Za-z'\-]", "", first_raw)
        if first and len(first) <= 24 and first.lower() not in STOP_FIRST and first.lower() not in VERB_BLOCK and not _is_unique_like(first):
            if not _looks_noise_token(first_raw):
                looks_name = first[:1].isupper() or (first.isupper() and len(first) <= 8)
                if looks_name and len(tokens) >= 2:
                    sp = _canonical_title(first)
                    dlg = s[len(tokens[0]):].strip()
                    dlg = re.sub(r"^[\|\.\-–—:：\s]+", "", dlg).strip()
                    dlg = _strip_ocr_digit_noise(dlg)
                    _learn_speaker(sp)
                    return "DIALOG", sp, dlg

    return "DIALOG", None, s

# ==============================================================================
# UNIQUE TERMS + PUNCT
# ==============================================================================
def _promote_unique_terms(src_text: str):
    if not src_text:
        return
    hits = set(m.group(0) for m in _RX_UNIQUE.finditer(src_text))
    if not hits:
        return

    known_speakers_lower = {k.lower() for k in NPC_DATABASE.get("known", [])}
    known = set(UNIQUE_TERMS.get("known", []))
    promoted = []
    for t in hits:
        if t.lower() in known_speakers_lower:
            continue
        try:
            from app.learning.learning_quarantine import should_promote_learning
            ok_unique, q_reason = should_promote_learning(PROJECT_ROOT, "unique", t, min_hits=int(os.environ.get("ORT_LEARNING_QUARANTINE_UNIQUE_HITS", "2")), context="unique_term")
            if not ok_unique:
                log(f"[LEARN] Unique term quarantined: {t} | reason={q_reason}")
                continue
        except Exception:
            pass
        _unique_counts[t] += 1
        if _unique_counts[t] >= 2 and t not in known:
            known.add(t)
            promoted.append(t)

    if promoted:
        UNIQUE_TERMS["known"] = sorted(known, key=len, reverse=True)
        for t in promoted:
            log(f"[LEARN] New unique term learned: {t}")
        _safe_save_json(UNIQUE_FILE, UNIQUE_TERMS)
        log(f"[LEARN] unique_terms saved | known={len(UNIQUE_TERMS['known'])}")

def _punct_count(src_text: str):
    if not src_text:
        return
    counts = PUNCT_STATS.setdefault("counts", {})
    for key, pat in [
        ("ellipsis_3", "..."),
        ("ellipsis_unicode", "…"),
        ("question", "?"),
        ("exclaim", "!"),
    ]:
        if pat in src_text:
            counts[key] = int(counts.get(key, 0)) + src_text.count(pat)

def _preserve_tail_punct(src_text: str, out_text: str) -> str:
    if not src_text or not out_text:
        return out_text
    s = src_text.strip()
    o = out_text.strip()
    m = re.search(r"([.…\.]{3,}|…+|[!?]+|[。！？]+)$", s)
    if not m:
        return o
    tail = m.group(1)
    if o.endswith(tail):
        return o
    if re.search(r"[.!?…。！？]+$", o):
        return o
    return o + tail

def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def _highlight_terms(html_text: str, terms, color_hex: str, exclude=None):
    if not html_text or not terms:
        return html_text
    out = html_text
    exclude = exclude or set()
    for t in sorted(set(terms), key=len, reverse=True):
        if not t or t in exclude:
            continue
        rx = re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
        out = rx.sub(lambda m: f"<b style='color:{color_hex};'>{m.group(0)}</b>", out)
    return out

# ==============================================================================
# OCR ENGINE + VRAM
# ==============================================================================
def _get_vram_gb():
    if not torch.cuda.is_available():
        return None
    try:
        free, total = torch.cuda.mem_get_info()
        return free / (1024**3), total / (1024**3)
    except Exception:
        return None

def reload_ocr_engine(target_mode: str = None):
    global GLOBAL_READER, IS_USING_GPU, CURRENT_ENGINE_MODE, AUTO_GPU_FALLBACK_CPU

    if target_mode:
        CURRENT_ENGINE_MODE = target_mode

    log("")
    log("[SYSTEM] OCR ENGINE SWITCH INITIATED...")
    log(f"[CHECK] Mode: {CURRENT_ENGINE_MODE}")

    target_gpu = False

    if CURRENT_ENGINE_MODE == "FORCE_CPU":
        target_gpu = False
        log("[CHECK] Forcing CPU.")
    elif CURRENT_ENGINE_MODE == "FORCE_GPU":
        if torch.cuda.is_available():
            target_gpu = True
            name = torch.cuda.get_device_name(0)
            v = _get_vram_gb()
            if v:
                log(f"[CHECK] GPU Detected: {name} | VRAM free={v[0]:.2f}GB / total={v[1]:.2f}GB")
            else:
                log(f"[CHECK] GPU Detected: {name}")
        else:
            target_gpu = False
            log("[CHECK] GPU NOT FOUND -> CPU.")
    else:
        if torch.cuda.is_available() and not AUTO_GPU_FALLBACK_CPU:
            target_gpu = True
            v = _get_vram_gb()
            if v:
                log(f"[CHECK] AUTO_GPU GPU | free={v[0]:.2f}GB / total={v[1]:.2f}GB")
        else:
            target_gpu = False
            if AUTO_GPU_FALLBACK_CPU:
                log("[CHECK] AUTO_GPU fallback -> CPU (low VRAM protection)")
            else:
                log("[CHECK] AUTO_GPU -> CPU (no GPU detected)")

    with OCR_LOCK:
        GLOBAL_READER = None

    gc.collect()
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    try:
        reader = easyocr.Reader(["ch_sim", "en"], gpu=target_gpu)
        with OCR_LOCK:
            GLOBAL_READER = reader
        IS_USING_GPU = bool(target_gpu)
        log(f"[SUCCESS] Engine Active: {'GPU' if IS_USING_GPU else 'CPU'}")
    except Exception as e:
        log(f"[CRITICAL] OCR init failed -> fallback CPU | {e}")
        reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        with OCR_LOCK:
            GLOBAL_READER = reader
        IS_USING_GPU = False
        log("[SUCCESS] Engine Active: CPU (fallback)")

def _vram_monitor_tick():
    global _last_vram_switch_ts, CURRENT_ENGINE_MODE, AUTO_GPU_FALLBACK_CPU, _vram_low_count
    try:
        if CURRENT_ENGINE_MODE != "AUTO_GPU":
            return
        if not torch.cuda.is_available():
            return
        v = _get_vram_gb()
        if not v:
            return
        free_gb, total_gb = v

        if time.time() - _last_vram_switch_ts < VRAM_COOLDOWN_SEC:
            return

        if (not AUTO_GPU_FALLBACK_CPU) and IS_USING_GPU and free_gb < VRAM_LOW_GB:
            _vram_low_count += 1
            # v8.5.1: staged VRAM guard.  Reduce OCR first; CPU fallback only when
            # the GPU budget is critically low for repeated samples.
            if ORT_RUNTIME_OCR_RESOLUTION_PERCENT > 55:
                new_ocr = max(48, min(55, ORT_RUNTIME_OCR_RESOLUTION_PERCENT - 12))
                log(f"[VRAM] Low VRAM: {free_gb:.2f}GB/{total_gb:.2f}GB -> staged OCR downscale {ORT_RUNTIME_OCR_RESOLUTION_PERCENT}%->{new_ocr}%")
                _set_runtime_ocr_resolution(new_ocr)
                _last_vram_switch_ts = time.time()
                return
            if free_gb < VRAM_CRITICAL_GB and _vram_low_count >= 3:
                log(f"[VRAM] Critical sustained VRAM: {free_gb:.2f}GB/{total_gb:.2f}GB -> AUTO fallback CPU")
                AUTO_GPU_FALLBACK_CPU = True
                _last_vram_switch_ts = time.time()
                reload_ocr_engine()
                save_cache("vram_fallback_cpu")
                return
            log(f"[VRAM] Low VRAM observed: {free_gb:.2f}GB/{total_gb:.2f}GB | keeping GPU, waiting for sustained critical condition")
            return

        if free_gb >= VRAM_RECOVER_GB:
            _vram_low_count = 0

        if AUTO_GPU_FALLBACK_CPU and free_gb > VRAM_RECOVER_GB:
            log(f"[VRAM] VRAM recovered: {free_gb:.2f}GB/{total_gb:.2f}GB -> AUTO back GPU")
            AUTO_GPU_FALLBACK_CPU = False
            _last_vram_switch_ts = time.time()
            reload_ocr_engine()
            save_cache("vram_recover_gpu")
            return

    except Exception as e:
        log(f"[VRAM] monitor error (ignored): {e}")

# ==============================================================================
# MULTI-MONITOR helpers
# ==============================================================================
def get_virtual_desktop_rect() -> QRect:
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    left = min(s.geometry().left() for s in screens)
    top = min(s.geometry().top() for s in screens)
    right = max(s.geometry().right() for s in screens)
    bottom = max(s.geometry().bottom() for s in screens)
    return QRect(left, top, right - left + 1, bottom - top + 1)

def pick_screen_for_region(region: dict):
    rx = int(region["left"])
    ry = int(region["top"])
    rw = int(region["width"])
    rh = int(region["height"])
    rrect = QRect(rx, ry, rw, rh)

    best = None
    best_area = -1
    for s in QGuiApplication.screens():
        g = s.geometry()
        inter = g.intersected(rrect)
        area = inter.width() * inter.height()
        if area > best_area:
            best_area = area
            best = s
    return best or QGuiApplication.primaryScreen()

# ==============================================================================
# UI: Snipping (robust overlay)
# ==============================================================================
class SnippingWidget(QWidget):
    selection_made = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        self.begin = QPoint()
        self.end = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)

        self.vrect = get_virtual_desktop_rect()
        self.setGeometry(self.vrect)

        log(f"[SNIP] Creating snip overlay on {len(QGuiApplication.screens())} screen(s)")
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.rubberBand.setGeometry(QRect(self.begin, self.end))
        self.rubberBand.show()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.rubberBand.setGeometry(QRect(self.begin, self.end).normalized())

    def mouseReleaseEvent(self, event):
        self.close()
        rect = QRect(self.begin, self.end).normalized()
        if rect.width() > 10 and rect.height() > 10:
            global_left = self.vrect.left() + rect.left()
            global_top = self.vrect.top() + rect.top()
            self.selection_made.emit({
                "top": int(global_top),
                "left": int(global_left),
                "width": int(rect.width()),
                "height": int(rect.height()),
            })

# ==============================================================================
# UI: Indicators (Mode + Engine + ms + Game)  [INSIDE BOX]
# ==============================================================================
def get_mode_badge_state():
    if CAPTURE_MODE == 1 and AUTO_SNAPSHOT_ON:
        return ("INTERVAL", "INTERVAL", "#FF4D4D")
    if CAPTURE_MODE == 1 and not AUTO_SNAPSHOT_ON:
        return ("FREEZE", "FREEZE", "#4DA3FF")
    if CAPTURE_MODE == 2:
        return ("HIGH", "HIGH", "#FFD700")
    return ("AUTO", "AUTO", "#00FF66")

def get_game_badge_html():
    raw = (ORT_GAME_OVERRIDE or "GFL2_EXILIUM").upper()
    if "GFL2" in raw:
        return (
            "<span style='color:#00FF66; font-weight:900; font-family:Segoe UI; font-size:12px;'>GFL</span>"
            "<span style='color:#FF9900; font-weight:900; font-family:Segoe UI; font-size:12px;'>2</span>"
        )
    elif "WUTHERING" in raw or "WUWA" in raw:
        text = "WUWA"
    else:
        text = (raw[:8] if raw else "...").replace("_", "")
    return (
        f"<span style='color:#66CCFF; font-weight:900; font-family:Segoe UI; font-size:12px;'>{text}</span>"
    )

class EngineLIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 22)
        self.mode_text = "GPU"

    def set_mode(self, txt: str):
        self.mode_text = txt
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 0))
        p.drawRect(self.rect())

        color = QColor(0, 255, 0) if IS_USING_GPU else QColor(255, 80, 80)
        if CURRENT_ENGINE_MODE == "AUTO_GPU":
            color = QColor(120, 220, 255) if IS_USING_GPU else QColor(255, 160, 80)

        p.setPen(color)
        p.drawLine(6, 6, 6, 18)
        p.drawLine(6, 6, 18, 6)

        p.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.drawText(QRect(22, 2, 36, 18), Qt.AlignVCenter | Qt.AlignLeft, self.mode_text)

class ModeIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__("AUTO", parent)
        self.setFixedHeight(18)
        self.setMinimumWidth(54)
        self.setAlignment(Qt.AlignCenter)
        self.setVisible(True)
        self.set_mode("AUTO", "#00FF66")

    def set_mode(self, text: str, color_hex: str):
        self.setText(text)
        self.setStyleSheet(
            "background-color: rgba(0,0,0,140);"
            f"border:1px solid {color_hex};"
            "border-radius:6px;"
            f"color: {color_hex};"
            "font-weight: bold;"
            "font-family: 'Segoe UI';"
            "font-size: 10px;"
            "padding-left: 6px; padding-right: 6px;"
        )
        fm = self.fontMetrics()
        self.setFixedWidth(max(54, fm.horizontalAdvance(text) + 16))

class TopRightStatus(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(260, 26)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.mode_badge = ModeIndicator(self)
        self.engine = EngineLIndicator(self)
        lay.addWidget(self.mode_badge)
        lay.addWidget(self.engine)

        self.ms_badge = QLabel(self)
        self.ms_badge.setAlignment(Qt.AlignCenter)
        self.ms_badge.setFixedHeight(22)
        self.ms_badge.setMinimumWidth(56)
        self.ms_badge.setStyleSheet(
            "background-color: rgba(0,0,0,160);"
            "border: 1px solid rgba(255,255,255,0.20);"
            "border-radius: 6px;"
            "padding-left: 6px; padding-right: 6px;"
            "color:#66CCFF; font-weight:900; font-family:Segoe UI; font-size:11px;"
        )
        self.ms_badge.setText("0ms")
        lay.addWidget(self.ms_badge)

        self.game_badge = QLabel(self)
        self.game_badge.setTextFormat(Qt.RichText)
        self.game_badge.setAlignment(Qt.AlignCenter)
        self.game_badge.setFixedHeight(22)
        self.game_badge.setMinimumWidth(48)
        self.game_badge.setStyleSheet(
            "background-color: rgba(0,0,0,160);"
            "border: 1px solid rgba(255,255,255,0.20);"
            "border-radius: 6px;"
            "padding-left: 6px; padding-right: 6px;"
        )
        self.game_badge.setText(get_game_badge_html())
        lay.addWidget(self.game_badge)

    def refresh(self):
        engine_txt = "GPU" if IS_USING_GPU else "CPU"
        if CURRENT_ENGINE_MODE == "AUTO_GPU":
            engine_txt = "AUTO"
        self.engine.set_mode(engine_txt)

        _key, mode_text, color = get_mode_badge_state()
        self.mode_badge.set_mode(mode_text, color)
        self.mode_badge.setVisible(True)

        try:
            self.ms_badge.setText(f"{int(LAST_TRANSLATE_MS)}ms")
        except Exception:
            self.ms_badge.setText("0ms")

        try:
            self.game_badge.setText(get_game_badge_html())
        except Exception:
            pass

# ==============================================================================
# UI: Main Translation Box (overlay normal)
# ==============================================================================
class TranslationBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.addWidget(self.container)

        self.mode_dot = QLabel(self)
        self.mode_dot.setFixedSize(12, 12)

        self.speaker_label = QLabel("", self)
        self.speaker_label.setTextFormat(Qt.RichText)
        self.speaker_label.setWordWrap(True)

        self.dialog_label = QLabel("", self)
        self.dialog_label.setTextFormat(Qt.RichText)
        self.dialog_label.setWordWrap(True)

        self.status = TopRightStatus(self)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(self.mode_dot)
        top_row.addSpacing(6)
        top_row.addWidget(self.speaker_label, stretch=1)
        top_row.addWidget(self.status, stretch=0, alignment=Qt.AlignRight | Qt.AlignVCenter)

        self.container_layout.addLayout(top_row)
        self.container_layout.addWidget(self.dialog_label)

        self.apply_style()
        self.update_mode_dot()
        self.refresh_status()

    def refresh_status(self):
        try:
            self.status.refresh()
        except Exception:
            pass

    def update_mode_dot(self):
        _key, _text, color = get_mode_badge_state()
        self.mode_dot.setStyleSheet(f"background-color:{color}; border-radius:6px; border:1px solid white;")

    def apply_style(self):
        base_css = f"font-family:'Segoe UI'; font-weight:bold; font-size:{CURRENT_FONT_SIZE}px;"
        self.speaker_label.setStyleSheet(base_css)
        self.dialog_label.setStyleSheet(base_css)

        if CURRENT_VISUAL_ID == 2:
            self.container.setStyleSheet(
                ".QWidget { background-color: rgba(30,30,30,160); border-radius: 10px;"
                "border: 1px solid rgba(255,255,255,0.18); border-left: 4px solid #00FF00; }"
            )
        elif CURRENT_VISUAL_ID == 1:
            self.container.setStyleSheet(
                ".QWidget { background-color: rgba(0,0,0,220); border-radius: 8px;"
                "border-left: 4px solid #00FF00; }"
            )
        else:
            self.container.setStyleSheet(
                ".QWidget { background-color: rgba(0,0,0,70); border-radius: 8px; }"
            )

        self.update_mode_dot()
        self.refresh_status()

    def set_text(self, speaker_html: str, dialog_html: str):
        self.speaker_label.setText(speaker_html or "")
        self.dialog_label.setText(dialog_html or "")
        self.apply_style()
        self._relayout()

    def _relayout(self):
        fixed_w = max(300, self.width() - 26)
        self.speaker_label.setFixedWidth(fixed_w)
        self.dialog_label.setFixedWidth(fixed_w)
        self.speaker_label.adjustSize()
        self.dialog_label.adjustSize()

# ==============================================================================
# OverlayHost: monitor-locked host (normal mode)
# ==============================================================================
class OverlayHost(QWidget):
    def __init__(self, screen, region):
        super().__init__()
        self.screen = screen
        self.region = region

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        g = self.screen.geometry()
        self.setGeometry(g)

        try:
            if self.windowHandle():
                self.windowHandle().setScreen(self.screen)
        except Exception:
            pass

        self.box = TranslationBox(self)
        self.box.show()
        self.reposition_box()

    def refresh_status(self):
        self.box.refresh_status()

    def update_mode_dot(self):
        self.box.update_mode_dot()

    def apply_visual(self):
        self.box.apply_style()
        self.refresh_status()

    def update_text(self, speaker_html: str, dialog_html: str):
        self.box.set_text(speaker_html, dialog_html)
        self.reposition_box()

    def hide_translation(self):
        self.hide()

    def show_translation(self):
        self.show()
        self.raise_()
        self.refresh_status()
        self.reposition_box()

    def reposition_box(self):
        sg = self.screen.geometry()

        rx = int(self.region["left"])
        ry = int(self.region["top"])
        rw = int(self.region["width"])
        rh = int(self.region["height"])

        rel_left = rx - sg.left()
        rel_top = ry - sg.top()

        desired_w = int(rw * CURRENT_WIDTH_SCALE)
        desired_w = max(320, desired_w)
        desired_w = min(desired_w, sg.width() - 20)

        self.box._relayout()
        content_h = max(90, min(420, self.box.speaker_label.height() + self.box.dialog_label.height() + 30))

        x = rel_left + int((rw - desired_w) / 2)
        x = max(10, min(x, sg.width() - desired_w - 10))

        if CURRENT_POS_MODE == "FLOATING":
            y = rel_top - content_h - 10
        else:
            y = rel_top

        y = max(10, min(y, sg.height() - content_h - 10))

        self.box.setGeometry(x, y, desired_w, content_h)
        self.box._relayout()
        self.box.refresh_status()

# ==============================================================================
# OCR Worker (Stable live + Freeze snapshot kinds)
# ==============================================================================
class OCRWorker(QThread):
    debug = pyqtSignal(str)
    snapshot_done = pyqtSignal(str, str)  # kind, pushed_text

    def __init__(self, region):
        super().__init__()
        self.region = region
        self.running = True
        self.last_pushed = ""
        self.vote_buf = deque(maxlen=6)
        self._snap_kind = None
        self._snap_lock = threading.Lock()
        self.last_ocr_ms = 0.0
        self.last_capture_ms = 0.0
        self.last_preprocess_ms = 0.0
        self.stable_commit_enabled = os.environ.get("ORT_STABLE_TEXT_COMMIT", "1") != "0"
        try:
            from app.ocr.stable_text_commit import StableTextCommitter
            self.stable_committer = StableTextCommitter(
                min_age_ms=int(os.environ.get("ORT_STABLE_COMMIT_MS", "180")),
                min_repeats=int(os.environ.get("ORT_STABLE_COMMIT_REPEATS", "2")),
            )
        except Exception:
            self.stable_committer = None
        self.scheduler_profile = os.environ.get("ORT_DIALOG_SCHEDULER_PROFILE", "interval_auto")
        self.image_hash_enabled = os.environ.get("ORT_IMAGE_HASH_GATE", "1") != "0"
        try:
            from app.ocr.image_hash_gate import ImageHashGate
            self.image_hash_gate = ImageHashGate.from_env(self.scheduler_profile)
        except Exception:
            self.image_hash_gate = None
        self._last_hash_skip_log = 0.0
        self._last_noise_skip_log = 0.0
        self._last_numeric_dual_pass_ts = 0.0
        self._last_numeric_dual_pass_text = ""
        self.last_numeric_retry_ms = 0.0
        self.last_body_ocr_ms = 0.0
        self.last_readability_rescue_ms = 0.0
        self.last_runtime_ocr_percent = int(ORT_RUNTIME_OCR_RESOLUTION_PERCENT)
        self.last_readability_score = 0.0
        self.last_readability_rescue_reason = ""
        self._last_readability_retry_ts = 0.0
        self._last_gfl_status_log = 0.0
        self._last_gfl_layout_meta = {}
        self.gfl_presence_guard = None
        if ORT_GFL_LAYOUT:
            try:
                from app.ocr.gfl_dialogue_layout import GFLDialoguePresenceGuard
                self.gfl_presence_guard = GFLDialoguePresenceGuard(miss_limit=3)
            except Exception:
                self.gfl_presence_guard = None
        self.gfl2_speaker_tracker = None
        self._last_gfl2_speaker_meta = {}
        if ORT_GFL2_SPEAKER_ROI:
            try:
                from app.ocr.gfl2_speaker_roi import GFL2SpeakerTracker
                from app.identity.speaker_registry import trusted_speaker_names, trusted_alias_map, verified_character_speaker_names
                self.gfl2_speaker_tracker = GFL2SpeakerTracker(trusted_speaker_names("GFL2_EXILIUM"), alias_map=trusted_alias_map("GFL2_EXILIUM"), verified_exact_names=verified_character_speaker_names("GFL2_EXILIUM"))
            except Exception as exc:
                self.debug.emit(f"[GFL2] Speaker ROI unavailable: {type(exc).__name__}")

    def _should_run_ocr_for_frame(self, frame_rgb, manual: bool = False):
        if not self.image_hash_enabled or self.image_hash_gate is None:
            return True
        try:
            decision = self.image_hash_gate.should_run(frame_rgb, manual=manual)
            if decision.run:
                return True
            now = time.time()
            if now - self._last_hash_skip_log > 3.0:
                self._last_hash_skip_log = now
                try:
                    from translation_event_logger import append_event
                    append_event("OCR_HASH_SKIPPED", {"reason": decision.reason, "distance": decision.distance, "profile": self.scheduler_profile}, source_module="TITANMAIN")
                except Exception:
                    pass
            if decision.sleep_ms > 0:
                self.msleep(min(int(decision.sleep_ms), 80))
            return False
        except Exception:
            return True

    def _apply_gfl_frame_policy(self, frame_rgb):
        if not ORT_GFL_LAYOUT:
            return frame_rgb
        try:
            if self.gfl_presence_guard is not None and ORT_GFL_DIALOG_PRESENCE_GUARD:
                decision = self.gfl_presence_guard.assess(frame_rgb)
                if not decision.process:
                    now = time.time()
                    if now - self._last_gfl_status_log > 2.5:
                        self._last_gfl_status_log = now
                        self.debug.emit(f"[GFL] non-dialog frame suppressed | reason={decision.reason} | yellow={decision.yellow_ratio:.4f} dark={decision.dark_ratio:.3f}")
                        try:
                            from translation_event_logger import append_event
                            append_event("GFL_NON_DIALOG_FRAME_SKIPPED", {"reason": decision.reason, "yellow_ratio": decision.yellow_ratio, "dark_ratio": decision.dark_ratio}, source_module="TITANMAIN")
                        except Exception:
                            pass
                    return None
            if ORT_GFL_FOOTER_MASK:
                from app.ocr.gfl_dialogue_layout import mask_footer_ui
                masked, meta = mask_footer_ui(frame_rgb)
                self._last_gfl_layout_meta = meta
                return masked
        except Exception:
            return frame_rgb
        return frame_rgb

    def request_snapshot(self, kind="FAST"):
        with self._snap_lock:
            if self._snap_kind is None:
                self._snap_kind = kind

    def _take_snapshot_kind(self):
        with self._snap_lock:
            k = self._snap_kind
            self._snap_kind = None
            return k

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    def _resize_for_v7(self, img_rgb, scale: float):
        if abs(scale - 1.0) < 0.01:
            return img_rgb
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        return cv2.resize(img_rgb, None, fx=scale, fy=scale, interpolation=interpolation)

    def _prep_stable_at_percent(self, img_rgb, percent: int):
        """Prepare one OCR view while preserving the original dialog geometry."""
        scale = max(0.35, min(1.20, float(percent) / 100.0))
        # v8.4.5: for wide GFL2 dialog boxes, trim only tiny UI margins.
        if ORT_LITE_WIDE_DIALOG_FILTER:
            try:
                h, w = img_rgb.shape[:2]
                if w >= 1600 and h >= 220:
                    top = max(0, int(h * 0.03))
                    bottom = max(top + 40, int(h * 0.98))
                    img_rgb = img_rgb[top:bottom, :, :]
            except Exception:
                pass
        up = self._resize_for_v7(img_rgb, scale)
        return cv2.cvtColor(up, cv2.COLOR_RGB2GRAY)

    def _prep_stable(self, img_rgb):
        # v8.7.6: initial OCR follows applied setting; Readability Guard may
        # request exactly one higher-resolution retry before translation/cache.
        return self._prep_stable_at_percent(img_rgb, ORT_RUNTIME_OCR_RESOLUTION_PERCENT)

    def _prep_freeze_variants(self, img_rgb):
        # Freeze tetap sedikit lebih kuat, tetapi tidak memaksa upscale besar saat Safe Game aktif.
        base_scale = max(ORT_RUNTIME_OCR_SCALE, 0.45)
        if not ORT_HEAVY_GAME_SAFE:
            base_scale = max(base_scale, 1.0 if IS_USING_GPU else 0.95)
        up = self._resize_for_v7(img_rgb, base_scale)
        gray = cv2.cvtColor(up, cv2.COLOR_RGB2GRAY)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        v1 = clahe.apply(gray)

        _, v2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return [("clahe", v1), ("otsu", v2)]

    def _queue_push(self, mode_name: str, text: str, meta_extra: dict | None = None):
        text = (text or "").strip()
        if len(text) < 2:
            return False
        reject, why = _should_reject_ocr_pipeline_text(text)
        if reject:
            now = time.time()
            if now - getattr(self, "_last_noise_skip_log", 0.0) > 2.5:
                self._last_noise_skip_log = now
                try:
                    self.debug.emit(f"[OCR] noise skipped | reason={why} | text={text[:60]}")
                except Exception:
                    pass
            return False
        if mode_name == "STABLE" and self.stable_commit_enabled and self.stable_committer is not None:
            try:
                res = self.stable_committer.update(text)
                if not res.commit:
                    return False
                text = res.text
            except Exception:
                pass
        if text == self.last_pushed:
            return False

        try:
            dropped = 0
            if ORT_RESPONSIVE_STORY_MODE and mode_name in {"STABLE", "HIGH_LATENCY"}:
                target = max(0, int(os.environ.get("ORT_RESPONSIVE_QUEUE_TARGET", "1")))
                while OCR_TEXT_QUEUE.qsize() > target:
                    try:
                        OCR_TEXT_QUEUE.get_nowait()
                        dropped += 1
                    except queue.Empty:
                        break
                if dropped:
                    try:
                        from translation_event_logger import append_event
                        append_event("RESPONSIVE_QUEUE_COALESCED", {"dropped": dropped, "target": target, "mode": mode_name, "text_length": len(text)}, source_module="TITANMAIN")
                    except Exception:
                        pass
            elif mode_name == "STABLE":
                while OCR_TEXT_QUEUE.qsize() > 6:
                    try:
                        OCR_TEXT_QUEUE.get_nowait()
                    except queue.Empty:
                        break
        except Exception:
            pass

        global LATEST_SPEAKER_EPOCH, LATEST_SPEAKER_NAME
        meta = {"ocr_ms": float(getattr(self, "last_ocr_ms", 0.0) or 0.0), "body_ocr_ms": float(getattr(self, "last_body_ocr_ms", 0.0) or 0.0), "numeric_retry_ms": float(getattr(self, "last_numeric_retry_ms", 0.0) or 0.0), "readability_rescue_ms": float(getattr(self, "last_readability_rescue_ms", 0.0) or 0.0), "runtime_ocr_percent": int(getattr(self, "last_runtime_ocr_percent", ORT_RUNTIME_OCR_RESOLUTION_PERCENT) or ORT_RUNTIME_OCR_RESOLUTION_PERCENT), "readability_score": float(getattr(self, "last_readability_score", 0.0) or 0.0), "readability_reason": str(getattr(self, "last_readability_rescue_reason", "") or ""), "capture_ms": float(getattr(self, "last_capture_ms", 0.0) or 0.0), "preprocess_ms": float(getattr(self, "last_preprocess_ms", 0.0) or 0.0), "total_ms": float((getattr(self, "last_capture_ms", 0.0) or 0.0) + (getattr(self, "last_preprocess_ms", 0.0) or 0.0) + (getattr(self, "last_ocr_ms", 0.0) or 0.0)), "scheduler_profile": self.scheduler_profile, "enqueued_at": time.time()}
        if isinstance(meta_extra, dict):
            meta.update(meta_extra)
        speaker_now = str(((meta.get("gfl2_speaker") or {}).get("speaker") or "")).strip()
        if ORT_SPEAKER_TRANSITION_GUARD and speaker_now and speaker_now != LATEST_SPEAKER_NAME:
            old_speaker = LATEST_SPEAKER_NAME
            LATEST_SPEAKER_NAME = speaker_now
            LATEST_SPEAKER_EPOCH += 1
            try:
                from translation_event_logger import append_event
                append_event("SPEAKER_TRANSITION_DETECTED", {"previous_speaker": old_speaker, "new_speaker": speaker_now, "speaker_epoch": LATEST_SPEAKER_EPOCH}, source_module="TITANMAIN")
            except Exception:
                pass
        meta["speaker_epoch"] = int(LATEST_SPEAKER_EPOCH)
        meta["speaker_at_enqueue"] = str(LATEST_SPEAKER_NAME)
        try:
            OCR_TEXT_QUEUE.put_nowait((mode_name, text, meta))
            self.last_pushed = text
            return True
        except queue.Full:
            try:
                _ = OCR_TEXT_QUEUE.get_nowait()
            except Exception:
                pass
            try:
                OCR_TEXT_QUEUE.put_nowait((mode_name, text, meta))
                self.last_pushed = text
                self.debug.emit("[PIPE] queue=FULL -> drop oldest")
                return True
            except Exception:
                return False

    def _readtext_fast(self, img_gray, source_rgb=None):
        with OCR_LOCK:
            reader = GLOBAL_READER
        if reader is None:
            return ""
        t0 = time.time()
        self.last_readability_rescue_ms = 0.0
        self.last_runtime_ocr_percent = int(ORT_RUNTIME_OCR_RESOLUTION_PERCENT)
        self.last_readability_score = 0.0
        self.last_readability_rescue_reason = ""
        try:
            if ORT_GFL_SPEAKER_ROI:
                det = reader.readtext(img_gray, detail=1, paragraph=False)
                from app.games.gfl_profile import extract_layout_text
                raw_text, meta = extract_layout_text(det, getattr(img_gray, "shape", (1, 1)))
                self._last_gfl_layout_meta = dict(meta or {})
                return raw_text

            body_t0 = time.perf_counter()
            out = reader.readtext(img_gray, detail=0, paragraph=True)
            raw_text = " ".join(out).strip() if out else ""
            body_img = img_gray
            body_percent = int(ORT_RUNTIME_OCR_RESOLUTION_PERCENT)

            # v8.7.6 Adaptive OCR Readability Guard: on GFL2 story, a degraded
            # low-resolution result receives at most one throttled higher-scale
            # retry. Only the better raw OCR string proceeds to translation/cache.
            if ORT_ADAPTIVE_READABILITY_GUARD and ORT_GAME_OVERRIDE in {"GFL2", "GFL2_EXILIUM"} and source_rgb is not None:
                try:
                    from app.ocr.readability_guard import score_text, rescue_percent, select_better_text
                    assessment = score_text(raw_text, body_percent, ORT_OCR_STORY_MIN_PERCENT)
                    self.last_readability_score = float(assessment.score)
                    self.last_readability_rescue_reason = str(assessment.reason)
                    cooldown = max(120, int(os.environ.get("ORT_READABILITY_RESCUE_COOLDOWN_MS", "360"))) / 1000.0
                    now = time.time()
                    if assessment.needs_rescue and (now - self._last_readability_retry_ts) >= cooldown:
                        retry_percent = rescue_percent(body_percent, ORT_OCR_STORY_MIN_PERCENT, int(os.environ.get("ORT_OCR_RESCUE_MAX_PERCENT", "65")))
                        if retry_percent > body_percent:
                            rt0 = time.perf_counter()
                            retry_img = self._prep_stable_at_percent(source_rgb, retry_percent)
                            retry_out = reader.readtext(retry_img, detail=0, paragraph=True)
                            retry_text = " ".join(retry_out).strip() if retry_out else ""
                            selected, before, after, used_retry = select_better_text(raw_text, retry_text, body_percent, retry_percent, ORT_OCR_STORY_MIN_PERCENT)
                            self.last_readability_rescue_ms = (time.perf_counter() - rt0) * 1000.0
                            self._last_readability_retry_ts = now
                            if used_retry:
                                raw_text = selected
                                body_img = retry_img
                                body_percent = retry_percent
                                self.last_runtime_ocr_percent = retry_percent
                                self.last_readability_score = float(after.score)
                            try:
                                from translation_event_logger import append_event
                                append_event("OCR_READABILITY_RESCUE", {
                                    "initial_percent": int(ORT_RUNTIME_OCR_RESOLUTION_PERCENT),
                                    "retry_percent": retry_percent,
                                    "selected_percent": body_percent,
                                    "initial_score": before.score,
                                    "retry_score": after.score,
                                    "used_retry": bool(used_retry),
                                    "reason": assessment.reason,
                                    "rescue_ms": round(self.last_readability_rescue_ms, 3),
                                    "initial_text": raw_text[:160] if not used_retry else str(" ".join(out).strip())[:160],
                                    "selected_text": raw_text[:160],
                                }, source_module="TITANMAIN")
                            except Exception:
                                pass
                except Exception:
                    pass

            self.last_body_ocr_ms = (time.perf_counter() - body_t0) * 1000.0

            if ORT_GFL2_SPEAKER_ROI and self.gfl2_speaker_tracker is not None:
                try:
                    # Name ROI uses a minimum quality floor because the region is
                    # small and directly controls speaker correctness.
                    roi_img = body_img
                    if source_rgb is not None and body_percent < ORT_NAME_ROI_MIN_PERCENT:
                        roi_img = self._prep_stable_at_percent(source_rgb, ORT_NAME_ROI_MIN_PERCENT)
                    result = self.gfl2_speaker_tracker.process(reader, roi_img, raw_text)
                    raw_text = result.text
                    self._last_gfl2_speaker_meta = {"speaker": result.speaker, "detected": result.detected, "temporal_hold": result.temporal_hold, "thin_glyph_recovered": result.thin_glyph_recovered, "confidence": result.confidence, "raw_roi": result.raw_roi, "decision_reason": result.decision_reason, "body_prefix_stripped": result.body_prefix_stripped, "name_roi_ms": float(result.roi_ms), "thin_glyph_ms": float(result.thin_glyph_ms), "roi_quality_floor_percent": max(body_percent, ORT_NAME_ROI_MIN_PERCENT), "runtime_ocr_percent": int(self.last_runtime_ocr_percent)}
                    if result.speaker or result.thin_glyph_recovered or result.raw_roi:
                        from translation_event_logger import append_event
                        append_event("GFL2_RAW_NAME_ROI", self._last_gfl2_speaker_meta, source_module="TITANMAIN")
                        if result.speaker:
                            append_event("GFL2_SPEAKER_SELECTED", self._last_gfl2_speaker_meta, source_module="TITANMAIN")
                except Exception:
                    pass
            return raw_text
        except Exception:
            return ""
        finally:
            bridge = _get_runtime_bridge()
            if bridge:
                try:
                    self.last_ocr_ms = (time.time() - t0) * 1000.0
                    bridge.observe_ocr_ms(self.last_ocr_ms)
                except Exception:
                    pass

    def _readtext_detail(self, img_gray):
        with OCR_LOCK:
            reader = GLOBAL_READER
        if reader is None:
            return []
        t0 = time.time()
        try:
            return reader.readtext(img_gray, detail=1, paragraph=True)
        except Exception:
            return []
        finally:
            bridge = _get_runtime_bridge()
            if bridge:
                try:
                    self.last_ocr_ms = (time.time() - t0) * 1000.0
                    bridge.observe_ocr_ms(self.last_ocr_ms)
                except Exception:
                    pass

    def _prep_numeric_variants(self, img_rgb, reason: str = "", raw_text: str = ""):
        """v8.5.1 ROI digit-focused OCR variants for tactical number callouts.

        Wide-dialog numeric OCR is now ROI-first.  Full-width scans were too prone
        to catching UI/progress fragments such as 821/8261/7.18:31.20.
        """
        variants = []
        try:
            img = img_rgb
            h, w = img.shape[:2]
            rois = []
            if w >= 1500 and h >= 180 and ORT_NUMERIC_ROI_ONLY:
                # Core subtitle text band, excluding extreme edges and lower UI strip.
                y1, y2 = int(h * 0.12), int(h * 0.82)
                x1, x2 = int(w * 0.10), int(w * 0.90)
                rois.append(("center_band", img[y1:y2, x1:x2, :]))
                # Tactical callouts often put values in the middle-right text flow.
                rois.append(("mid_right", img[int(h*0.10):int(h*0.78), int(w*0.30):int(w*0.92), :]))
                # Meter/ascend phrases are often on the left-to-middle of the line.
                if "meter" in (reason or "").lower():
                    rois.append(("mid_left", img[int(h*0.10):int(h*0.78), int(w*0.08):int(w*0.72), :]))
            else:
                top = max(0, int(h * 0.04))
                bottom = max(top + 40, int(h * 0.92))
                rois.append(("full_trim", img[top:bottom, :, :]))

            scale = max(1.35, min(1.85, max(ORT_RUNTIME_OCR_SCALE, 0.50) * 1.8))
            for roi_name, roi in rois[:3]:
                if roi is None or roi.size == 0:
                    continue
                up = self._resize_for_v7(roi, scale)
                gray = cv2.cvtColor(up, cv2.COLOR_RGB2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.7, tileGridSize=(8, 8)).apply(gray)
                variants.append((f"{roi_name}:clahe", clahe))
                sharp = cv2.GaussianBlur(clahe, (0, 0), 1.0)
                sharp = cv2.addWeighted(clahe, 1.55, sharp, -0.55, 0)
                variants.append((f"{roi_name}:sharp", sharp))
                _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                variants.append((f"{roi_name}:otsu", otsu))
        except Exception:
            pass
        return variants

    def _readtext_numeric_candidates(self, img_gray):
        with OCR_LOCK:
            reader = GLOBAL_READER
        if reader is None:
            return []
        candidates = []
        allow = "0123456789.,-+°"
        try:
            det = reader.readtext(img_gray, detail=1, paragraph=False, allowlist=allow)
        except TypeError:
            try:
                det = reader.readtext(img_gray, detail=1, paragraph=False)
            except Exception:
                det = []
        except Exception:
            det = []
        for item in det or []:
            try:
                txt = str(item[1] or "")
                conf = float(item[2]) if len(item) >= 3 else 0.0
                if conf < 0.25:
                    continue
                # Drop obvious UI/progress fragments before semantic validation.
                if any(ch in txt for ch in ["/", ":", ";"]):
                    continue
                candidates.append(txt)
            except Exception:
                continue
        return candidates

    def _maybe_numeric_dual_pass(self, raw_text: str, frame_rgb):
        numeric_t0 = time.perf_counter()
        self.last_numeric_retry_ms = 0.0
        if not ORT_NUMERIC_DUAL_PASS:
            return raw_text
        try:
            from app.ocr.number_guard import needs_numeric_dual_pass, merge_numeric_candidates_into_text
            need, reason = needs_numeric_dual_pass(raw_text)
            if not need:
                return raw_text
            now = time.time()
            # Avoid hammering GPU on the same stuck partial text.
            if raw_text == self._last_numeric_dual_pass_text and (now - self._last_numeric_dual_pass_ts) * 1000.0 < ORT_NUMERIC_DUAL_PASS_MIN_MS:
                return raw_text
            self._last_numeric_dual_pass_ts = now
            self._last_numeric_dual_pass_text = raw_text
            all_candidates = []
            for tag, variant in self._prep_numeric_variants(frame_rgb, reason=reason, raw_text=raw_text):
                all_candidates.extend(self._readtext_numeric_candidates(variant))
                if len(all_candidates) >= 6:
                    break
            merged, merge_reason = merge_numeric_candidates_into_text(raw_text, all_candidates)
            if merged != raw_text:
                self.last_numeric_retry_ms = (time.perf_counter() - numeric_t0) * 1000.0
                self.debug.emit(f"[OCR] numeric dual-pass {reason} -> {merge_reason}")
                return merged
            self.last_numeric_retry_ms = (time.perf_counter() - numeric_t0) * 1000.0
            self.debug.emit(f"[OCR] numeric dual-pass known limitation | reason={reason} | no safe ROI digit")
        except Exception as exc:
            try:
                self.debug.emit(f"[OCR] numeric dual-pass skipped: {type(exc).__name__}")
            except Exception:
                pass
        return raw_text

    def _freeze_ultra(self, img_rgb):
        t0 = time.time()
        best_text = ""
        best_score = -1.0
        best_conf = 0.0

        variants = self._prep_freeze_variants(img_rgb)
        for tag, v in variants:
            det = self._readtext_detail(v)
            if not det:
                continue
            if ORT_GFL_SPEAKER_ROI:
                try:
                    from app.games.gfl_profile import extract_layout_text
                    txt, meta = extract_layout_text(det, getattr(v, "shape", (1, 1)))
                    self._last_gfl_layout_meta = dict(meta or {})
                except Exception:
                    txt = " ".join([d[1] for d in det if d and d[1]]).strip()
            else:
                txt = " ".join([d[1] for d in det if d and d[1]]).strip()
            if not txt:
                continue
            confs = [float(d[2]) for d in det if len(d) >= 3]
            avg_conf = float(sum(confs) / max(1, len(confs))) if confs else 0.0

            txt2 = normalize_ocr_text(txt)
            txt2 = _strip_ocr_digit_noise(txt2)
            score = len(txt2) + (avg_conf * 50.0)

            if score > best_score:
                best_score = score
                best_text = txt2
                best_conf = avg_conf

            if best_conf >= 0.62 and len(best_text) >= 40:
                break

        dt = int((time.time() - t0) * 1000)
        self.debug.emit(f"[FREEZE] ULTRA done | conf={best_conf:.2f} | {dt}ms")
        return best_text

    def run(self):
        global CAS_ACTIVE
        with mss.mss() as sct:
            while self.running:
                if IS_PAUSED:
                    self.msleep(30)
                    continue

                if CAS_ACTIVE:
                    self.msleep(35)
                    continue

                try:
                    t_cap0 = time.time()
                    frame = np.array(sct.grab(self.region))[:, :, :3]
                    self.last_capture_ms = (time.time() - t_cap0) * 1000.0
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_rgb = self._apply_gfl_frame_policy(frame_rgb)
                    if frame_rgb is None:
                        self.msleep(max(30, ORT_SCAN_SLEEP_GPU_MS if IS_USING_GPU else ORT_SCAN_SLEEP_CPU_MS))
                        continue

                    if CAPTURE_MODE == 1:
                        snap_kind = self._take_snapshot_kind()
                        if snap_kind is None:
                            self.msleep(ORT_SCAN_SLEEP_GPU_MS if IS_USING_GPU else max(ORT_SCAN_SLEEP_CPU_MS, 40))
                            continue

                        manual_freeze = not AUTO_SNAPSHOT_ON
                        if snap_kind != "ULTRA" and not self._should_run_ocr_for_frame(frame_rgb, manual=manual_freeze):
                            self.snapshot_done.emit(snap_kind, "")
                            self.msleep(5)
                            continue

                        if snap_kind == "ULTRA":
                            raw_text = self._freeze_ultra(frame_rgb)
                        else:
                            t_prep0 = time.time()
                            proc = self._prep_stable(frame_rgb)
                            self.last_preprocess_ms = (time.time() - t_prep0) * 1000.0
                            raw_text = self._readtext_fast(proc, frame_rgb)
                            raw_text = normalize_ocr_text(raw_text)
                            raw_text = _strip_ocr_digit_noise(raw_text)
                            raw_text = self._maybe_numeric_dual_pass(raw_text, frame_rgb)

                        pushed = self._queue_push("FREEZE", raw_text, {"snap_kind": snap_kind, "auto_snapshot": bool(AUTO_SNAPSHOT_ON), "manual_freeze": bool(not AUTO_SNAPSHOT_ON), "gfl_layout": dict(self._last_gfl_layout_meta) if ORT_GFL_LAYOUT else {}, "gfl2_speaker": dict(self._last_gfl2_speaker_meta) if ORT_GFL2_SPEAKER_ROI else {}})
                        self.snapshot_done.emit(snap_kind, raw_text if pushed else "")
                        self.msleep(5)
                        continue

                    if not self._should_run_ocr_for_frame(frame_rgb, manual=False):
                        continue
                    t_prep0 = time.time()
                    proc = self._prep_stable(frame_rgb)
                    self.last_preprocess_ms = (time.time() - t_prep0) * 1000.0
                    raw_text = self._readtext_fast(proc, frame_rgb)
                    raw_text = normalize_ocr_text(raw_text)
                    raw_text = _strip_ocr_digit_noise(raw_text)
                    raw_text = self._maybe_numeric_dual_pass(raw_text, frame_rgb)

                    if CAPTURE_MODE == 0:
                        self._queue_push("STABLE", raw_text, {"auto_snapshot": False, "manual_freeze": False, "gfl_layout": dict(self._last_gfl_layout_meta) if ORT_GFL_LAYOUT else {}, "gfl2_speaker": dict(self._last_gfl2_speaker_meta) if ORT_GFL2_SPEAKER_ROI else {}})
                    elif CAPTURE_MODE == 2:
                        if len(raw_text) > 2:
                            self.vote_buf.append(raw_text)
                            if len(self.vote_buf) >= 5:
                                most = Counter(self.vote_buf).most_common(1)[0]
                                if most[1] >= 3:
                                    self._queue_push("HIGH_LATENCY", most[0], {"auto_snapshot": False, "manual_freeze": False, "gfl_layout": dict(self._last_gfl_layout_meta) if ORT_GFL_LAYOUT else {}, "gfl2_speaker": dict(self._last_gfl2_speaker_meta) if ORT_GFL2_SPEAKER_ROI else {}})

                except Exception as e:
                    self.debug.emit(f"[OCR] ERR: {e}")

                sleep_default = ORT_SCAN_SLEEP_GPU_MS if IS_USING_GPU else ORT_SCAN_SLEEP_CPU_MS
                bridge = _get_runtime_bridge()
                if bridge:
                    try:
                        sleep_default = bridge.extra_loop_sleep_ms(int(sleep_default), bool(IS_USING_GPU))
                    except Exception:
                        pass
                try:
                    sleep_default = max(int(sleep_default), int(_apply_runtime_actions() or 0))
                except Exception:
                    pass
                self.msleep(int(sleep_default))

# ==============================================================================
# Translator Worker
# ==============================================================================
class TranslatorWorker(QThread):
    new_payload = pyqtSignal(str, str)
    debug = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.last_dialog = ""
        self.last_speaker = ""
        try:
            from app.runtime.story_dialogue_scheduler import StoryDialogueScheduler
            self.dialog_scheduler = StoryDialogueScheduler.from_env()
        except Exception:
            self.dialog_scheduler = None
        self._last_scheduler_log = 0.0
        self.turn_safe_overlay = TurnSafeOverlayController() if TurnSafeOverlayController is not None else None
        self.dialog_accumulator = DialogueTurnAccumulator.from_env() if DialogueTurnAccumulator is not None else None
        self.overlay_commit_gate = OverlayCommitGate.from_env() if OverlayCommitGate is not None else None
        self.recording_telemetry = RecordingTelemetry() if RecordingTelemetry is not None else None

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    def run(self):
        while self.running:
            try:
                item = OCR_TEXT_QUEUE.get(timeout=0.25)
                if isinstance(item, tuple) and len(item) >= 3:
                    mode_name, raw_text, ocr_meta = item[0], item[1], (item[2] if isinstance(item[2], dict) else {})
                else:
                    mode_name, raw_text = item
                    ocr_meta = {}
            except queue.Empty:
                continue

            if ORT_RESPONSIVE_STORY_MODE and ORT_LATEST_FRAME_WINS and mode_name != "FREEZE":
                dropped_latest = 0
                try:
                    while True:
                        newer = OCR_TEXT_QUEUE.get_nowait()
                        if isinstance(newer, tuple) and len(newer) >= 3:
                            mode_name, raw_text, ocr_meta = newer[0], newer[1], (newer[2] if isinstance(newer[2], dict) else {})
                        else:
                            mode_name, raw_text = newer
                            ocr_meta = {}
                        dropped_latest += 1
                except queue.Empty:
                    pass
                if dropped_latest:
                    try:
                        from translation_event_logger import append_event
                        append_event("LATEST_FRAME_WINS", {"discarded_older": dropped_latest, "capture_mode": mode_name}, source_module="TITANMAIN")
                    except Exception:
                        pass

            raw_text = (raw_text or "").strip()
            queue_wait_ms = max(0.0, (time.time() - float(ocr_meta.get("enqueued_at") or time.time())) * 1000.0)
            ocr_meta["queue_wait_ms"] = queue_wait_ms
            if self.dialog_scheduler is not None:
                try:
                    decision = self.dialog_scheduler.decide(raw_text, mode=mode_name, meta=ocr_meta)
                    if not decision.process:
                        now = time.time()
                        if now - self._last_scheduler_log > 2.5 and decision.reason not in {"voice_hold_duplicate"}:
                            self._last_scheduler_log = now
                            self.debug.emit(f"[SCHED v8.7] {decision.state}: {decision.reason}")
                        try:
                            from translation_event_logger import append_event
                            append_event("DIALOG_SCHEDULER_HOLD", {"state": decision.state, "reason": decision.reason, "mode": mode_name, "text_length": len(raw_text)}, source_module="TITANMAIN")
                        except Exception:
                            pass
                        if decision.sleep_ms > 0:
                            self.msleep(min(int(decision.sleep_ms), 120))
                        continue
                    raw_text = decision.text
                    ocr_meta["scheduler_state"] = decision.state
                    ocr_meta["scheduler_reason"] = decision.reason
                except Exception:
                    pass
            bridge = _get_runtime_bridge()
            if bridge:
                pre = bridge.preprocess_ocr_text(raw_text, meta={"mode": mode_name, "game": ORT_GAME_OVERRIDE})
                if not pre.get("process", True):
                    reason = pre.get("reason", "skip")
                    if reason not in {"duplicate", "empty"}:
                        self.debug.emit(f"[V7.1] OCR skipped: {reason} | load={pre.get('status','-')}")
                    sleep_ms = int(pre.get("sleep_ms", 0) or 0)
                    if sleep_ms > 0:
                        self.msleep(min(sleep_ms, 500))
                    continue
                raw_text = (pre.get("text") or raw_text).strip()
                sleep_ms = int(pre.get("sleep_ms", 0) or 0)
                if sleep_ms > 0:
                    self.msleep(min(sleep_ms, 500))

            raw_text = normalize_ocr_text(raw_text)
            raw_text = _strip_ocr_digit_noise(raw_text)

            if len(raw_text) < 2:
                continue

            if ORT_SCENE_EXIT_GUARD and ORT_GAME_OVERRIDE == "GFL2_EXILIUM" and is_scene_exit_text(raw_text):
                try:
                    from translation_event_logger import append_event
                    append_event("SCENE_EXIT_OVERLAY_CLEARED", {"text": raw_text[:240], "game": ORT_GAME_OVERRIDE, "reason": "raw_ui_scene_exit"}, source_module="TITANMAIN")
                except Exception:
                    pass
                self.last_dialog = ""
                self.last_speaker = ""
                self.new_payload.emit("", "")
                self.debug.emit("[PIPE] scene_exit cleared non-dialog reward/map UI")
                continue

            if ORT_GFL_LAYOUT:
                try:
                    from app.games.gfl_profile import is_non_dialog_text
                    if is_non_dialog_text(raw_text):
                        self.debug.emit(f"[GFL] non-dialog/footer text skipped: {raw_text[:70]}")
                        try:
                            from translation_event_logger import append_event
                            append_event("GFL_NON_DIALOG_TEXT_SKIPPED", {"text": raw_text[:180], "game": ORT_GAME_OVERRIDE}, source_module="TITANMAIN")
                        except Exception:
                            pass
                        continue
                except Exception:
                    pass

            if CAS_ACTIVE:
                continue

            if re.fullmatch(r"\d{1,6}", raw_text.strip()):
                continue

            self.debug.emit(f"[OCR] {raw_text[:90]}..." if len(raw_text) > 90 else f"[OCR] {raw_text}")
            try:
                from translation_event_logger import append_event
                append_event("OCR_CAPTURED", {"correlation_id": __import__("app.telemetry.correlation", fromlist=["make_correlation_id"]).make_correlation_id(raw_text, "ocr"), "mode": mode_name, "text": raw_text, "game": ORT_GAME_OVERRIDE, "latency_ms": float(ocr_meta.get("total_ms") or ocr_meta.get("ocr_ms") or 0.0), "ocr_ms": float(ocr_meta.get("ocr_ms") or 0.0), "capture_ms": float(ocr_meta.get("capture_ms") or 0.0), "preprocess_ms": float(ocr_meta.get("preprocess_ms") or 0.0), "body_ocr_ms": float(ocr_meta.get("body_ocr_ms") or 0.0), "numeric_retry_ms": float(ocr_meta.get("numeric_retry_ms") or 0.0), "readability_rescue_ms": float(ocr_meta.get("readability_rescue_ms") or 0.0), "runtime_ocr_percent": int(ocr_meta.get("runtime_ocr_percent") or ORT_RUNTIME_OCR_RESOLUTION_PERCENT), "readability_score": float(ocr_meta.get("readability_score") or 0.0), "queue_wait_ms": float(ocr_meta.get("queue_wait_ms") or 0.0), "name_roi_ms": float((ocr_meta.get("gfl2_speaker", {}) or {}).get("name_roi_ms") or 0.0), "thin_glyph_ms": float((ocr_meta.get("gfl2_speaker", {}) or {}).get("thin_glyph_ms") or 0.0), "total_ms": float(ocr_meta.get("total_ms") or 0.0), "text_length": len(raw_text)}, source_module="TITANMAIN")
            except Exception:
                pass

            try:
                from app.ocr.number_guard import should_reject_numeric_noise, number_quality_hint
                reject_num, reason_num = should_reject_numeric_noise(raw_text)
                if reject_num:
                    self.debug.emit(f"[OCR] numeric noise skipped: {reason_num}")
                    continue
                hint_num = number_quality_hint(raw_text)
                try:
                    from app.ocr.number_guard import number_gap_hint
                    gap_hint = number_gap_hint(raw_text)
                    if gap_hint != "none":
                        self.debug.emit(f"[OCR] number gap: {gap_hint}")
                except Exception:
                    pass
                if hint_num not in {"none", "number_safe"}:
                    self.debug.emit(f"[OCR] number guard: {hint_num}")
            except Exception:
                pass

            _promote_unique_terms(raw_text)
            _punct_count(raw_text)

            roi_meta = dict(ocr_meta.get("gfl2_speaker", {}) or {}) if ORT_GFL2_SPEAKER_ROI else {}
            roi_speaker = str(roi_meta.get("speaker") or "").strip()
            if roi_speaker:
                kind, speaker = "DIALOG", roi_speaker
                dialog = (raw_text or "").strip()
                try:
                    from app.identity.speaker_registry import strip_matching_speaker_prefix
                    dialog, stripped = strip_matching_speaker_prefix(dialog, speaker, "GFL2_EXILIUM")
                except Exception:
                    stripped = False
                try:
                    from translation_event_logger import append_event
                    append_event("GFL2_SPEAKER_META_COMMITTED", {"speaker": speaker, "raw_name_roi": roi_meta.get("raw_roi", ""), "confidence": roi_meta.get("confidence", 0.0), "decision_reason": roi_meta.get("decision_reason", ""), "body_prefix_stripped": bool(stripped)}, source_module="TITANMAIN")
                except Exception:
                    pass
            else:
                kind, speaker, dialog = split_speaker_and_dialog(raw_text)
            dialog = (dialog or "").strip()

            if ORT_TURN_SAFE_OVERLAY and ORT_GAME_OVERRIDE == "GFL2_EXILIUM" and self.turn_safe_overlay is not None:
                try:
                    turn_decision = self.turn_safe_overlay.evaluate(speaker, dialog, raw_text)
                    ocr_meta["dialog_turn_id"] = turn_decision.turn_id
                    if turn_decision.scene_exit:
                        from translation_event_logger import append_event
                        append_event("SCENE_EXIT_OVERLAY_CLEARED", {"text": raw_text[:240], "reason": turn_decision.reason}, source_module="TITANMAIN")
                        self.last_dialog = ""
                        self.last_speaker = ""
                        if self.dialog_accumulator is not None:
                            try:
                                self.dialog_accumulator.reset()
                            except Exception:
                                pass
                        if self.overlay_commit_gate is not None:
                            try:
                                self.overlay_commit_gate.reset(clear_visible=True)
                            except Exception:
                                pass
                        if self.recording_telemetry is not None:
                            try:
                                self.recording_telemetry.inc("scene_exit_clear")
                            except Exception:
                                pass
                        self.new_payload.emit("", "")
                        continue
                    if turn_decision.clear_overlay:
                        from translation_event_logger import append_event
                        append_event("STALE_OVERLAY_CLEARED_ON_NEW_TURN", {"dialog_turn_id": turn_decision.turn_id, "speaker": speaker or "", "source": dialog[:240]}, source_module="TITANMAIN")
                        self.last_dialog = ""
                        self.last_speaker = ""
                        if self.dialog_accumulator is not None:
                            try:
                                self.dialog_accumulator.reset()
                            except Exception:
                                pass
                        if self.overlay_commit_gate is not None:
                            try:
                                # v8.8.3: do not blank overlay on a normal new turn; keep last
                                # readable translation until the next meaningful payload is ready.
                                self.overlay_commit_gate.reset(clear_visible=False)
                            except Exception:
                                pass
                        if ORT_RESPONSIVE_STORY_MODE:
                            self.debug.emit("[COMMIT v8.8.3] defer_clear | reason=new_turn_keep_last_until_next_commit")
                except Exception:
                    pass

            if self.dialog_accumulator is not None and dialog:
                try:
                    stability = self.dialog_accumulator.update(speaker, dialog, mode=mode_name, turn_id=str(ocr_meta.get("dialog_turn_id", "")))
                    ocr_meta["dialog_stability_state"] = stability.state
                    ocr_meta["dialog_stability_reason"] = stability.reason
                    ocr_meta["dialog_best_source"] = stability.text
                    if not stability.process:
                        try:
                            from translation_event_logger import append_event
                            append_event("DIALOG_STABILITY_HOLD", {"state": stability.state, "reason": stability.reason, "speaker": speaker or "", "source": dialog[:240], "best_source": stability.text[:240], "mode": mode_name}, source_module="TITANMAIN")
                        except Exception:
                            pass
                        if ORT_RESPONSIVE_STORY_MODE:
                            self.debug.emit(f"[SMOOTH v8.8.3] keep_last | state={stability.state} | reason={stability.reason}")
                        continue
                    if stability.text and stability.text != dialog:
                        try:
                            from translation_event_logger import append_event
                            append_event("DIALOG_BEST_SOURCE_SELECTED", {"speaker": speaker or "", "source": dialog[:240], "best_source": stability.text[:300], "reason": stability.reason, "state": stability.state}, source_module="TITANMAIN")
                        except Exception:
                            pass
                        dialog = stability.text
                except Exception:
                    pass

            if not dialog and speaker:
                # v8.8.3: speaker-only OCR fragments are common during typewriter transitions.
                # In Auto/Recording they should not blank or replace the current subtitle.
                if ORT_RESPONSIVE_STORY_MODE and mode_name != "FREEZE":
                    self.debug.emit("[COMMIT v8.8.3] keep_last | reason=speaker_only_fragment")
                    if self.recording_telemetry is not None:
                        try:
                            self.recording_telemetry.inc("speaker_only_suppressed")
                        except Exception:
                            pass
                    continue
                speaker_html = f"<b style='color:#FFD700; font-size:{CURRENT_FONT_SIZE+2}px; text-shadow:1px 1px 2px #000;'>{_html_escape(speaker)}</b>"
                self.new_payload.emit(speaker_html, "")
                continue

            if not dialog:
                continue

            cache_hit = dialog in TRANSLATION_MEMORY
            try:
                from translation_event_logger import append_translation_event
                append_translation_event("TRANSLATION_REQUEST", source=dialog, speaker=speaker, extra={"mode": mode_name, "kind": kind, "game": ORT_GAME_OVERRIDE}, source_module="TITANMAIN")
            except Exception:
                pass
            t0 = time.time()
            out = offline_translate_ram(dialog)
            out = _preserve_tail_punct(dialog, out)
            dt = int((time.time() - t0) * 1000)
            try:
                from app.identity.speaker_registry import has_internal_entity_token
                if has_internal_entity_token(out):
                    from translation_event_logger import append_event
                    append_event("OVERLAY_INTERNAL_MARKER_BLOCKED", {"speaker": speaker or "", "source": dialog[:240], "unsafe_output": str(out)[:240]}, source_module="TITANMAIN")
                    out = dialog
            except Exception:
                pass
            if ORT_SPEAKER_TRANSITION_GUARD and int(ocr_meta.get("speaker_epoch") or 0) < int(LATEST_SPEAKER_EPOCH):
                try:
                    from translation_event_logger import append_event
                    append_event("OVERLAY_STALE_SPEAKER_DROPPED", {"translated_speaker": speaker or "", "current_speaker": LATEST_SPEAKER_NAME, "translated_epoch": int(ocr_meta.get("speaker_epoch") or 0), "current_epoch": int(LATEST_SPEAKER_EPOCH), "latency_ms": dt}, source_module="TITANMAIN")
                except Exception:
                    pass
                continue
            global LAST_TRANSLATE_MS
            LAST_TRANSLATE_MS = dt

            meta_now = dict(LAST_TRANSLATION_META or {})
            if meta_now.get("overlay_hold") and not meta_now.get("trusted_preview"):
                try:
                    from translation_event_logger import append_event
                    append_event("OVERLAY_HELD_UNTRUSTED_OR_INCOMPLETE", {"speaker": speaker or "", "source": dialog[:300], "reason": str(meta_now.get("hold_reason", "held")), "cache_blocked": str(meta_now.get("cache_blocked", ""))}, source_module="TITANMAIN")
                except Exception:
                    pass
                self.debug.emit(f"[PIPE] hold={meta_now.get('hold_reason','held')} | engine={meta_now.get('engine','held')} | scheduler={os.environ.get('ORT_DIALOG_SCHEDULER_PROFILE','-')} | responsive={1 if ORT_RESPONSIVE_STORY_MODE else 0}")
                if self.recording_telemetry is not None:
                    try:
                        self.recording_telemetry.inc("held_keep_last")
                    except Exception:
                        pass
                continue
            cache_label = str(meta_now.get("cache") or ("LEGACY_HIT" if cache_hit else "MISS"))
            engine_label = str(meta_now.get("engine") or "legacy_argos")
            requested_mode = os.environ.get("ORT_UI_REQUESTED_MODE", os.environ.get("ORT_BOOT_MODE", mode_name)).upper()
            scheduler_profile = os.environ.get("ORT_DIALOG_SCHEDULER_PROFILE", "-")
            self.debug.emit(f"[PIPE] cache={cache_label} | {dt}ms | engine={engine_label} | requested_mode={requested_mode} | capture_mode={mode_name} | scheduler={scheduler_profile} | responsive={1 if ORT_RESPONSIVE_STORY_MODE else 0} | queue={int(ocr_meta.get('queue_wait_ms', 0.0))}ms | entity={meta_now.get('entity_match_ms', '-')}ms | backend={meta_now.get('backend_translate_ms', '-')}ms | idn={meta_now.get('idn_post_ms', '-')}ms | kind={kind}")
            try:
                from translation_event_logger import append_translation_event
                append_translation_event("TRANSLATION_RESULT", source=dialog, translation=out, speaker=speaker, engine=engine_label, latency_ms=dt, cache=cache_label, extra={"mode": mode_name, "requested_mode": requested_mode, "scheduler": scheduler_profile, "kind": kind, "game": ORT_GAME_OVERRIDE, "speaker_source": "gfl2_roi_metadata" if roi_speaker else "text_parser", "responsive_story": bool(ORT_RESPONSIVE_STORY_MODE), "entity_match_ms": meta_now.get("entity_match_ms", 0.0), "backend_translate_ms": meta_now.get("backend_translate_ms", 0.0), "idn_post_ms": meta_now.get("idn_post_ms", 0.0), "name_roi_ms": roi_meta.get("name_roi_ms", 0.0), "ocr_body_ms": ocr_meta.get("body_ocr_ms", 0.0), "ocr_numeric_retry_ms": ocr_meta.get("numeric_retry_ms", 0.0), "ocr_readability_rescue_ms": ocr_meta.get("readability_rescue_ms", 0.0), "runtime_ocr_percent": ocr_meta.get("runtime_ocr_percent", ORT_RUNTIME_OCR_RESOLUTION_PERCENT), "readability_score": ocr_meta.get("readability_score", 0.0), "ocr_thin_glyph_ms": roi_meta.get("thin_glyph_ms", 0.0), "queue_wait_ms": ocr_meta.get("queue_wait_ms", 0.0), "dialog_stability_state": ocr_meta.get("dialog_stability_state", ""), "dialog_stability_reason": ocr_meta.get("dialog_stability_reason", "")}, source_module="TITANMAIN")
                overlay_event = "TRUSTED_PREVIEW_OVERLAY" if meta_now.get("trusted_preview") else "FINAL_OVERLAY"
                append_event(overlay_event, {"speaker": speaker or "", "body": dialog, "translation": out, "speaker_source": "gfl2_roi_metadata" if roi_speaker else "text_parser", "game": ORT_GAME_OVERRIDE, "faithfulness_allowed": bool(meta_now.get("faithfulness_allowed", True)), "faithfulness_reason": meta_now.get("faithfulness_reason", "safe"), "semantic_flags": meta_now.get("semantic_flags", []), "semantic_fidelity_reason": meta_now.get("semantic_fidelity_reason", "safe"), "coverage_score": meta_now.get("coverage_score", 1.0), "fallback_backend_reason": meta_now.get("fallback_backend_reason", ""), "cache_allowed_after_gate": not bool(meta_now.get("cache_blocked")), "trusted_preview": bool(meta_now.get("trusted_preview")), "dialog_turn_id": ocr_meta.get("dialog_turn_id", "")}, source_module="TITANMAIN")
            except Exception:
                pass
            if not meta_now.get("cache_blocked"):
                training_log_record(mode_name, dialog, out, meta={"speaker": speaker, "kind": kind, "engine": engine_label, "cache": cache_label})
                bridge = _get_runtime_bridge()
                if bridge:
                    try:
                        bridge.observe_dialog(speaker, dialog, out)
                    except Exception:
                        pass
            else:
                try:
                    from translation_event_logger import append_event
                    append_event("TRAINING_SAMPLE_BLOCKED_BY_SAFETY_GATE", {"speaker": speaker or "", "source": dialog[:300], "reason": str(meta_now.get("cache_blocked", ""))}, source_module="TITANMAIN")
                except Exception:
                    pass

            out = _soft_wrap_long_tokens(out, max_run=18)
            safe_out = _html_escape(out)

            try:
                from app.identity.speaker_registry import speaker_exact_names
                npc_names = speaker_exact_names(ORT_GAME_OVERRIDE)
            except Exception:
                npc_names = NPC_DATABASE.get("known", [])
            exclude = {speaker} if speaker else set()
            safe_out = _highlight_terms(safe_out, npc_names, "#FF5555", exclude=exclude)
            safe_out = _highlight_terms(safe_out, UNIQUE_TERMS.get("known", []), "#55AAFF")

            if kind == "MONOLOG":
                speaker_html = ""
                dialog_html = f"<i style='color:#FFFFFF; font-size:{CURRENT_FONT_SIZE}px; text-shadow:1px 1px 2px #000;'>{safe_out}</i>"
            else:
                if speaker:
                    sp_main = _html_escape(_soft_wrap_long_tokens(speaker, max_run=18))
                    speaker_html = f"<b style='color:#FFD700; font-size:{CURRENT_FONT_SIZE+2}px; text-shadow:1px 1px 2px #000;'>{sp_main}</b>"
                else:
                    speaker_html = ""
                dialog_html = f"<span style='color:#FFFFFF; font-size:{CURRENT_FONT_SIZE}px; text-shadow:1px 1px 2px #000;'>{safe_out}</span>"

            # v8.8.3: final visual commit gate. OCR/translation may run quickly, but
            # the overlay is only replaced when the new payload is visually meaningful.
            if self.overlay_commit_gate is not None:
                try:
                    final_payload = not bool(meta_now.get("trusted_preview")) and not bool(meta_now.get("cache_blocked"))
                    gate_decision = self.overlay_commit_gate.decide(
                        speaker_html=speaker_html,
                        dialog_html=dialog_html,
                        plain_translation=out,
                        source_text=dialog,
                        speaker=speaker or "",
                        turn_id=str(ocr_meta.get("dialog_turn_id", "")),
                        mode=mode_name,
                        engine=engine_label,
                        cache=cache_label,
                        trusted_preview=bool(meta_now.get("trusted_preview")),
                        final=bool(final_payload),
                        held=False,
                    )
                    if not gate_decision.commit:
                        if self.recording_telemetry is not None:
                            try:
                                self.recording_telemetry.inc("overlay_suppressed")
                                self.recording_telemetry.inc("overlay_suppressed_" + gate_decision.state.lower())
                                self.recording_telemetry.maybe_log(lambda msg: self.debug.emit(msg))
                            except Exception:
                                pass
                        try:
                            from translation_event_logger import append_event
                            append_event("OVERLAY_COMMIT_SUPPRESSED", {"state": gate_decision.state, "reason": gate_decision.reason, "speaker": speaker or "", "source": dialog[:240], "translation": out[:240], "engine": engine_label, "cache": cache_label, "turn_id": str(ocr_meta.get("dialog_turn_id", ""))}, source_module="TITANMAIN")
                        except Exception:
                            pass
                        self.debug.emit(f"[COMMIT v8.8.3] suppress | state={gate_decision.state} | reason={gate_decision.reason}")
                        continue
                    self.overlay_commit_gate.mark_committed(
                        speaker_html=speaker_html,
                        dialog_html=dialog_html,
                        plain_translation=out,
                        source_text=dialog,
                        turn_id=str(ocr_meta.get("dialog_turn_id", "")),
                        signature=gate_decision.signature,
                    )
                    if self.recording_telemetry is not None:
                        try:
                            self.recording_telemetry.inc("overlay_committed")
                            self.recording_telemetry.inc("overlay_committed_" + gate_decision.state.lower())
                            self.recording_telemetry.maybe_log(lambda msg: self.debug.emit(msg))
                        except Exception:
                            pass
                except Exception as exc:
                    self.debug.emit(f"[COMMIT v8.8.3] gate_error_fallback_commit | {type(exc).__name__}: {exc}")
            else:
                if dialog_html == self.last_dialog and speaker_html == self.last_speaker:
                    continue

            if dialog_html == self.last_dialog and speaker_html == self.last_speaker:
                continue
            self.last_dialog = dialog_html
            self.last_speaker = speaker_html

            self.new_payload.emit(speaker_html, dialog_html)

# ==============================================================================
# CAS utilities (FAST)  [only CAS changed]
# ==============================================================================
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _bbox_to_rect(bbox):
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    x1, x2 = int(min(xs)), int(max(xs))
    y1, y2 = int(min(ys)), int(max(ys))
    return x1, y1, x2 - x1, y2 - y1

def _clean_cas_fast_text(s: str) -> str:
    if not s:
        return ""
    s = normalize_ocr_text(s)
    s = _strip_ocr_digit_noise(s)
    s = s.replace("\uFFFD", "").replace("\u200b", "")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _is_fast_text_ok(t: str) -> bool:
    t = (t or "").strip()
    if len(t) < 2:
        return False
    if re.fullmatch(r"\d{1,6}", t):
        return False
    # reject super-symbol heavy tokens (fast)
    bad = sum(ch in "@#$%^*_=<>~`" for ch in t)
    if len(t) >= 6 and bad >= 2:
        return False
    return True

def _detect_scale_for_width_fast(w: int) -> float:
    if w <= 0:
        return 1.0
    target = float(CAS_FAST_DETECT_W)
    if w <= target:
        return 1.0
    s = target / float(w)
    return _clamp(s, 0.40, 1.0)

def _group_boxes_into_lines_fast(items):
    """
    FAST grouping:
    - cluster by Y center proximity (looser)
    - join within line by x order (simple)
    """
    if not items:
        return []

    items = sorted(items, key=lambda d: (d["cy"], d["x"]))
    lines = []
    for it in items:
        placed = False
        for ln in lines:
            # y proximity threshold based on avg height
            h = max(10.0, ln["havg"])
            if abs(it["cy"] - ln["cy"]) <= h * 0.65:
                ln["items"].append(it)
                ln["cy"] = (ln["cy"] * 0.75) + (it["cy"] * 0.25)
                ln["havg"] = (ln["havg"] * 0.75) + (float(it["h"]) * 0.25)
                placed = True
                break
        if not placed:
            lines.append({"items": [it], "cy": float(it["cy"]), "havg": float(it["h"])})

    merged = []
    for ln in lines:
        seg = sorted(ln["items"], key=lambda d: d["x"])
        text = " ".join([x["text"] for x in seg if x.get("text")]).strip()
        text = _clean_cas_fast_text(text)
        if not _is_fast_text_ok(text):
            continue

        x1 = min(x["x"] for x in seg)
        y1 = min(x["y"] for x in seg)
        x2 = max(x["x"] + x["w"] for x in seg)
        y2 = max(x["y"] + x["h"] for x in seg)
        conf = sum(float(x.get("conf", 0.0)) for x in seg) / max(1, len(seg))
        merged.append({"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "conf": conf, "text": text})

    merged = [m for m in merged if m["h"] >= CAS_FAST_MIN_H and m["w"] >= CAS_FAST_MIN_W]
    merged.sort(key=lambda d: (d["y"], d["x"]))
    return merged

def _dedupe_lines_fast(lines):
    if not lines or not CAS_FAST_DEDUPE:
        return lines or []
    kept = []
    seen = set()
    for ln in lines:
        key = ln.get("text", "").strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(ln)
    return kept

# ==============================================================================
# CAS Worker (FAST, less accurate)
# ==============================================================================
class CASWorker(QThread):
    preview = pyqtSignal(object)   # {"job_id", "rgb", "geom"}
    done = pyqtSignal(object)      # {"job_id", "rgb", "boxes", "geom"}
    progress = pyqtSignal(int)     # 0..100
    debug = pyqtSignal(str)

    def __init__(self, screen_geom: QRect, job_id: int):
        super().__init__()
        self.screen_geom = screen_geom
        self.job_id = int(job_id)
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _reader(self):
        with OCR_LOCK:
            return GLOBAL_READER

    def _emit_prog(self, pct: int, msg: str = None):
        try:
            pct = int(_clamp(int(pct), 0, 100))
        except Exception:
            pct = 0
        try:
            self.progress.emit(pct)
        except Exception:
            pass
        if msg:
            self.debug.emit(msg)

    def _readtext_safe(self, reader, img_gray, *, detail, paragraph, batch_size, decoder,
                       canvas_size=None, mag_ratio=None,
                       text_threshold=None, low_text=None, link_threshold=None, min_size=None):
        """
        Compatibility wrapper: beberapa versi EasyOCR tidak punya semua argumen.
        (FAST version: only common args used; thresholds optional)
        """
        kwargs = dict(detail=detail, paragraph=paragraph, batch_size=batch_size, decoder=decoder)
        if canvas_size is not None: kwargs["canvas_size"] = canvas_size
        if mag_ratio is not None: kwargs["mag_ratio"] = mag_ratio
        if text_threshold is not None: kwargs["text_threshold"] = text_threshold
        if low_text is not None: kwargs["low_text"] = low_text
        if link_threshold is not None: kwargs["link_threshold"] = link_threshold
        if min_size is not None: kwargs["min_size"] = min_size

        try:
            return reader.readtext(img_gray, **kwargs)
        except TypeError:
            for k in ["text_threshold","low_text","link_threshold","min_size"]:
                kwargs.pop(k, None)
            try:
                return reader.readtext(img_gray, **kwargs)
            except Exception:
                return [] if detail else ""
        except Exception:
            return [] if detail else ""

    def run(self):
        global CAS_IN_PROGRESS
        CAS_IN_PROGRESS = True
        t0 = time.time()

        try:
            self._emit_prog(2, "[CAS] FAST start...")

            mon = {
                "left": int(self.screen_geom.left()),
                "top": int(self.screen_geom.top()),
                "width": int(self.screen_geom.width()),
                "height": int(self.screen_geom.height()),
            }

            # Capture
            self._emit_prog(6, "[CAS] Capturing screen...")
            with mss.mss() as sct:
                frame = np.array(sct.grab(mon))[:, :, :3]  # BGR
            rgb0 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            geom = (mon["left"], mon["top"], mon["width"], mon["height"])
            self.preview.emit({"job_id": self.job_id, "rgb": rgb0, "geom": geom})

            if self._cancel.is_set() or (not CAS_ACTIVE):
                return

            reader = self._reader()
            if reader is None:
                self.debug.emit("[CAS] Reader not ready")
                self.done.emit({"job_id": self.job_id, "rgb": rgb0, "boxes": [], "geom": geom})
                return

            # Downscale for speed
            self._emit_prog(18, "[CAS] Downscale + OCR detect...")
            H0, W0 = rgb0.shape[:2]
            s_det = _detect_scale_for_width_fast(W0)

            if s_det < 0.999:
                small = cv2.resize(rgb0, None, fx=s_det, fy=s_det, interpolation=cv2.INTER_AREA)
            else:
                small = rgb0

            gray_small = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)

            batch = max(1, (CAS_FAST_BATCH_GPU if IS_USING_GPU else CAS_FAST_BATCH_CPU))
            canvas = int(min(CAS_FAST_CANVAS, max(gray_small.shape[:2])))

            # 1-pass detect only (FAST)
            det = self._readtext_safe(
                reader, gray_small,
                detail=1, paragraph=False,
                batch_size=batch,
                decoder="greedy",
                canvas_size=canvas,
                mag_ratio=1.0,
                text_threshold=0.62,
                low_text=0.35,
                link_threshold=0.35,
                min_size=CAS_FAST_MIN_H,
            )

            if self._cancel.is_set() or (not CAS_ACTIVE):
                return

            self._emit_prog(45, "[CAS] Building lines...")

            items = []
            left, top = self.screen_geom.left(), self.screen_geom.top()

            for d in det or []:
                try:
                    bbox, txt, conf = d[0], (d[1] or "").strip(), float(d[2])
                except Exception:
                    continue

                if conf < CAS_FAST_DET_MIN_CONF:
                    continue

                txt = _clean_cas_fast_text(txt)
                if not _is_fast_text_ok(txt):
                    continue

                x, y, w, h = _bbox_to_rect(bbox)
                if s_det != 1.0:
                    x = int(x / s_det); y = int(y / s_det)
                    w = int(w / s_det); h = int(h / s_det)

                if h < CAS_FAST_MIN_H or w < 22:
                    continue

                gx = x + left
                gy = y + top

                items.append({
                    "x": int(gx), "y": int(gy), "w": int(w), "h": int(h),
                    "cx": gx + w * 0.5, "cy": gy + h * 0.5,
                    "conf": conf, "text": txt
                })

            # Merge quickly into lines (FAST)
            lines = _group_boxes_into_lines_fast(items)
            lines = _dedupe_lines_fast(lines)

            if not lines:
                dt = int((time.time() - t0) * 1000)
                self._emit_prog(100, f"[CAS] done | lines=0 | {dt}ms")
                self.done.emit({"job_id": self.job_id, "rgb": rgb0, "boxes": [], "geom": geom})
                return

            # Keep top lines (speed)
            if CAS_FAST_MAX_LINES > 0 and len(lines) > CAS_FAST_MAX_LINES:
                # score: bigger area + conf + len
                def _score(ln):
                    return (ln["w"] * ln["h"]) * 0.001 + (ln.get("conf", 0.0) * 2.0) + min(40, len(ln.get("text",""))) * 0.05
                lines = sorted(lines, key=_score, reverse=True)[:CAS_FAST_MAX_LINES]
                lines = sorted(lines, key=lambda d: (d["y"], d["x"]))

            if self._cancel.is_set() or (not CAS_ACTIVE):
                return

            self._emit_prog(72, "[CAS] Translating...")

            out_boxes = []
            for ln in lines:
                src = (ln.get("text") or "").strip()
                if not _is_fast_text_ok(src):
                    continue
                if float(ln.get("conf", 0.0)) < CAS_FAST_MIN_CONF and len(src) < 6:
                    continue

                trans = offline_translate_ram(src)
                trans = _preserve_tail_punct(src, trans).strip()

                out_boxes.append({
                    "x": int(ln["x"]), "y": int(ln["y"]),
                    "w": int(ln["w"]), "h": int(ln["h"]),
                    "src": src, "trans": trans
                })

            dt = int((time.time() - t0) * 1000)
            self._emit_prog(100, f"[CAS] done | lines={len(out_boxes)} | {dt}ms")
            self.done.emit({"job_id": self.job_id, "rgb": rgb0, "boxes": out_boxes, "geom": geom})

        except Exception as e:
            self.debug.emit(f"[CAS] ERR: {e}")
            try:
                self.done.emit({"job_id": self.job_id, "rgb": None, "boxes": [], "geom": None})
            except Exception:
                pass
        finally:
            CAS_IN_PROGRESS = False

# ==============================================================================
# CAS Overlay Host (with progress label)
# ==============================================================================
class CASOverlayHost(QWidget):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.pix = None

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        g = self.screen.geometry()
        self.setGeometry(g)

        try:
            if self.windowHandle():
                self.windowHandle().setScreen(self.screen)
        except Exception:
            pass

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, g.width(), g.height())
        self.label.setScaledContents(True)

        # progress label (top-left)
        self.prog = QLabel("CAS 0%", self)
        self.prog.setGeometry(12, 10, 120, 26)
        self.prog.setAlignment(Qt.AlignCenter)
        self.prog.setStyleSheet(
            "background-color: rgba(0,0,0,160);"
            "border:1px solid rgba(255,255,255,160);"
            "border-radius:8px;"
            "color: #00FF66;"
            "font-weight: 900;"
            "font-family: 'Segoe UI';"
            "font-size: 12px;"
        )
        self.prog.hide()

    def clear(self):
        self.pix = None
        self.label.clear()
        self.prog.hide()

    def set_progress(self, pct: int):
        try:
            pct = int(_clamp(int(pct), 0, 100))
        except Exception:
            pct = 0
        self.prog.setText(f"CAS {pct}%")
        if not self.prog.isVisible():
            self.prog.show()
        self.prog.raise_()

    def set_qimage(self, qimg: QImage):
        if qimg is None:
            return
        self.pix = QPixmap.fromImage(qimg)
        self.label.setPixmap(self.pix)
        self.show()
        self.raise_()
        self.prog.raise_()

# ==============================================================================
# CAS Rendering (same as V2 - keep readable overlay)
# ==============================================================================
def _qimage_from_rgb(rgb: np.ndarray) -> QImage:
    if rgb is None:
        return None
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()

def _render_cas_qimage(rgb: np.ndarray, boxes: list, geom_tuple):
    if rgb is None or geom_tuple is None:
        return None

    left, top, w, h = geom_tuple
    img = rgb.copy()
    H, W = img.shape[:2]

    # Stronger wipe ROI: blur + mean blend
    for b in boxes:
        x = int(b["x"] - left)
        y = int(b["y"] - top)
        bw = int(b["w"])
        bh = int(b["h"])

        pad = int(max(3, min(16, bh * 0.28)))
        x1 = _clamp(x - pad, 0, W - 1)
        y1 = _clamp(y - pad, 0, H - 1)
        x2 = _clamp(x + bw + pad, 0, W)
        y2 = _clamp(y + bh + pad, 0, H)

        if x2 <= x1 or y2 <= y1:
            continue

        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            continue

        blur_roi = cv2.GaussianBlur(roi, (0, 0), sigmaX=7, sigmaY=7)
        mean = blur_roi.mean(axis=(0, 1), keepdims=True)

        roi2 = blur_roi.astype(np.float32) * 0.33 + mean.astype(np.float32) * 0.67
        roi2 = roi2 * 0.86 + 255.0 * 0.14
        img[y1:y2, x1:x2] = np.clip(roi2, 0, 255).astype(np.uint8)

    qimg = _qimage_from_rgb(img)
    if qimg is None:
        return None

    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    for b in boxes:
        text = (b.get("trans") or "").strip()
        if not text:
            continue

        x = int(b["x"] - left)
        y = int(b["y"] - top)
        bw = int(b["w"])
        bh = int(b["h"])

        rx = _clamp(x, 0, W - 2)
        ry = _clamp(y, 0, H - 2)
        rw = _clamp(bw, 40, W - rx)
        rh = _clamp(bh, 18, H - ry)

        pad_x = int(max(5, min(14, rw * 0.028)))
        pad_y = int(max(2, min(9,  rh * 0.11)))
        rect = QRect(rx + pad_x, ry + pad_y, max(10, rw - 2 * pad_x), max(10, rh - 2 * pad_y))

        max_fs = int(max(10, min(36, rh * 0.72)))
        fs = max_fs

        def _make_font(size):
            f = QFont("Segoe UI", int(size))
            if size <= 14:
                f.setWeight(QFont.DemiBold)
            else:
                f.setWeight(QFont.Bold)
            try:
                f.setHintingPreference(QFont.PreferFullHinting)
            except Exception:
                pass
            return f

        font = _make_font(fs)
        flags = Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter

        for _ in range(26):
            metrics = QFontMetrics(font)
            br = metrics.boundingRect(QRect(0, 0, rect.width(), 5000), flags, text)
            if br.height() <= rect.height() and br.width() <= rect.width() + 6:
                break
            fs -= 1
            if fs < 9:
                fs = 9
                font = _make_font(fs)
                break
            font = _make_font(fs)

        painter.setFont(font)

        painter.setPen(QColor(0, 0, 0, 235))
        painter.drawText(rect.translated(1, 1), flags, text)
        painter.drawText(rect.translated(-1, 1), flags, text)
        painter.drawText(rect.translated(1, -1), flags, text)
        painter.drawText(rect.translated(-1, -1), flags, text)

        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(rect, flags, text)

    painter.end()
    return qimg

# ==============================================================================
# Controller (UNCHANGED behavior; CAS uses FAST worker)
# ==============================================================================
def _launch_external_titancore_v2():
    base = BASE_DIR
    candidates = [
        os.path.join(base, "TitanCore_V2.py"),
        os.path.join(base, "TitanCore_V2.exe"),
        os.path.join(base, "TitanCore_V2"),
    ]

    target = None
    for c in candidates:
        if os.path.exists(c):
            target = c
            break

    if not target:
        log("[SHIFT+F9] TitanCore_V2 not found (expected TitanCore_V2.py/.exe in same folder)")
        return

    try:
        if target.lower().endswith(".py"):
            cmd = [sys.executable, target, "--menu"]
        else:
            cmd = [target, "--menu"]

        creationflags = 0
        try:
            creationflags = subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS
        except Exception:
            creationflags = 0

        subprocess.Popen(
            cmd,
            cwd=base,
            stdout=None,
            stderr=None,
            stdin=None,
            creationflags=creationflags,
            close_fds=True,
            shell=False,
        )
        log(f"[SHIFT+F9] Launched: {os.path.basename(target)}")
    except Exception as e:
        log(f"[SHIFT+F9] Launch failed: {e}")


class Controller(QObject):
    def __init__(self):
        super().__init__()
        self.host = None
        self.snipper = None
        self.ocr_worker = None
        self.tr_worker = None
        self.region = None
        self.screen = None

        self.cas_host = None
        self.cas_worker = None
        self._cas_prev_mode = 0
        self._cas_prev_auto = False
        self._cas_job_counter = 0
        self._cas_active_job = 0

        self.vram_timer = QTimer()
        self.vram_timer.timeout.connect(_vram_monitor_tick)

        self.auto_timer = QTimer()
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._auto_tick)

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self._poll_stop_request)

        def post(fn):
            QTimer.singleShot(0, fn)

        keyboard.add_hotkey("F1", lambda: post(self.toggle_pause))
        keyboard.add_hotkey("F2", lambda: post(self.reset_area))
        keyboard.add_hotkey("F3", lambda: post(self.switch_capture_mode))
        keyboard.add_hotkey("F4", lambda: post(self.switch_visual))
        keyboard.add_hotkey("F5", lambda: post(self.switch_position))
        keyboard.add_hotkey("F6", lambda: post(self.font_down))
        keyboard.add_hotkey("F7", lambda: post(self.font_up))
        keyboard.add_hotkey("F8", lambda: post(self.cycle_width))
        keyboard.add_hotkey("F9", lambda: post(self.switch_engine_mode))
        keyboard.add_hotkey("F10", lambda: post(self.snapshot_ultra))
        keyboard.add_hotkey("F11", lambda: post(self.toggle_auto_snapshot_anywhere))  # Interval / Auto Snapshot
        keyboard.add_hotkey("ctrl+f11", lambda: post(self.capture_all_screen))  # Capture All Screen (CAS)
        keyboard.add_hotkey("esc", lambda: post(self.exit_app))

        # CAS toggle keys (keep) + add Shift+F9 (requested)
        keyboard.add_hotkey("`", lambda: post(self.capture_all_screen))
        keyboard.add_hotkey("shift+f1", lambda: post(self.capture_all_screen))
        keyboard.add_hotkey("shift+f9", lambda: post(self.launch_titancore_v2))

        boot_system()

        QTimer.singleShot(80, self.start_snipping)
        self.vram_timer.start(VRAM_CHECK_INTERVAL_MS)
        self.stop_timer.start(500)

    def _poll_stop_request(self):
        req = _runtime_stop_requested()
        if req:
            log(f"[V8.1] Stop request detected: {req.get('reason', 'unknown') if isinstance(req, dict) else req}")
            self.exit_app(reason="webui_stop_request")

    def launch_titancore_v2(self):
        """SHIFT+F9: open TitanCore_V2 menu/launcher in a new console."""
        if CAS_ACTIVE:
            try:
                self._exit_cas_restore()
            except Exception:
                pass
        log("[SHIFT+F9] Running TitanCore_V2...")
        _launch_external_titancore_v2()

    # ---------------- CAS helpers ----------------
    def _enter_cas_if_needed(self):
        global CAS_ACTIVE, AUTO_SNAPSHOT_ON, CAS_PROGRESS
        if CAS_ACTIVE:
            return

        CAS_ACTIVE = True
        CAS_PROGRESS = 0
        self._cas_prev_mode = CAPTURE_MODE
        self._cas_prev_auto = AUTO_SNAPSHOT_ON

        if AUTO_SNAPSHOT_ON:
            AUTO_SNAPSHOT_ON = False
            self.auto_timer.stop()

        try:
            while True:
                OCR_TEXT_QUEUE.get_nowait()
        except Exception:
            pass

        if self.host:
            self.host.hide_translation()

        if self.cas_host is None:
            sc = self.screen or QGuiApplication.primaryScreen()
            self.cas_host = CASOverlayHost(sc)
        self.cas_host.show()
        self.cas_host.raise_()
        self.cas_host.set_progress(0)

    def _exit_cas_restore(self):
        global CAS_ACTIVE, CAS_PROGRESS
        if not CAS_ACTIVE:
            return

        try:
            if self.cas_worker and self.cas_worker.isRunning():
                self.cas_worker.cancel()
        except Exception:
            pass

        CAS_ACTIVE = False
        CAS_PROGRESS = 0

        try:
            if self.cas_host:
                self.cas_host.clear()
                self.cas_host.hide()
        except Exception:
            pass

        global CAPTURE_MODE, AUTO_SNAPSHOT_ON
        CAPTURE_MODE = self._cas_prev_mode
        AUTO_SNAPSHOT_ON = self._cas_prev_auto

        if self.host:
            self.host.show_translation()
            self.host.update_mode_dot()
            self.host.refresh_status()

        if AUTO_SNAPSHOT_ON and CAPTURE_MODE == 1:
            self._kick_auto_cycle()

    def _pre_action_leave_cas(self):
        if CAS_ACTIVE:
            self._exit_cas_restore()

    # ---------------- App lifecycle ----------------
    def exit_app(self, reason="exit"):
        log(f"[EXIT] Closing... reason={reason}")
        try:
            if hasattr(self, "stop_timer"):
                self.stop_timer.stop()
        except Exception:
            pass
        try:
            if self.ocr_worker:
                self.ocr_worker.stop()
        except Exception:
            pass
        try:
            if self.tr_worker:
                self.tr_worker.stop()
        except Exception:
            pass
        try:
            _finalize_runtime_shutdown(reason)
        except Exception:
            pass
        try:
            if self.host:
                self.host.close()
        except Exception:
            pass
        try:
            if self.cas_host:
                self.cas_host.close()
        except Exception:
            pass
        QApplication.quit()

    def toggle_pause(self):
        global IS_PAUSED
        IS_PAUSED = not IS_PAUSED
        if IS_PAUSED:
            log("[PAUSE] UI hidden + workers paused")
            if self.host:
                self.host.hide_translation()
            if self.cas_host:
                self.cas_host.hide()
            try:
                while True:
                    OCR_TEXT_QUEUE.get_nowait()
            except Exception:
                pass
            save_cache("pause_toggle")
        else:
            log("[RESUME] UI shown + workers active")
            if CAS_ACTIVE and self.cas_host:
                self.cas_host.show()
            elif self.host:
                self.host.show_translation()

    def reset_area(self):
        self._pre_action_leave_cas()
        log("[RESET] Re-scan area + save cache")
        save_cache("reset_area")

        global AUTO_SNAPSHOT_ON
        AUTO_SNAPSHOT_ON = False
        self.auto_timer.stop()

        try:
            if self.ocr_worker:
                self.ocr_worker.stop()
        except Exception:
            pass
        try:
            if self.tr_worker:
                self.tr_worker.stop()
        except Exception:
            pass

        if self.host:
            try:
                self.host.close()
            except Exception:
                pass
            self.host = None

        if self.snipper:
            try:
                self.snipper.close()
            except Exception:
                pass
            self.snipper = None

        try:
            while True:
                OCR_TEXT_QUEUE.get_nowait()
        except Exception:
            pass

        QTimer.singleShot(60, self.start_snipping)

    def start_snipping(self):
        log("[UI] Select capture region... (snipping should appear now)")
        self.snipper = SnippingWidget()
        self.snipper.selection_made.connect(self.on_area_selected)
        self.snipper.show()

    def on_area_selected(self, region):
        self.region = region
        self.screen = pick_screen_for_region(region)
        log(f"[UI] Locked region: {region}")
        try:
            from status_manager import write_status
            rw = int(region.get("width", 0) or 0)
            rh = int(region.get("height", 0) or 0)
            quality = "OK"
            warnings = []
            if ORT_GFL_LAYOUT:
                quality = "GFL_MASK_ACTIVE"
                if rw >= 1250 or rh >= 270:
                    warnings.append("Profil GFL aktif pada area dialog lebar/tinggi; footer kanan bawah tetap dimask, tetapi gunakan crop sekecil kotak dialog untuk hasil terbaik.")
                warnings.append("GFsystem/footer mask aktif; area kanan bawah akan diabaikan tanpa memotong seluruh baris dialog.")
            elif ORT_GFL2_SPEAKER_ROI:
                quality = "GFL2_SPEAKER_ROI_ACTIVE"
                warnings.append("GFL2 Name ROI aktif: DP-12/KSVK dipindai terpisah dengan temporal label hold; body OCR tetap paragraph untuk performa.")
            elif rw >= 1800 or rh >= 260:
                if ORT_LITE_WIDE_DIALOG_FILTER and ORT_GAME_OVERRIDE == "GFL2_EXILIUM":
                    quality = "OK_WIDE_DIALOG"
                    warnings.append("Region dialog GFL2 lebar diterima; v8.4.5 mengaktifkan wide-dialog filter/noise reject agar dialog panjang tetap aman.")
                else:
                    quality = "WARNING"
                    warnings.append("Region OCR besar; jika muncul noise/angka UI, aktifkan wide-dialog filter atau crop sedikit lebih ketat ke area teks.")
            if rh < 80:
                quality = "WARNING"
                warnings.append("Region OCR terlalu pendek; pastikan semua baris dialog masuk.")
            write_status("ocr_region", {
                "version": "v8.7",
                "region": dict(region),
                "width": rw,
                "height": rh,
                "quality": quality,
                "warnings": warnings,
                "recommendation": "Untuk GFL pilih kotak dialog saja; v8.7 mem-mask footer GFsystem/ikon kanan bawah dan memakai Name/Body ROI. Untuk GFL2, dialog lebar tetap boleh dipakai dengan filter yang tersedia.",
                "game_profile": ORT_GAME_OVERRIDE,
                "gfl_layout": bool(ORT_GFL_LAYOUT),
                "footer_mask": bool(ORT_GFL_FOOTER_MASK),
            }, BASE_DIR)
        except Exception:
            pass

        self.host = OverlayHost(self.screen, region)
        self.host.show_translation()
        self.host.update_mode_dot()
        self.host.refresh_status()

        self.ocr_worker = OCRWorker(region)
        self.ocr_worker.debug.connect(lambda m: log(m))
        self.ocr_worker.snapshot_done.connect(self._on_snapshot_done)
        self.ocr_worker.start()

        self.tr_worker = TranslatorWorker()
        self.tr_worker.debug.connect(lambda m: log(m))
        self.tr_worker.new_payload.connect(self.host.update_text)
        self.tr_worker.start()

        # Important: arm the capture loop immediately after snipping so the user
        # does not need to toggle mode/engine first to start translation.
        if CAPTURE_MODE == 1 and AUTO_SNAPSHOT_ON:
            QTimer.singleShot(120, self._kick_auto_cycle)
        elif CAPTURE_MODE == 0 and self.ocr_worker:
            QTimer.singleShot(120, lambda: self.ocr_worker.request_snapshot("FAST"))

    # ---------------- Mode switching ----------------
    def switch_capture_mode(self):
        if CAS_ACTIVE:
            log("[CAS] Exit via F3 -> restore previous mode")
            self._exit_cas_restore()
            return

        global CAPTURE_MODE, AUTO_SNAPSHOT_ON

        if CAPTURE_MODE == 0:
            CAPTURE_MODE = 1
            AUTO_SNAPSHOT_ON = False
            mode_name = "FREEZE"
        elif CAPTURE_MODE == 1 and not AUTO_SNAPSHOT_ON:
            CAPTURE_MODE = 2
            AUTO_SNAPSHOT_ON = False
            mode_name = "HIGH_LATENCY"
        elif CAPTURE_MODE == 2:
            CAPTURE_MODE = 1
            AUTO_SNAPSHOT_ON = True
            mode_name = "INTERVAL"
        else:
            CAPTURE_MODE = 0
            AUTO_SNAPSHOT_ON = False
            mode_name = "STABLE"

        log(f"[MODE] CAPTURE_MODE -> {mode_name}")
        save_cache("mode_switch")

        if CAPTURE_MODE != 1 and AUTO_SNAPSHOT_ON:
            AUTO_SNAPSHOT_ON = False
            self.auto_timer.stop()
            log("[MODE] Auto Snapshot OFF (keluar dari FREEZE)")

        if CAPTURE_MODE == 1 and AUTO_SNAPSHOT_ON:
            self.auto_timer.stop()
            self.auto_timer.start(AUTO_SNAPSHOT_INTERVAL_MS)
            log(f"[MODE] INTERVAL -> ON | {AUTO_SNAPSHOT_INTERVAL_MS}ms")

        if self.host:
            self.host.update_mode_dot()
            self.host.refresh_status()

        if CAPTURE_MODE == 1 and not AUTO_SNAPSHOT_ON:
            log("[MODE] FREEZE -> siap (F10 ULTRA / F11 AUTO FAST)")

    def switch_visual(self):
        self._pre_action_leave_cas()
        global CURRENT_VISUAL_ID
        CURRENT_VISUAL_ID = (CURRENT_VISUAL_ID + 1) % 3
        if self.host:
            self.host.apply_visual()

    def switch_position(self):
        self._pre_action_leave_cas()
        global CURRENT_POS_MODE
        CURRENT_POS_MODE = "COVER" if CURRENT_POS_MODE == "FLOATING" else "FLOATING"
        if self.host:
            self.host.reposition_box()

    def font_up(self):
        self._pre_action_leave_cas()
        global CURRENT_FONT_SIZE
        CURRENT_FONT_SIZE += 2
        log(f"[UI] Font size -> {CURRENT_FONT_SIZE}")
        if self.host:
            self.host.apply_visual()
            self.host.reposition_box()

    def font_down(self):
        self._pre_action_leave_cas()
        global CURRENT_FONT_SIZE
        CURRENT_FONT_SIZE = max(12, CURRENT_FONT_SIZE - 2)
        log(f"[UI] Font size -> {CURRENT_FONT_SIZE}")
        if self.host:
            self.host.apply_visual()
            self.host.reposition_box()

    def cycle_width(self):
        self._pre_action_leave_cas()
        global CURRENT_WIDTH_SCALE
        scales = [1.0, 1.1, 1.2, 0.9]
        try:
            idx = scales.index(CURRENT_WIDTH_SCALE)
            CURRENT_WIDTH_SCALE = scales[(idx + 1) % len(scales)]
        except Exception:
            CURRENT_WIDTH_SCALE = 1.0
        log(f"[UI] Box width scale -> {CURRENT_WIDTH_SCALE}")
        if self.host:
            self.host.reposition_box()

    def switch_engine_mode(self):
        self._pre_action_leave_cas()
        global CURRENT_ENGINE_MODE, AUTO_GPU_FALLBACK_CPU, _last_vram_switch_ts
        AUTO_GPU_FALLBACK_CPU = False

        if CURRENT_ENGINE_MODE == "AUTO_GPU":
            CURRENT_ENGINE_MODE = "FORCE_GPU"
        elif CURRENT_ENGINE_MODE == "FORCE_GPU":
            CURRENT_ENGINE_MODE = "FORCE_CPU"
        else:
            CURRENT_ENGINE_MODE = "AUTO_GPU"

        log(f"[COMMAND] OCR Engine -> {CURRENT_ENGINE_MODE}")
        reload_ocr_engine()
        _last_vram_switch_ts = time.time()
        save_cache("engine_switch")

        if self.host:
            self.host.refresh_status()

    # ---------------- Freeze snapshot controls ----------------
    def snapshot_ultra(self):
        self._pre_action_leave_cas()
        if CAPTURE_MODE != 1:
            log("[F10] Snapshot ULTRA ignored (only FREEZE)")
            return
        if self.ocr_worker:
            log("[F10] Snapshot ULTRA -> capture once")
            self.ocr_worker.request_snapshot("ULTRA")

    def toggle_auto_snapshot_anywhere(self):
        if CAS_ACTIVE:
            log("[CAS] F11 -> exit CAS, go FREEZE + AUTO")
            self._exit_cas_restore()

        global CAPTURE_MODE, AUTO_SNAPSHOT_ON
        if CAPTURE_MODE != 1:
            CAPTURE_MODE = 1
            if self.host:
                self.host.update_mode_dot()
            log("[CTRL+F11] Force mode -> FREEZE (from any mode)")

        AUTO_SNAPSHOT_ON = not AUTO_SNAPSHOT_ON
        if AUTO_SNAPSHOT_ON:
            log(f"[CTRL+F11] Auto Snapshot ON | interval={AUTO_SNAPSHOT_INTERVAL_MS}ms")
            self._kick_auto_cycle()
        else:
            log("[CTRL+F11] Auto Snapshot OFF")
            self.auto_timer.stop()

        if self.host:
            self.host.refresh_status()

    def _kick_auto_cycle(self):
        if IS_PAUSED:
            return
        if CAPTURE_MODE != 1:
            return
        if not self.ocr_worker:
            return
        self.ocr_worker.request_snapshot("FAST")

    def _on_snapshot_done(self, kind, pushed_text):
        if not AUTO_SNAPSHOT_ON:
            return
        if CAPTURE_MODE != 1:
            return
        if IS_PAUSED:
            return
        if CAS_ACTIVE:
            return
        self.auto_timer.start(AUTO_SNAPSHOT_INTERVAL_MS)

    def _auto_tick(self):
        if not AUTO_SNAPSHOT_ON:
            return
        if CAPTURE_MODE != 1:
            return
        if IS_PAUSED:
            return
        if CAS_ACTIVE:
            return
        if self.ocr_worker:
            self.ocr_worker.request_snapshot("FAST")
        if self.host:
            self.host.refresh_status()

    # ---------------- CAS (Capture All Screen) ----------------
    def capture_all_screen(self):
        if IS_PAUSED:
            log("[CAS] ignored (paused)")
            return

        if CAS_ACTIVE:
            log("[CAS] Toggle OFF")
            self._exit_cas_restore()
            return

        self.screen = _get_active_screen()
        if not self.screen:
            self.screen = QGuiApplication.primaryScreen()

        self._enter_cas_if_needed()
        if self.cas_host:
            self.cas_host.show()
            self.cas_host.raise_()
            self.cas_host.set_progress(0)

        try:
            if self.cas_worker and self.cas_worker.isRunning():
                log("[CAS] still running -> skip")
                return
        except Exception:
            pass

        self._cas_job_counter += 1
        self._cas_active_job = self._cas_job_counter

        log("[CAS] Toggle ON -> processing (FAST, less accurate)...")
        self.cas_worker = CASWorker(self.screen.geometry(), job_id=self._cas_active_job)
        self.cas_worker.debug.connect(lambda m: log(m))
        self.cas_worker.progress.connect(self._cas_progress_payload)
        self.cas_worker.preview.connect(self._cas_preview_payload)
        self.cas_worker.done.connect(self._cas_apply_payload)
        self.cas_worker.start()

    def _cas_progress_payload(self, pct: int):
        global CAS_PROGRESS
        if not CAS_ACTIVE or not self.cas_host:
            return
        try:
            CAS_PROGRESS = int(_clamp(int(pct), 0, 100))
        except Exception:
            CAS_PROGRESS = 0
        try:
            self.cas_host.set_progress(CAS_PROGRESS)
        except Exception:
            pass

    def _cas_preview_payload(self, payload: object):
        if not CAS_ACTIVE or not self.cas_host:
            return
        try:
            if payload.get("job_id") != self._cas_active_job:
                return
            rgb = payload.get("rgb", None)
            qimg = _qimage_from_rgb(rgb)
            if qimg is None:
                return
            self.cas_host.set_qimage(qimg)
        except Exception as e:
            log(f"[CAS] preview error: {e}")

    def _cas_apply_payload(self, payload: object):
        if not CAS_ACTIVE or not self.cas_host:
            return
        try:
            if payload.get("job_id") != self._cas_active_job:
                return

            rgb = payload.get("rgb", None)
            boxes = payload.get("boxes", [])
            geom = payload.get("geom", None)

            qimg = _render_cas_qimage(rgb, boxes, geom)
            if qimg is None:
                return
            self.cas_host.set_qimage(qimg)
            self.cas_host.set_progress(100)
        except Exception as e:
            log(f"[CAS] apply error: {e}")

# ==============================================================================
# BOOT/UI
# ==============================================================================
def boot_system():
    os.system("cls" if os.name == "nt" else "clear")
    print(VERSION)
    print("=" * 57)
    print("[BOOT] Connecting & syncing all cores...")
    print("=" * 57)

    log(f"[BOOT] CPU threads target = {CPU_THREADS}")
    log(f"[BOOT] v8.8.3 profile | game={ORT_GAME_OVERRIDE} | model={ORT_MODEL_KEY or '-'} | group={ORT_MODEL_GROUP} | policy={ORT_PERFORMANCE_POLICY} | core_profile={ORT_CORE_PROFILE} | engine_policy={ORT_ENGINE_POLICY} | heavy_safe={ORT_HEAVY_GAME_SAFE}")
    log(f"[BOOT] OCR resolution={ORT_OCR_RESOLUTION_PERCENT}% | scan_sleep_gpu={ORT_SCAN_SLEEP_GPU_MS}ms | scan_sleep_cpu={ORT_SCAN_SLEEP_CPU_MS}ms | queue_max={OCR_TO_TRANSLATE_MAX}")
    log(f"[BOOT] v8.7 story scheduler={os.environ.get('ORT_DIALOG_SCHEDULER_PROFILE','interval_auto')} | fast_profile={os.environ.get('ORT_FAST_PROFILE','standard')} | image_hash_gate={os.environ.get('ORT_IMAGE_HASH_GATE','1')} | fuzzy_cache={os.environ.get('ORT_FUZZY_CACHE_KEY','1')} | max_wait={os.environ.get('ORT_DIALOG_MAX_WAIT_MS','auto')}ms | voice_hold={os.environ.get('ORT_DIALOG_VOICE_HOLD_MS','-')}ms")
    if ORT_GFL_LAYOUT:
        log("[BOOT] GFL Dialogue Layout active | layout=GFL_DIALOG_STANDARD | name_roi=1 | body_roi=1 | footer_mask=1 | scene_guard=1 | normalized_cache=1")
    if ORT_GFL2_SPEAKER_ROI:
        log("[BOOT] GFL2 Speaker ROI v2 active | name_pass=detail | temporal_hold=1 | text_repair=1 | stable_final_cache=1")
    if os.environ.get('ORT_FAST_PROFILE_LABEL'):
        log(f"[BOOT] Fast profile: {os.environ.get('ORT_FAST_PROFILE_LABEL')}")
    load_all_learning()

    try:
        _ = argostranslate.translate.get_installed_languages()
        log("[BOOT] Argos models OK.")
        try:
            argos_print_status()
        except Exception:
            pass
    except Exception:
        log("[BOOT] Argos check failed (translation may fallback).")

    log("[BOOT] Initializing OCR...")
    # v8: hormati pilihan engine dari WebUI. Jangan paksa AUTO_GPU saat user memilih CPU/GPU.
    reload_ocr_engine(CURRENT_ENGINE_MODE)
    # v8.7.2: pay IDN/NLP initialization cost before the first visible dialogue.
    if os.environ.get("ORT_IDN_WARMUP", "1") == "1" and "idn" in ORT_MODEL_KEY:
        try:
            _bridge = _get_runtime_bridge()
            _engine = _get_translation_engine() if ORT_RUNTIME_STRATEGY_ENABLED else None
            if _engine:
                _engine.warmup(_bridge)
        except Exception as _exc:
            log(f"[TRANSLATION] warmup unavailable: {_exc}")

    print("")
    print("================= SHORTCUTS =================")
    print(" [F1]  PAUSE / RESUME")
    print(" [F2]  RESET AREA (re-snip)")
    print(" [F3]  CAPTURE MODE: STABLE / FREEZE / HIGH_LATENCY  (or Exit CAS)")
    print(" [F4]  VISUAL STYLE")
    print(" [F5]  BOX POSITION")
    print(" [F6]  FONT SIZE (-)")
    print(" [F7]  FONT SIZE (+)")
    print(" [F8]  BOX WIDTH")
    print(f" [F9]  OCR ENGINE: AUTO_GPU -> FORCE_GPU -> FORCE_CPU  | current={CURRENT_ENGINE_MODE}")
    print(" [Shift+F9] CAS TOGGLE (Capture All Screen)  [OK]")
    print(" [F10] SNAPSHOT ULTRA (FREEZE)")
    if ORT_BOOT_MODE == "auto":
        print(f" [F11]  AUTO STORY MODE active | scheduler={os.environ.get('ORT_DIALOG_SCHEDULER_PROFILE','auto_story')}")
    elif ORT_BOOT_MODE == "freeze":
        print(" [F11]  FREEZE MANUAL MODE active")
    else:
        print(f" [F11]  INTERVAL MODE (switch FREEZE + AUTO SNAPSHOT) | interval={AUTO_SNAPSHOT_INTERVAL_MS}ms")
    print(" [`]   CAS TOGGLE (Capture All Screen)")
    print(" [Shift+F1] CAS TOGGLE (Capture All Screen)")
    print(" [ESC] EXIT")
    print("=================================================")
    print("")
    print("[BOOT] START ENGINE [OK]")
    print("")

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    import atexit
    atexit.register(lambda: _finalize_runtime_shutdown("atexit"))
    try:
        signal.signal(signal.SIGTERM, _signal_shutdown_handler)
        signal.signal(signal.SIGINT, _signal_shutdown_handler)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _signal_shutdown_handler)
    except Exception:
        pass

    app = QApplication(sys.argv)
    _ = Controller()
    return app.exec_()

if __name__ == "__main__":
    raise SystemExit(main())
