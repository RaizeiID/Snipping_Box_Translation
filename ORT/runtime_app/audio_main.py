from __future__ import annotations

import html
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.audio.cloud_streaming import (
    CloudFallbackLatch,
    LiveSubtitleStabilizer,
    normalize_audio_engine,
    normalize_audio_usage,
    resolve_live_media_policy,
)
from app.audio.profiles import get_audio_profile
from app.audio.runtime_modes import HybridFailoverController, normalize_audio_mode, resolve_audio_plan
from app.audio.segment_ledger import SegmentLedger, SegmentTask
from app.runtime.app_state import save_state
from build_info import APP_VERSION_TAG
from status_manager import write_status


BASE_DIR = Path(__file__).resolve().parent
EVENT_PREFIX = "ORT_AUDIO_EVENT "
CAPTURE_EVENT_PREFIX = "ORT_AUDIO_CAPTURE_EVENT "
TRANSLATION_EVENT_PREFIX = "ORT_AUDIO_TRANSLATION_EVENT "
CLOUD_EVENT_PREFIX = "ORT_AUDIO_CLOUD_EVENT "
WINDOWS_ACCESS_VIOLATION = 0xC0000005


def log(message: str) -> None:
    print(str(message), flush=True)


def _write_audio_status(**updates: Any) -> None:
    current = {
        "version": APP_VERSION_TAG,
        "translation_source": "audio",
        "status": "STARTING",
        "profile": os.environ.get("ORT_AUDIO_PROFILE", "normal"),
        "processing": os.environ.get("ORT_AUDIO_PROCESSING", "vad"),
        "input_mode": os.environ.get("ORT_AUDIO_INPUT_MODE", "loopback"),
        "language": os.environ.get("ORT_AUDIO_LANGUAGE", "auto"),
        "device_index": os.environ.get("ORT_AUDIO_DEVICE_INDEX", "-1"),
        "requested_mode": os.environ.get("ORT_AUDIO_REQUESTED_MODE", "hybrid"),
        "effective_mode": os.environ.get("ORT_AUDIO_EFFECTIVE_MODE", "hybrid"),
        "audio_usage": os.environ.get("ORT_AUDIO_USAGE", "live_media"),
        "audio_engine_requested": os.environ.get("ORT_AUDIO_ENGINE_REQUESTED", "azure_fallback"),
        "audio_engine_effective": os.environ.get("ORT_AUDIO_ENGINE_EFFECTIVE", "azure"),
        "asr_device": os.environ.get("ORT_AUDIO_ASR_DEVICE", "cuda"),
        "asr_compute_type": os.environ.get("ORT_AUDIO_ASR_COMPUTE_TYPE", "int8_float16"),
        "cloud_provider": "azure",
        "cloud_connected": False,
    }
    try:
        path = BASE_DIR / "status" / "audio_runtime.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(existing, dict):
                current.update(existing)
    except Exception:
        pass
    current.update(updates)
    write_status("audio_runtime", current, BASE_DIR)
    try:
        save_state({
            "version": APP_VERSION_TAG,
            "status": current.get("status", "RUNNING"),
            "translation_source": "audio",
            "active_engine": current.get("translation_engine", "audio_cpu"),
            "audio_profile": current.get("profile", "normal"),
            "audio_processing": current.get("processing", "vad"),
            "audio_state": current.get("audio_state", current.get("status", "RUNNING")),
            "audio_requested_mode": current.get("requested_mode", "hybrid"),
            "audio_effective_mode": current.get("effective_mode", "hybrid"),
            "audio_usage": current.get("audio_usage", "live_media"),
            "audio_engine_requested": current.get("audio_engine_requested", "azure_fallback"),
            "audio_engine_effective": current.get("audio_engine_effective", "azure"),
        }, BASE_DIR)
    except Exception:
        pass


def _append_audio_event(event_type: str, payload: dict) -> None:
    try:
        from translation_event_logger import append_event

        append_event(event_type, payload, source_module="audio_main")
    except Exception:
        pass


class AudioOverlay(QWidget):
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._drag_origin: Optional[QPoint] = None
        self.show_source_text = str(os.environ.get("ORT_AUDIO_SHOW_SOURCE", "1")).lower() in {"1", "true", "yes", "on"}
        self.setWindowTitle(f"ORT Audio · {APP_VERSION_TAG}")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(720)
        self.setMaximumWidth(1120)

        container = QFrame(self)
        container.setObjectName("container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 15, 22, 17)
        layout.setSpacing(7)

        header = QHBoxLayout()
        self.mode_label = QLabel("AUDIO · HYBRID")
        self.mode_label.setObjectName("mode")
        self.status_label = QLabel("Menyiapkan model audio…")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.mode_label)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.source_label = QLabel("")
        self.source_label.setObjectName("source")
        self.source_label.setWordWrap(True)
        self.source_label.hide()
        layout.addWidget(self.source_label)

        self.translation_label = QLabel("ORT sedang menunggu suara karakter…")
        self.translation_label.setObjectName("translation")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.translation_label.setFont(QFont("Segoe UI", 15, QFont.DemiBold))
        layout.addWidget(self.translation_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(container)
        self.setStyleSheet("""
            QFrame#container {
                background: rgba(4, 10, 22, 232);
                border: 1px solid rgba(56, 189, 248, 135);
                border-radius: 17px;
            }
            QLabel#mode {
                color: #7dd3fc;
                font: 800 10pt "Segoe UI";
                letter-spacing: 1px;
            }
            QLabel#status {
                color: #94a3b8;
                font: 600 9pt "Segoe UI";
            }
            QLabel#source {
                color: #94a3b8;
                font: 9pt "Segoe UI";
            }
            QLabel#translation {
                color: #f8fafc;
                padding-top: 1px;
            }
        """)
        self.adjustSize()

    def show_centered_bottom(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(980, max(720, int(area.width() * 0.62)))
            self.resize(width, self.sizeHint().height())
            self.move(area.x() + (area.width() - width) // 2, area.y() + area.height() - self.height() - 72)
        self.show()
        self.raise_()

    def set_state(self, text: str) -> None:
        self.status_label.setText(str(text or ""))

    def set_transcript(self, text: str) -> None:
        clean = " ".join(str(text or "").split())
        self.source_label.setText("Preview EN: " + clean)
        self.source_label.setToolTip(clean)
        self.source_label.setVisible(self.show_source_text)
        # Keep the last usable translation visible until the next result is
        # ready. Only the compact status changes, so the overlay swaps atomically
        # instead of flashing a placeholder between utterances.
        self.status_label.setText("Menerjemahkan · CPU")
        self.translation_label.setStyleSheet("color:#f8fafc;")
        self.adjustSize()

    def set_translation(self, source: str, translation: str, status: str) -> None:
        self.source_label.setText("Preview EN: " + " ".join(str(source or "").split()))
        self.source_label.setVisible(self.show_source_text)
        self.translation_label.setText(str(translation or source or ""))
        self.translation_label.setStyleSheet("color:#f8fafc;")
        self.status_label.setText(status)
        self.adjustSize()

    def set_cloud_source(self, source: str, latency_ms: int = 0) -> None:
        clean_source = " ".join(str(source or "").split())
        if clean_source:
            self.source_label.setText("Preview EN: " + clean_source)
            self.source_label.setVisible(self.show_source_text)
        self.status_label.setText(f"Azure · memahami ucapan · {max(0, int(latency_ms))} ms")
        self.adjustSize()

    def set_cloud_translation(self, source: str, translation: str, stable: bool, latency_ms: int = 0) -> None:
        clean_source = " ".join(str(source or "").split())
        clean_translation = " ".join(str(translation or source or "").split())
        self.source_label.setText("Preview EN: " + clean_source)
        self.source_label.setVisible(self.show_source_text)
        self.translation_label.setText(clean_translation)
        if stable:
            self.translation_label.setStyleSheet("color:#f8fafc;")
            self.status_label.setText(f"Azure · final · {max(0, int(latency_ms))} ms")
        else:
            self.translation_label.setStyleSheet("color:#bae6fd;")
            self.status_label.setText(f"Azure · live · {max(0, int(latency_ms))} ms")
        self.adjustSize()

    def set_error(self, message: str) -> None:
        self.status_label.setText("Audio berhenti")
        self.translation_label.setText("Audio Error · " + str(message or "Tidak diketahui"))
        self.adjustSize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self.close_requested.emit()
        event.accept()


class CaptureBridge(QObject):
    event_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
    process_finished = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stopping = False

    def start(self, spool_dir: Path) -> None:
        capture_python = Path(os.environ.get("ORT_AUDIO_CAPTURE_PYTHON", ""))
        sidecar = BASE_DIR / "audio_capture_sidecar.py"
        if not capture_python.exists():
            raise FileNotFoundError(f"Runtime capture Audio belum siap: {capture_python}")
        command = [
            str(capture_python),
            str(sidecar),
            "--profile", os.environ.get("ORT_AUDIO_PROFILE", "normal"),
            "--processing", os.environ.get("ORT_AUDIO_PROCESSING", "vad"),
            "--device-index", os.environ.get("ORT_AUDIO_DEVICE_INDEX", "-1"),
            "--spool-dir", str(spool_dir),
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            command,
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
        self._reader = threading.Thread(target=self._read_loop, name="ort-audio-capture-reader", daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            if line.startswith(CAPTURE_EVENT_PREFIX):
                try:
                    event = json.loads(line[len(CAPTURE_EVENT_PREFIX):])
                    if isinstance(event, dict):
                        self.event_received.emit(event)
                        continue
                except Exception:
                    pass
            self.log_received.emit(line)
        self.process_finished.emit(int(self.proc.wait()))

    def stop(self) -> None:
        self._stopping = True
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                proc.terminate()
            proc.wait(timeout=4.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class CloudBridge(QObject):
    event_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
    process_finished = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stopping = False

    def start(self, spool_dir: Path) -> None:
        cloud_python = Path(str(os.environ.get("ORT_AUDIO_CLOUD_PYTHON", "") or ""))
        config_path = Path(str(os.environ.get("ORT_AUDIO_CLOUD_CONFIG", "") or ""))
        sidecar = BASE_DIR / "audio_cloud_sidecar.py"
        if not cloud_python.exists():
            raise FileNotFoundError(f"Runtime Azure belum siap: {cloud_python}")
        command = [
            str(cloud_python),
            str(sidecar),
            "--stream",
            "--config-path", str(config_path),
            "--source-locale", os.environ.get("ORT_AUDIO_CLOUD_SOURCE_LOCALE", "ja-JP"),
            "--target-language", os.environ.get("ORT_AUDIO_CLOUD_TARGET_LANGUAGE", "id"),
            "--usage", os.environ.get("ORT_AUDIO_USAGE", "live_media"),
            "--realtime-profile", os.environ.get("ORT_AUDIO_PROFILE", "normal"),
            "--game", os.environ.get("ORT_GAME_PROFILE", "GFL2_EXILIUM"),
            "--input-mode", os.environ.get("ORT_AUDIO_INPUT_MODE", "loopback"),
            "--device-index", os.environ.get("ORT_AUDIO_DEVICE_INDEX", "-1"),
            "--test-file", os.environ.get("ORT_AUDIO_TEST_FILE", ""),
            "--spool-dir", str(spool_dir),
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            command,
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
        self._reader = threading.Thread(target=self._read_loop, name="ort-audio-cloud-reader", daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            if line.startswith(CLOUD_EVENT_PREFIX):
                try:
                    event = json.loads(line[len(CLOUD_EVENT_PREFIX):])
                    if isinstance(event, dict):
                        self.event_received.emit(event)
                        continue
                except Exception:
                    pass
            self.log_received.emit(line)
        self.process_finished.emit(int(self.proc.wait()))

    def stop(self) -> None:
        self._stopping = True
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                proc.terminate()
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class RealtimeLocalBridge(QObject):
    event_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
    process_finished = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stopping = False

    def start(self) -> None:
        requested_mode = normalize_audio_mode(os.environ.get("ORT_AUDIO_REQUESTED_MODE", "hybrid"))
        effective_mode = str(os.environ.get("ORT_AUDIO_EFFECTIVE_MODE", requested_mode) or requested_mode).lower()
        profile = get_audio_profile(os.environ.get("ORT_AUDIO_PROFILE", "normal"))
        plan = resolve_audio_plan(requested_mode, profile.key)
        use_gpu = effective_mode in {"gpu", "hybrid"}
        active_spec = plan.primary if use_gpu else (plan.fallback or plan.primary)
        python_key = "ORT_AUDIO_GPU_PYTHON" if active_spec.device == "cuda" else "ORT_AUDIO_CPU_PYTHON"
        runtime_python = Path(str(os.environ.get(python_key, "") or ""))
        if not runtime_python.exists():
            raise FileNotFoundError(f"Runtime local real-time tidak ditemukan: {runtime_python}")
        sidecar = BASE_DIR / "audio_realtime_local_sidecar.py"
        fallback_model = plan.fallback.model_size if plan.fallback else "base"
        command = [
            str(runtime_python),
            str(sidecar),
            "--stream-json",
            "--profile", profile.key,
            "--language", os.environ.get("ORT_AUDIO_LANGUAGE", "auto"),
            "--model-root", os.environ.get("ORT_AUDIO_MODEL_ROOT", str(BASE_DIR / "_runtime" / "audio_models")),
            "--model-size", active_spec.model_size,
            "--fallback-model-size", fallback_model,
            "--asr-device", active_spec.device,
            "--compute-type", active_spec.compute_type,
            "--cpu-threads", str(active_spec.cpu_threads),
            "--input-mode", os.environ.get("ORT_AUDIO_INPUT_MODE", "loopback"),
            "--device-index", os.environ.get("ORT_AUDIO_DEVICE_INDEX", "-1"),
            "--test-file", os.environ.get("ORT_AUDIO_TEST_FILE", ""),
            "--game", os.environ.get("ORT_GAME_PROFILE", "GFL2_EXILIUM"),
            "--language-correction", os.environ.get("ORT_AUDIO_LANGUAGE_AUTOCORRECT", "balanced"),
        ]
        if str(os.environ.get("ORT_AUDIO_LANGUAGE_LOCK", "0")).lower() in {"1", "true", "yes", "on"}:
            command.append("--language-lock")
        if requested_mode == "hybrid":
            command.append("--allow-cpu-fallback")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["OMP_NUM_THREADS"] = str(active_spec.cpu_threads)
        env["ORT_CPU_THREADS"] = str(active_spec.cpu_threads)
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            command,
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
        self._reader = threading.Thread(target=self._read_loop, name="ort-audio-local-realtime-reader", daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            if line.startswith(EVENT_PREFIX):
                try:
                    event = json.loads(line[len(EVENT_PREFIX):])
                    if isinstance(event, dict):
                        self.event_received.emit(event)
                        continue
                except Exception:
                    pass
            self.log_received.emit(line)
        self.process_finished.emit(int(self.proc.wait()))

    def stop(self) -> None:
        self._stopping = True
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                proc.terminate()
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class ASRCoordinator(QObject):
    event_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
    runtime_event = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.requested_mode = normalize_audio_mode(os.environ.get("ORT_AUDIO_REQUESTED_MODE", "hybrid"))
        self.effective_mode = str(os.environ.get("ORT_AUDIO_EFFECTIVE_MODE", self.requested_mode) or self.requested_mode).lower()
        self.profile = get_audio_profile(os.environ.get("ORT_AUDIO_PROFILE", "normal"))
        self.plan = resolve_audio_plan(self.requested_mode, self.profile.key)
        self.failover = HybridFailoverController.create(self.requested_mode, self.effective_mode)
        self.ledger = SegmentLedger(max_pending=3)
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._ready = False
        self._worker_device = ""
        self._last_error_code = ""
        self._return_to_gpu_after_replay = False
        self._planned_switch_device = ""

    @staticmethod
    def _exit_label(code: int) -> str:
        unsigned = int(code) & 0xFFFFFFFF
        if unsigned == WINDOWS_ACCESS_VIOLATION:
            return "0xC0000005"
        return str(code)

    def _spec_for(self, device: str):
        if device == "cuda":
            return self.plan.primary
        if self.requested_mode == "hybrid" and self.plan.fallback is not None:
            return self.plan.fallback
        return self.plan.primary

    def _python_for(self, device: str) -> Path:
        key = "ORT_AUDIO_GPU_PYTHON" if device == "cuda" else "ORT_AUDIO_CPU_PYTHON"
        return Path(str(os.environ.get(key, "") or ""))

    def _initial_device(self) -> str:
        return "cuda" if self.effective_mode in {"gpu", "hybrid"} else "cpu"

    def start(self) -> None:
        with self._lock:
            self._launch_locked(self._initial_device())

    def _launch_locked(self, device: str) -> None:
        if self._stopping.is_set():
            return
        python_path = self._python_for(device)
        if not python_path.exists():
            raise FileNotFoundError(f"Runtime ASR {device} tidak ditemukan: {python_path}")
        spec = self._spec_for(device)
        command = [
            str(python_path),
            str(BASE_DIR / "audio_asr_sidecar.py"),
            "--worker-json",
            "--profile", self.profile.key,
            "--processing", os.environ.get("ORT_AUDIO_PROCESSING", "vad"),
            "--language", os.environ.get("ORT_AUDIO_LANGUAGE", "auto"),
            "--model-root", os.environ.get("ORT_AUDIO_MODEL_ROOT", str(BASE_DIR / "_runtime" / "audio_models")),
            "--model-size", spec.model_size,
            "--asr-device", spec.device,
            "--compute-type", spec.compute_type,
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["OMP_NUM_THREADS"] = str(spec.cpu_threads)
        env["ORT_CPU_THREADS"] = str(spec.cpu_threads)
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            command,
            cwd=str(BASE_DIR),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        self._proc = proc
        self._ready = False
        self._worker_device = device
        self._last_error_code = ""
        self._reader = threading.Thread(
            target=self._read_loop,
            args=(proc, device),
            name=f"ort-audio-asr-{device}-reader",
            daemon=True,
        )
        self._reader.start()
        self.runtime_event.emit({
            "type": "ASR_PROCESS_STARTED",
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "worker_device": device,
            "model": spec.model_size,
            "compute_type": spec.compute_type,
            "pid": int(proc.pid),
        })

    def submit(self, payload: dict) -> None:
        task = SegmentTask.from_payload(payload)
        with self._lock:
            dropped = self.ledger.submit(task)
            if dropped is not None:
                self._cleanup_task(dropped)
                self.event_received.emit({
                    "type": "metric",
                    "name": "asr_queue_drop",
                    "segment_id": dropped.segment_id,
                })
            self._dispatch_locked()

    def _dispatch_locked(self) -> None:
        proc = self._proc
        if not self._ready or proc is None or proc.poll() is not None or proc.stdin is None:
            return
        task = self.ledger.dispatch_next()
        if task is None:
            return
        payload = {"type": "transcribe", **task.as_dict()}
        try:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except Exception as exc:
            self.ledger.requeue_inflight()
            self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] ASR request write error: {exc}")
            try:
                proc.terminate()
            except Exception:
                pass

    def _read_loop(self, proc: subprocess.Popen, device: str) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if line.startswith(EVENT_PREFIX):
                try:
                    event = json.loads(line[len(EVENT_PREFIX):])
                    if isinstance(event, dict):
                        self._handle_event(proc, event)
                        continue
                except Exception:
                    pass
            self.log_received.emit(line)
        self._handle_exit(proc, int(proc.wait()), device)

    def _handle_event(self, proc: subprocess.Popen, event: dict) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "state" and str(event.get("state") or "").upper() == "MODEL_READY":
            with self._lock:
                if proc is not self._proc:
                    return
                self._ready = True
                self._dispatch_locked()
        elif event_type == "error" and event.get("fatal"):
            self._last_error_code = str(event.get("code") or "ASR_WORKER_ERROR")
        elif event_type == "segment_complete":
            with self._lock:
                completed = self.ledger.acknowledge(str(event.get("segment_id") or ""))
                if completed is not None:
                    self._cleanup_task(completed)
                    if completed.kind == "file":
                        self.runtime_event.emit({"type": "ASR_FILE_COMPLETE", "segment_id": completed.segment_id})
                should_retry_gpu = bool(
                    completed is not None
                    and self.requested_mode == "hybrid"
                    and self._worker_device == "cpu"
                    and self._return_to_gpu_after_replay
                    and not self.failover.circuit_open
                )
                if should_retry_gpu:
                    self._return_to_gpu_after_replay = False
                    self._planned_switch_device = "cuda"
                    self._ready = False
                    if self._proc is not None and self._proc.poll() is None and self._proc.stdin is not None:
                        try:
                            self._proc.stdin.write('{"type":"shutdown"}\n')
                            self._proc.stdin.flush()
                        except Exception:
                            try:
                                self._proc.terminate()
                            except Exception:
                                pass
                else:
                    self._dispatch_locked()
        self.event_received.emit(event)

    def _handle_exit(self, proc: subprocess.Popen, code: int, device: str) -> None:
        decision = None
        replay = None
        planned_switch = ""
        with self._lock:
            if proc is not self._proc:
                return
            self._proc = None
            self._ready = False
            planned_switch = self._planned_switch_device
            self._planned_switch_device = ""
            replay = self.ledger.requeue_inflight()
            if not self._stopping.is_set() and not planned_switch:
                decision = self.failover.worker_failure(device, self._last_error_code or f"ASR_WORKER_EXIT_{self._exit_label(code)}")
                self.effective_mode = str(decision.get("effective_mode") or self.effective_mode)
        self.runtime_event.emit({
            "type": "ASR_PROCESS_EXIT",
            "exit_code": int(code),
            "exit_label": self._exit_label(code),
            "worker_device": device,
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "replay_segment_id": replay.segment_id if replay else "",
            "planned_switch": planned_switch,
        })
        if self._stopping.is_set():
            return
        if planned_switch:
            with self._lock:
                self.effective_mode = "hybrid" if planned_switch == "cuda" else self.effective_mode
                self.failover.effective_mode = self.effective_mode
                self.runtime_event.emit({
                    "type": "HYBRID_GPU_RETRY",
                    "effective_mode": self.effective_mode,
                    "gpu_failures": self.failover.gpu_failures,
                    "worker_device": planned_switch,
                })
                try:
                    self._launch_locked(planned_switch)
                except Exception as exc:
                    self.event_received.emit({"type": "error", "stage": "asr_gpu_retry", "message": str(exc), "fatal": True})
            return
        if decision and decision.get("action") == "fallback_cpu":
            self._return_to_gpu_after_replay = bool(decision.get("retry_gpu_after_replay"))
            self.runtime_event.emit({
                "type": "HYBRID_FAILOVER",
                **decision,
                "replay_segment_id": replay.segment_id if replay else "",
                "from_device": "cuda",
                "to_device": "cpu",
            })
            self.log_received.emit(
                f"[AUDIO {APP_VERSION_TAG}] HYBRID_FAILOVER | reason={decision.get('reason')} | "
                f"replay_generation={replay.segment_id if replay else '-'} | from=gpu | to=cpu | "
                f"gpu_failures={decision.get('gpu_failures')} | circuit_open={int(bool(decision.get('circuit_open')))}"
            )
            with self._lock:
                try:
                    self._launch_locked("cpu")
                except Exception as exc:
                    self.event_received.emit({"type": "error", "stage": "asr_fallback", "message": str(exc), "fatal": True})
            return
        self.event_received.emit({
            "type": "error",
            "stage": "asr_process",
            "code": self._last_error_code or "ASR_WORKER_EXIT",
            "message": f"ASR {device} berhenti dengan code {self._exit_label(code)}",
            "fatal": True,
        })

    @staticmethod
    def _cleanup_task(task: SegmentTask) -> None:
        if task.kind != "npy":
            return
        try:
            Path(task.path).unlink(missing_ok=True)
        except Exception:
            pass

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            proc = self._proc
            reader = self._reader
            if proc is not None and proc.poll() is None and proc.stdin is not None:
                try:
                    proc.stdin.write('{"type":"shutdown"}\n')
                    proc.stdin.flush()
                except Exception:
                    pass
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=4.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if reader is not None and reader.is_alive():
            reader.join(timeout=1.0)
        with self._lock:
            for task in self.ledger.clear():
                self._cleanup_task(task)
            self._proc = None
            self._ready = False
            self._planned_switch_device = ""
            self._return_to_gpu_after_replay = False


class TranslationCoordinator(QObject):
    translation_ready = pyqtSignal(dict)
    state_changed = pyqtSignal(str)
    log_received = pyqtSignal(str)
    runtime_event = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stopping = threading.Event()
        self._lock = threading.RLock()
        self._generation = 0
        self._pending: Optional[dict] = None
        self._inflight: Optional[dict] = None
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._ready = False
        self._safe_mode = False
        self._restart_count = 0
        self._last_emitted_by_segment: dict[str, int] = {}
        self._latest_segment_id = ""

    @staticmethod
    def _unsigned_exit_code(code: int) -> int:
        return int(code) & 0xFFFFFFFF

    @classmethod
    def _exit_label(cls, code: int) -> str:
        unsigned = cls._unsigned_exit_code(code)
        if unsigned == WINDOWS_ACCESS_VIOLATION:
            return "0xC0000005 (native access violation)"
        return str(code)

    def _build_env(self, safe_mode: bool) -> dict:
        env = os.environ.copy()
        profile = get_audio_profile(env.get("ORT_AUDIO_PROFILE", "normal"))
        translation_threads = max(1, min(2, max(1, profile.cpu_threads // 2)))
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["ORT_TRANSLATION_SOURCE"] = "audio"
        env["ORT_AUDIO_SOURCE"] = "1"
        env["ORT_AUDIO_TRANSLATION_THREADS"] = str(1 if safe_mode else translation_threads)
        env["OMP_NUM_THREADS"] = str(1 if safe_mode else translation_threads)
        env["OPENBLAS_NUM_THREADS"] = str(1 if safe_mode else translation_threads)
        env["MKL_NUM_THREADS"] = str(1 if safe_mode else translation_threads)
        env["CT2_PACKED_GEMM"] = "0"
        env["CT2_USE_EXPERIMENTAL_PACKED_GEMM"] = "0"
        if safe_mode:
            env["ORT_AUDIO_TRANSLATION_SAFE_MODE"] = "1"
            env["ORT_DISABLE_CT2"] = "1"
        else:
            env.pop("ORT_AUDIO_TRANSLATION_SAFE_MODE", None)
            env.pop("ORT_DISABLE_CT2", None)
        return env

    def _launch_locked(self, safe_mode: bool) -> None:
        sidecar = BASE_DIR / "audio_translation_sidecar.py"
        if not sidecar.is_file():
            raise FileNotFoundError(f"Translation sidecar tidak ditemukan: {sidecar}")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            [sys.executable, str(sidecar)],
            cwd=str(BASE_DIR),
            env=self._build_env(safe_mode),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        self._proc = proc
        self._ready = False
        self._safe_mode = bool(safe_mode)
        self._reader = threading.Thread(
            target=self._read_loop,
            args=(proc, bool(safe_mode)),
            name="ort-audio-translation-sidecar-reader",
            daemon=True,
        )
        self._reader.start()
        self.runtime_event.emit({
            "type": "TRANSLATION_PROCESS_STARTED",
            "safe_mode": bool(safe_mode),
            "restart_count": self._restart_count,
            "pid": int(proc.pid),
        })

    def start(self) -> None:
        with self._lock:
            if self._stopping.is_set():
                return
            if self._proc is not None and self._proc.poll() is None:
                return
            try:
                self._launch_locked(self._safe_mode)
                self.state_changed.emit("Menyiapkan penerjemah · CPU")
            except Exception as exc:
                self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] translation sidecar start error: {exc}")
                self.runtime_event.emit({
                    "type": "TRANSLATION_PROCESS_START_ERROR",
                    "message": str(exc),
                    "safe_mode": self._safe_mode,
                })

    def submit(self, event: dict) -> int:
        with self._lock:
            self._generation += 1
            item = {**event, "generation_id": self._generation, "received_at": time.perf_counter()}
            self._latest_segment_id = str(item.get("segment_id") or self._latest_segment_id)
            dropped = self._pending
            self._pending = item
            if dropped is not None:
                self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] stale transcript dropped | generation={dropped.get('generation_id', '-')}")
            if self._proc is None:
                self.start()
            self._dispatch_locked()
            return self._generation

    def _dispatch_locked(self) -> None:
        proc = self._proc
        if not self._ready or self._inflight is not None or self._pending is None:
            return
        if proc is None or proc.poll() is not None or proc.stdin is None:
            return
        item = self._pending
        payload = {
            "type": "translate",
            "generation_id": int(item.get("generation_id", 0)),
            "text": str(item.get("text") or ""),
            "asr_ms": int(item.get("asr_ms", 0) or 0),
            "requested_language": str(item.get("requested_language") or os.environ.get("ORT_AUDIO_LANGUAGE_REQUESTED", "auto")),
            "detected_language": str(item.get("detected_language") or ""),
            "source_language": str(item.get("source_language") or item.get("detected_language") or ""),
            "bridge_language": str(item.get("bridge_language") or "en"),
            "asr_task": str(item.get("asr_task") or "transcribe"),
            "japanese_specialist": bool(item.get("japanese_specialist")),
            "language_probability": float(item.get("language_probability", 0.0) or 0.0),
            "audio_seconds": float(item.get("audio_seconds", 0.0) or 0.0),
            "model": str(item.get("model") or ""),
            "profile": str(item.get("profile") or ""),
            "segment_id": str(item.get("segment_id") or ""),
            "asr_device": str(item.get("asr_device") or ""),
            "asr_compute_type": str(item.get("asr_compute_type") or ""),
            "quality": item.get("quality") or {},
            "quality_retry": bool(item.get("quality_retry")),
            "glossary_hits": item.get("glossary_hits") or [],
        }
        try:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            self._pending = None
            self._inflight = item
            self.state_changed.emit("Menerjemahkan · CPU")
        except Exception as exc:
            self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] translation request write error: {exc}")
            try:
                proc.terminate()
            except Exception:
                pass

    def _read_loop(self, proc: subprocess.Popen, safe_mode: bool) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if line.startswith(TRANSLATION_EVENT_PREFIX):
                try:
                    event = json.loads(line[len(TRANSLATION_EVENT_PREFIX):])
                    if isinstance(event, dict):
                        self._handle_process_event(proc, event)
                        continue
                except Exception:
                    pass
            self.log_received.emit(line)
        code = int(proc.wait())
        self._handle_process_exit(proc, code, safe_mode)

    def _handle_process_event(self, proc: subprocess.Popen, event: dict) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            if state == "TRANSLATOR_READY":
                with self._lock:
                    if proc is not self._proc:
                        return
                    self._ready = True
                    self._dispatch_locked()
                    busy = self._inflight is not None
                if not busy:
                    mode = "Argos recovery" if event.get("safe_mode") else "ORTCore Fast V2"
                    self.state_changed.emit(f"Penerjemah siap · {mode}")
            elif state == "TRANSLATOR_LOADING":
                self.state_changed.emit("Memuat penerjemah · mode aman" if event.get("safe_mode") else "Memuat penerjemah · CPU")
            self.runtime_event.emit(event)
            return
        if event_type == "translation":
            generation = int(event.get("generation_id", 0) or 0)
            with self._lock:
                if proc is not self._proc:
                    return
                original = self._inflight or {}
                self._inflight = None
                payload = {**original, **event}
                segment_id = str(payload.get("segment_id") or "")
                last_emitted = int(self._last_emitted_by_segment.get(segment_id, 0) or 0)
                is_current_segment = not self._latest_segment_id or segment_id == self._latest_segment_id
                should_emit = generation > last_emitted and is_current_segment
                if should_emit:
                    self._last_emitted_by_segment[segment_id] = generation
                self._dispatch_locked()
            # v8.9.8: a completed translation is useful even when a newer ASR
            # revision of the same segment is already queued. The current-segment
            # guard prevents an older speaker from overwriting a newer subtitle.
            # Blocking every non-latest generation starved Japanese partials and
            # delayed Indonesian until a pause.
            if should_emit:
                self.translation_ready.emit(payload)
            else:
                self.log_received.emit(
                    f"[AUDIO {APP_VERSION_TAG}] superseded translation ignored | generation={generation} "
                    f"segment={segment_id} current={self._latest_segment_id or '-'} last_emitted={last_emitted}"
                )
            return
        if event_type == "error":
            self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] translation sidecar error: {event.get('message', 'unknown error')}")
            self.runtime_event.emit(event)

    def _handle_process_exit(self, proc: subprocess.Popen, code: int, safe_mode: bool) -> None:
        fallback_payload: Optional[dict] = None
        restart = False
        with self._lock:
            if proc is not self._proc:
                return
            self._proc = None
            self._ready = False
            if self._inflight is not None:
                if self._pending is None or int(self._inflight.get("generation_id", 0)) >= int(self._pending.get("generation_id", 0)):
                    self._pending = self._inflight
                self._inflight = None
            if not self._stopping.is_set() and not safe_mode:
                self._restart_count += 1
                self._safe_mode = True
                restart = True
            elif not self._stopping.is_set() and self._pending is not None:
                item = self._pending
                self._pending = None
                fallback_payload = {
                    **item,
                    "type": "translation",
                    "translation": str(item.get("text") or ""),
                    "translation_ms": 0,
                    "total_ms": int(item.get("asr_ms", 0) or 0),
                    "translation_engine": "source_fallback",
                    "cache": "MISS",
                    "translation_error": f"translation sidecar exit {self._exit_label(code)}",
                    "translation_safe_mode": True,
                }
        label = self._exit_label(code)
        self.runtime_event.emit({
            "type": "TRANSLATION_PROCESS_EXIT",
            "exit_code": int(code),
            "exit_label": label,
            "native_access_violation": self._unsigned_exit_code(code) == WINDOWS_ACCESS_VIOLATION,
            "safe_mode": bool(safe_mode),
            "restart": bool(restart),
            "restart_count": self._restart_count,
        })
        if restart:
            self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] translation process exit {label}; restarting with isolated Argos recovery")
            self.state_changed.emit("Memulihkan penerjemah · mode aman")
            with self._lock:
                if not self._stopping.is_set() and (self._proc is None or self._proc.poll() is not None):
                    try:
                        self._launch_locked(True)
                    except Exception as exc:
                        self.log_received.emit(f"[AUDIO {APP_VERSION_TAG}] translation recovery start error: {exc}")
            return
        if fallback_payload is not None:
            self.translation_ready.emit(fallback_payload)
        elif not self._stopping.is_set():
            self.state_changed.emit("ASR aktif · penerjemah belum tersedia")

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            proc = self._proc
            reader = self._reader
            self._pending = None
            self._inflight = None
            if proc is not None and proc.poll() is None and proc.stdin is not None:
                try:
                    proc.stdin.write('{"type":"shutdown"}\n')
                    proc.stdin.flush()
                except Exception:
                    pass
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=4.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if reader is not None and reader.is_alive():
            reader.join(timeout=1.0)
        with self._lock:
            self._proc = None
            self._ready = False

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def safe_mode(self) -> bool:
        with self._lock:
            return self._safe_mode

    @property
    def restart_count(self) -> int:
        with self._lock:
            return self._restart_count


class AudioApplication(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.overlay = AudioOverlay()
        self.capture = CaptureBridge()
        self.cloud = CloudBridge()
        self.local_live = RealtimeLocalBridge()
        self.asr = ASRCoordinator()
        self.translator = TranslationCoordinator()
        self.requested_mode = self.asr.requested_mode
        self.effective_mode = self.asr.effective_mode
        self.audio_usage = normalize_audio_usage(os.environ.get("ORT_AUDIO_USAGE", "live_media"))
        self.engine_requested = normalize_audio_engine(os.environ.get("ORT_AUDIO_ENGINE_REQUESTED", "azure_fallback"))
        self.engine_effective = str(os.environ.get("ORT_AUDIO_ENGINE_EFFECTIVE", "azure") or "azure").strip().lower()
        self.realtime_policy = resolve_live_media_policy(
            self.audio_usage,
            os.environ.get("ORT_AUDIO_CLOUD_SOURCE_LOCALE", os.environ.get("ORT_AUDIO_LANGUAGE", "ja")),
            os.environ.get("ORT_AUDIO_PROFILE", "normal"),
        )
        self.subtitle_stabilizer = LiveSubtitleStabilizer(
            minimum_interim_interval=self.realtime_policy.minimum_interim_interval_s
        )
        self.cloud_fallback = CloudFallbackLatch()
        self._closing = False
        self._local_started = False
        self._cloud_error_reason = ""
        self._cloud_replay_path = ""
        self._last_meter_at = 0.0
        self._last_event: Dict[str, Any] = {}
        self._spool_dir: Optional[Path] = None

        self.capture.event_received.connect(self._handle_capture_event)
        self.capture.log_received.connect(log)
        self.capture.process_finished.connect(self._capture_finished)
        self.cloud.event_received.connect(self._handle_cloud_event)
        self.cloud.log_received.connect(log)
        self.cloud.process_finished.connect(self._cloud_finished)
        self.local_live.event_received.connect(self._handle_local_live_event)
        self.local_live.log_received.connect(log)
        self.local_live.process_finished.connect(self._local_live_finished)
        self.asr.event_received.connect(self._handle_asr_event)
        self.asr.log_received.connect(log)
        self.asr.runtime_event.connect(self._handle_asr_runtime_event)
        self.translator.translation_ready.connect(self._translation_ready)
        self.translator.state_changed.connect(self.overlay.set_state)
        self.translator.log_received.connect(log)
        self.translator.runtime_event.connect(self._handle_translation_runtime_event)
        self.overlay.close_requested.connect(self.shutdown)
        self.app.aboutToQuit.connect(self._cleanup)

        self.stop_timer = QTimer(self)
        self.stop_timer.timeout.connect(self._check_stop_request)
        self.stop_timer.start(300)

    def _update_mode_label(self) -> None:
        profile = get_audio_profile(os.environ.get("ORT_AUDIO_PROFILE", "normal"))
        usage_label = "LIVE MEDIA" if self.audio_usage == "live_media" else "CONVERSATION"
        engine_labels = {
            "azure": "AZURE LIVE",
            "local": "LOCAL SEGMENT",
            "local_live": "LOCAL LIVE",
            "local_guard": "LOCAL LIVE GUARD",
            "local_fallback": "LOCAL LIVE FALLBACK",
        }
        labels = {
            "cpu": "CPU INT8",
            "gpu": "GPU INT8-FP16",
            "hybrid": "HYBRID GPU→CPU",
            "cpu_guard": "HYBRID · CPU GUARD",
            "cpu_recovery": "HYBRID · CPU REPLAY",
            "cpu_fallback": "HYBRID · CPU FALLBACK",
        }
        execution = labels.get(self.effective_mode, self.effective_mode.upper())
        engine = engine_labels.get(self.engine_effective, self.engine_effective.upper())
        self.overlay.mode_label.setText(f"AUDIO · {usage_label} · {engine} · {profile.label.upper()} {execution}")

    def start(self) -> None:
        launcher_version = str(os.environ.get("ORT_LAUNCHER_VERSION", "") or "").strip()
        pipeline_contract = str(os.environ.get("ORT_AUDIO_PIPELINE_CONTRACT", "") or "").strip()
        if launcher_version != APP_VERSION_TAG or pipeline_contract != "rolling-partial-v2":
            message = (
                "Instalasi/proses ORT tercampur. "
                f"launcher={launcher_version or 'missing'}, audio={APP_VERSION_TAG}, contract={pipeline_contract or 'missing'}. "
                "Tutup seluruh WebUI dan Audio ORT, ekstrak ulang patch v8.9.9, lalu jalankan VERIFY_ORT_V8_9_9.bat."
            )
            self._update_mode_label()
            self.overlay.show_centered_bottom()
            self.overlay.set_error(message)
            _write_audio_status(status="ERROR", audio_state="VERSION_CONTRACT_FAILED", last_error=message)
            log(f"[AUDIO {APP_VERSION_TAG}][VERSION CONTRACT FAILED] {message}")
            return
        profile = get_audio_profile(os.environ.get("ORT_AUDIO_PROFILE", "normal"))
        plan = resolve_audio_plan(self.requested_mode, profile.key)
        active_spec = plan.primary if self.effective_mode in {"gpu", "hybrid"} else (plan.fallback or plan.primary)
        cloud_active = self.engine_effective == "azure"
        runtime_asr_model = "azure_speech_translation" if cloud_active else active_spec.model_size
        runtime_asr_device = "cloud" if cloud_active else active_spec.device
        runtime_asr_compute = "streaming" if cloud_active else active_spec.compute_type
        spool_root = Path(str(os.environ.get("ORT_AUDIO_SPOOL_ROOT", "") or (Path(tempfile.gettempdir()) / "ort_audio_spool")))
        spool_root.mkdir(parents=True, exist_ok=True)
        self._spool_dir = Path(tempfile.mkdtemp(prefix="session-", dir=str(spool_root)))
        self._update_mode_label()
        self.overlay.show_centered_bottom()
        _write_audio_status(
            status="RUNNING",
            audio_state="STARTING",
            profile=profile.key,
            requested_mode=self.requested_mode,
            effective_mode=self.effective_mode,
            audio_usage=self.audio_usage,
            audio_engine_requested=self.engine_requested,
            audio_engine_effective=self.engine_effective,
            asr_model=runtime_asr_model,
            asr_device=runtime_asr_device,
            asr_compute_type=runtime_asr_compute,
            fallback_model=plan.fallback.model_size if plan.fallback else "",
            cpu_threads=active_spec.cpu_threads,
            realtime_profile=self.realtime_policy.profile,
            realtime_policy=self.realtime_policy.as_dict(),
            started_at=time.time(),
        )
        _append_audio_event("AUDIO_RUNTIME_STARTED", {
            "profile": profile.key,
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "audio_usage": self.audio_usage,
            "audio_engine_requested": self.engine_requested,
            "audio_engine_effective": self.engine_effective,
            "primary": plan.primary.as_dict(),
            "fallback": plan.fallback.as_dict() if plan.fallback else None,
            "processing": os.environ.get("ORT_AUDIO_PROCESSING", "vad"),
            "input_mode": os.environ.get("ORT_AUDIO_INPUT_MODE", "loopback"),
        })
        log(
            f"[AUDIO {APP_VERSION_TAG}] parent runtime start | usage={self.audio_usage} | "
            f"requested_engine={self.engine_requested} | effective_engine={self.engine_effective} | "
            f"requested_mode={self.requested_mode} | "
            f"effective_mode={self.effective_mode} | profile={profile.key} | "
            f"asr={runtime_asr_model}:{runtime_asr_device}:{runtime_asr_compute}"
        )
        if self.engine_effective == "azure":
            self.overlay.set_state("Menghubungkan Azure Live Media…")
            self.cloud.start(self._spool_dir)
            return
        if self.audio_usage == "live_media":
            self._start_local_realtime_pipeline()
            return
        self._start_local_pipeline()

    def _start_local_realtime_pipeline(self) -> None:
        if self._local_started:
            return
        self._local_started = True
        self.engine_effective = "local_live"
        self._update_mode_label()
        self.translator.start()
        self.overlay.set_state("Local Live · menyiapkan rolling partial ASR…")
        _write_audio_status(
            status="RUNNING",
            audio_state="LOCAL_REALTIME_STARTING",
            audio_engine_effective="local_live",
            local_realtime=True,
        )
        self.local_live.start()

    def _start_local_pipeline(self, replay_path: str = "") -> None:
        if self._local_started:
            return
        if self._spool_dir is None:
            raise RuntimeError("Spool Audio lokal belum tersedia.")
        self._local_started = True
        self.translator.start()
        self.asr.start()
        if replay_path:
            replay = Path(replay_path).expanduser().resolve()
            if replay.is_file():
                self.asr.submit({
                    "segment_id": f"cloud-replay-{int(time.time() * 1000)}",
                    "path": str(replay),
                    "kind": "npy",
                    "audio_seconds": 0.0,
                    "created_at": time.time(),
                })
        test_file = str(os.environ.get("ORT_AUDIO_TEST_FILE", "") or "").strip()
        if test_file and not replay_path:
            self.asr.submit({
                "segment_id": f"file-{int(time.time() * 1000)}",
                "path": str(Path(test_file).expanduser().resolve()),
                "kind": "file",
                "audio_seconds": 0.0,
                "created_at": time.time(),
            })
        elif not test_file:
            self.capture.start(self._spool_dir)

    def _handle_local_live_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        self._last_event = event
        if event_type in {"partial_transcript", "transcript", "quality_reject", "error", "metric"}:
            self._handle_asr_event(event)
            return
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            labels = {
                "MODEL_LOADING": "Local Live · memuat model ASR",
                "MODEL_READY": "Local Live · model siap",
                "LOCAL_REALTIME_READY": "Local Live · menunggu suara",
                "STREAMING": "Local Live · menerjemahkan selama dialog",
                "SPEECH_ACTIVE": "Local Live · memperbarui subtitle",
                "CUDA_PREFLIGHT": "Local Live · memeriksa CUDA sebelum streaming",
                "CUDA_PREFLIGHT_PASSED": "Local Live · CUDA siap",
                "HYBRID_FAILOVER": "GPU tidak siap · mempertahankan model di CPU",
                "JAPANESE_SPECIALIST_CPU_LOADING": "Japanese Specialist · berpindah ke CPU",
                "JAPANESE_SPECIALIST_CPU_ACTIVE": "Japanese Specialist · CPU aktif",
                "JAPANESE_SPECIALIST_CPU_FAILED": "Japanese Specialist CPU gagal · memakai multilingual fallback",
                "LANGUAGE_WATCHDOG_LOADING": "Language Watchdog · memuat detektor",
                "LANGUAGE_WATCHDOG_READY": "Language Watchdog · aktif",
                "LANGUAGE_MISMATCH_CONFIRMING": "Bahasa berbeda terdeteksi · mengonfirmasi",
                "TEMPORARY_CODE_SWITCH": "Bahasa asing sementara · sesi utama dipertahankan",
                "LANGUAGE_SWITCH_CONFIRMED": "Bahasa utama dikoreksi otomatis",
                "LANGUAGE_LOCKED": "Bahasa utama terdeteksi dan dikunci",
                "LANGUAGE_PROVISIONAL_LOCK": "Bahasa awal terdeteksi",
                "LANGUAGE_MODEL_SWITCHING": "Mengganti model sesuai bahasa",
                "STOPPED": "Local Live berhenti",
            }
            self.overlay.set_state(labels.get(state, state.replace("_", " ").title()))
            if state == "HYBRID_FAILOVER":
                self.effective_mode = "cpu_fallback"
                self._update_mode_label()
            _write_audio_status(
                status="RUNNING" if state != "STOPPED" else "STOP",
                audio_state=state,
                local_realtime=True,
                audio_engine_effective="local_live",
                asr_device=event.get("device", event.get("to_device", "")),
                asr_compute_type=event.get("compute_type", ""),
                asr_model=event.get("model", ""),
                first_partial_ms=event.get("first_partial_ms"),
                partial_interval_ms=event.get("partial_interval_ms"),
                endpoint_ms=event.get("endpoint_ms"),
                max_phrase_ms=event.get("max_phrase_ms"),
                language_correction=event.get("language_correction", os.environ.get("ORT_AUDIO_LANGUAGE_AUTOCORRECT", "balanced")),
                language_locked=event.get("language_locked", str(os.environ.get("ORT_AUDIO_LANGUAGE_LOCK", "0")).lower() in {"1", "true", "yes", "on"}),
                detected_language=event.get("detected_language", ""),
                specialist_active=state in {"JAPANESE_SPECIALIST_ACTIVE", "JAPANESE_SPECIALIST_CPU_ACTIVE"},
            )
            log(f"[AUDIO {APP_VERSION_TAG}] local_live_state={state} | {json.dumps(event, ensure_ascii=False)}")
            return
        if event_type == "meter":
            now = time.monotonic()
            if now - self._last_meter_at >= 0.5:
                _write_audio_status(
                    status="RUNNING",
                    audio_state="LOCAL_REALTIME_SPEECH" if event.get("speech_active") else "LOCAL_REALTIME_STREAMING",
                    audio_rms=event.get("rms", 0.0),
                    local_realtime=True,
                )
                self._last_meter_at = now
            return
        if event_type == "segment_complete":
            _append_audio_event("AUDIO_LOCAL_REALTIME_SEGMENT_COMPLETE", event)

    def _local_live_finished(self, code: int) -> None:
        if self._closing:
            return
        test_file = str(os.environ.get("ORT_AUDIO_TEST_FILE", "") or "").strip()
        if code == 0 and test_file:
            self.overlay.set_state("Uji Local Live selesai · tekan Stop")
            _write_audio_status(status="RUNNING", audio_state="LOCAL_REALTIME_FILE_COMPLETE")
            return
        message = f"Local Live berhenti dengan code {code}"
        self.overlay.set_error(message)
        _write_audio_status(status="ERROR", audio_state="LOCAL_REALTIME_STOPPED", last_error=message, local_realtime=True)
        log(f"[AUDIO {APP_VERSION_TAG}][ERROR] {message}")

    def _handle_cloud_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "").lower()
        self._last_event = event
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            labels = {
                "CONNECTING": "Menghubungkan Azure Live Media…",
                "CLOUD_CONNECTED": "Azure terhubung · menunggu audio",
                "STREAMING": "Azure Live Media · menerjemahkan langsung",
                "CLOUD_STOPPED": "Azure berhenti",
            }
            if state != "CLOUD_STOPPED" or not self._cloud_error_reason:
                self.overlay.set_state(labels.get(state, state.replace("_", " ").title()))
            _write_audio_status(
                status="RUNNING" if state != "CLOUD_STOPPED" else "STOP",
                audio_state=state,
                cloud_connected=bool(event.get("cloud_connected")),
                cloud_provider="azure",
                asr_model="azure_speech_translation",
                asr_device="cloud",
                asr_compute_type="streaming",
                translation_engine="azure_speech_translation",
                cloud_region=event.get("region", ""),
                cloud_source_locale=event.get("source_locale", ""),
                cloud_target_language=event.get("target_language", ""),
                device=event.get("device", ""),
                channels=event.get("channels"),
                sample_rate=event.get("sample_rate"),
                cloud_interim_count=event.get("interim_count"),
                cloud_final_count=event.get("final_count"),
                realtime_profile=event.get("realtime_profile", self.realtime_policy.profile),
                segmentation_silence_ms=event.get("segmentation_silence_ms"),
                segmentation_maximum_ms=event.get("segmentation_maximum_ms"),
                audio_chunk_ms=event.get("audio_chunk_ms"),
            )
            log(f"[AUDIO {APP_VERSION_TAG}] cloud_state={state} | connected={int(bool(event.get('cloud_connected')))}")
            return
        if event_type == "telemetry":
            metric = str(event.get("metric") or "cloud_metric")
            value = event.get("value")
            status_updates = {
                "status": "RUNNING",
                "audio_state": "CLOUD_STREAMING",
                "cloud_connected": True,
                "cloud_last_metric": metric,
                "cloud_last_metric_value": value,
            }
            if metric == "first_interim_ms":
                status_updates["cloud_first_interim_ms"] = value
            elif metric == "first_final_ms":
                status_updates["cloud_first_final_ms"] = value
            elif metric == "cloud_connect_ms":
                status_updates["cloud_connect_ms"] = value
            elif metric == "session_summary":
                status_updates["cloud_session_summary"] = event
            _write_audio_status(**status_updates)
            _append_audio_event("AUDIO_CLOUD_TELEMETRY", event)
            log(f"[AUDIO {APP_VERSION_TAG}] cloud_telemetry | metric={metric} | value={value}")
            return
        if event_type == "meter":
            now = time.monotonic()
            if now - self._last_meter_at >= 1.0:
                _write_audio_status(
                    status="RUNNING",
                    audio_state="CLOUD_STREAMING",
                    audio_rms=event.get("rms", 0.0),
                    cloud_connected=bool(event.get("cloud_connected")),
                )
                self._last_meter_at = now
            return
        if event_type in {"interim", "final"}:
            update = self.subtitle_stabilizer.accept(event)
            if update is None:
                return
            source = str(update.get("source") or "")
            translation = str(update.get("translation") or "")
            stable = bool(update.get("stable"))
            cloud_ms = int(update.get("cloud_ms", 0) or 0)
            if not translation and not stable:
                self.overlay.set_cloud_source(source, cloud_ms)
            else:
                self.overlay.set_cloud_translation(source, translation or source, stable, cloud_ms)
            state = "CLOUD_FINAL" if stable else "CLOUD_INTERIM"
            _write_audio_status(
                status="RUNNING",
                audio_state=state,
                cloud_connected=True,
                cloud_provider="azure",
                cloud_result_state="final" if stable else "interim",
                cloud_result_id=update.get("result_id", ""),
                cloud_display_sequence=update.get("display_sequence", 0),
                cloud_display_revision=update.get("display_revision", 0),
                cloud_ms=cloud_ms,
                last_transcript=source,
                last_translation=translation,
                audio_engine_effective="azure",
                displayed_at=time.time(),
            )
            _append_audio_event(
                "AUDIO_CLOUD_FINAL_DISPLAYED" if stable else "AUDIO_CLOUD_INTERIM_DISPLAYED",
                {
                    "result_id": update.get("result_id", ""),
                    "source": source,
                    "translation": translation,
                    "cloud_ms": cloud_ms,
                    "stable": stable,
                    "display_sequence": update.get("display_sequence", 0),
                    "display_revision": update.get("display_revision", 0),
                },
            )
            log(
                f"[AUDIO {APP_VERSION_TAG}] cloud_{'final' if stable else 'interim'} | "
                f"result={update.get('result_id', '-')} | cloud_ms={cloud_ms} | translation={translation}"
            )
            return
        if event_type == "drop":
            reason = str(event.get("reason") or "NO_MATCH")
            _write_audio_status(
                status="RUNNING",
                audio_state="CLOUD_STREAMING",
                last_cloud_drop=reason,
                cloud_drop_overlay_visible=False,
            )
            _append_audio_event("AUDIO_CLOUD_DROP", {**event, "overlay_visible": False})
            log(f"[AUDIO {APP_VERSION_TAG}] cloud_drop | reason={reason} | overlay_visible=0")
            return
        if event_type == "error":
            reason = str(event.get("code") or "AZURE_STREAM_FAILED")
            message = str(event.get("message") or "Koneksi Azure Speech terputus.")
            self._cloud_error_reason = reason
            self._cloud_replay_path = str(event.get("replay_path") or "")
            can_fallback = bool(
                self.engine_requested == "azure_fallback"
                and event.get("fallback_recommended", True)
                and os.environ.get("ORT_AUDIO_LOCAL_FALLBACK_READY", "0") == "1"
            )
            if can_fallback:
                self.overlay.set_state("Azure terputus · menyiapkan fallback lokal…")
            else:
                self.overlay.set_error(message)
            _write_audio_status(
                status="RUNNING" if can_fallback else "ERROR",
                audio_state="CLOUD_FAILOVER_PENDING" if can_fallback else "CLOUD_ERROR",
                cloud_connected=False,
                cloud_error_code=reason,
                last_error=message,
                cloud_replay_path=self._cloud_replay_path,
            )
            _append_audio_event("AUDIO_CLOUD_ERROR", event)
            log(f"[AUDIO {APP_VERSION_TAG}][CLOUD] {reason} | {message}")

    def _cloud_finished(self, code: int) -> None:
        if self._closing:
            return
        test_file = str(os.environ.get("ORT_AUDIO_TEST_FILE", "") or "").strip()
        if code == 0 and test_file and not self._cloud_error_reason:
            self.overlay.set_state("Uji Azure selesai · tekan Stop")
            _write_audio_status(status="RUNNING", audio_state="CLOUD_FILE_COMPLETE", cloud_connected=False)
            return
        reason = self._cloud_error_reason or f"AZURE_PROCESS_EXIT_{code}"
        if (
            self.engine_requested == "azure_fallback"
            and os.environ.get("ORT_AUDIO_LOCAL_FALLBACK_READY", "0") == "1"
            and not self._local_started
        ):
            decision = self.cloud_fallback.activate(reason, self._cloud_replay_path)
            if decision is not None:
                self.engine_effective = "local_live"
                self._update_mode_label()
                self.overlay.set_state("Fallback Local Live aktif · melanjutkan subtitle real-time")
                _write_audio_status(
                    status="RUNNING",
                    audio_state="CLOUD_LOCAL_FAILOVER",
                    cloud_connected=False,
                    audio_engine_effective="local_live",
                    cloud_failover_reason=reason,
                    cloud_replay_path=self._cloud_replay_path,
                )
                _append_audio_event("AUDIO_CLOUD_LOCAL_FAILOVER", decision)
                log(
                    f"[AUDIO {APP_VERSION_TAG}] CLOUD_LOCAL_FAILOVER | reason={reason} | "
                    f"replay={self._cloud_replay_path or '-'} | effective_engine=local_live"
                )
                try:
                    self._start_local_realtime_pipeline()
                except Exception as exc:
                    message = f"Fallback lokal gagal dimulai: {exc}"
                    self.overlay.set_error(message)
                    _write_audio_status(status="ERROR", audio_state="LOCAL_FALLBACK_ERROR", last_error=message)
            return
        message = f"Azure Live Media berhenti dengan code {code}"
        self.overlay.set_error(message)
        _write_audio_status(
            status="ERROR",
            audio_state="CLOUD_STOPPED",
            cloud_connected=False,
            cloud_process_exit_code=code,
            last_error=message,
        )

    def _handle_capture_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        self._last_event = event
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            if state == "LISTENING":
                self.overlay.set_state("Mendengarkan audio internal")
            _write_audio_status(
                status="RUNNING" if state != "CAPTURE_STOPPED" else "STOP",
                audio_state=state,
                device=event.get("device", ""),
                channels=event.get("channels"),
                sample_rate=event.get("sample_rate"),
            )
            log(f"[AUDIO {APP_VERSION_TAG}] capture_state={state} | {json.dumps(event, ensure_ascii=False)}")
        elif event_type == "meter":
            now = time.monotonic()
            if now - self._last_meter_at >= 1.0:
                _write_audio_status(
                    status="RUNNING",
                    audio_state="SPEECH" if event.get("speech_active") else "LISTENING",
                    audio_rms=event.get("rms", 0.0),
                    vad_threshold=event.get("threshold", 0.0),
                )
                self._last_meter_at = now
        elif event_type == "segment":
            self.asr.submit(event)
            _append_audio_event("AUDIO_SEGMENT_QUEUED", event)
        elif event_type == "error":
            message = str(event.get("message") or "Audio capture error")
            self.overlay.set_error(message)
            _write_audio_status(status="ERROR", audio_state="CAPTURE_ERROR", last_error=message)
            log(f"[AUDIO {APP_VERSION_TAG}][ERROR] {message}")

    def _handle_asr_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        self._last_event = event
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            device = str(event.get("device") or event.get("asr_device") or "cpu").upper()
            labels = {
                "MODEL_LOADING": f"Memuat model ASR · {device}",
                "MODEL_READY": "Model ASR siap · menunggu dialog",
                "TRANSCRIBING": f"Mengenali ucapan · {device}",
                "STOPPED": "ASR berhenti",
            }
            self.overlay.set_state(labels.get(state, state.replace("_", " ").title()))
            _write_audio_status(
                status="RUNNING" if state != "STOPPED" else "STOP",
                audio_state=state,
                asr_device=str(event.get("device") or ""),
                asr_compute_type=event.get("compute_type", ""),
                asr_model=event.get("model", ""),
            )
            log(f"[AUDIO {APP_VERSION_TAG}] asr_state={state} | {json.dumps(event, ensure_ascii=False)}")
        elif event_type in {"partial_transcript", "transcript"}:
            source = str(event.get("text") or "").strip()
            if not source:
                return
            is_partial = event_type == "partial_transcript" or not bool(event.get("stable", event_type == "transcript"))
            local_live = bool(event.get("local_realtime"))
            event = {**event, "local_realtime": local_live, "stable": not is_partial}
            generation = self.translator.submit(event)
            if local_live:
                self.overlay.set_cloud_source(source, int(event.get("asr_ms", 0) or 0))
                if event.get("specialist_correction"):
                    self.overlay.status_label.setText("Kotoba · koreksi final")
                elif event.get("provisional"):
                    self.overlay.status_label.setText("Local Live · preview cepat" if is_partial else "Local Live · final cepat")
                else:
                    self.overlay.status_label.setText("Local Live · parsial" if is_partial else "Local Live · final ASR")
            else:
                self.overlay.set_transcript(source)
            quality = event.get("quality") or {}
            _write_audio_status(
                status="RUNNING",
                audio_state="LOCAL_REALTIME_TRANSLATING" if local_live else "TRANSLATING",
                generation_id=generation,
                segment_id=event.get("segment_id", ""),
                last_transcript=source,
                detected_language=event.get("detected_language", ""),
                source_language=event.get("source_language", event.get("detected_language", "")),
                bridge_language=event.get("bridge_language", "en"),
                asr_task=event.get("asr_task", "transcribe"),
                japanese_specialist=bool(event.get("japanese_specialist")),
                language_probability=event.get("language_probability", 0.0),
                asr_ms=event.get("asr_ms", 0),
                asr_device=event.get("asr_device", ""),
                asr_compute_type=event.get("asr_compute_type", ""),
                asr_quality=quality,
                asr_quality_retry=bool(event.get("quality_retry")),
                local_realtime=local_live,
                result_stable=not is_partial,
                result_revision=event.get("revision", 0),
            )
            _append_audio_event("AUDIO_TRANSCRIPT_READY", {**event, "generation_id": generation})
            log(
                f"[AUDIO {APP_VERSION_TAG}] {'partial' if is_partial else 'transcript'} | generation={generation} | segment={event.get('segment_id')} | "
                f"asr={event.get('asr_device')}:{event.get('model')} | asr_ms={event.get('asr_ms')} | text={source}"
            )
        elif event_type == "quality_reject":
            reasons = ",".join(str(item) for item in (event.get("reasons") or [])) or "UNKNOWN"
            _write_audio_status(
                status="RUNNING",
                audio_state="LISTENING",
                last_quality_reject=reasons,
                last_quality_metrics=event.get("metrics") or {},
                repetition_guard_triggered=any(str(item).startswith("REPEAT") or str(item) in {"LOW_LEXICAL_DIVERSITY", "OUTPUT_AUDIO_RATIO", "BRIDGE_NOT_ENGLISH"} for item in (event.get("reasons") or [])),
                rejected_segment_id=event.get("segment_id", ""),
                quality_reject_overlay_visible=False,
            )
            _append_audio_event("AUDIO_ASR_QUALITY_REJECTED", {**event, "overlay_visible": False})
            log(
                f"[AUDIO {APP_VERSION_TAG}] quality_reject | segment={event.get('segment_id')} | "
                f"reasons={reasons} | overlay_visible=0"
            )
        elif event_type == "error":
            message = str(event.get("message") or "ASR error")
            recovering = bool(event.get("fatal") and self.requested_mode == "hybrid" and self.effective_mode in {"hybrid", "gpu"})
            if recovering:
                self.overlay.set_state("Memulihkan ASR melalui CPU…")
                _write_audio_status(status="RUNNING", audio_state="ASR_RECOVERING", last_error=message, error_code=event.get("code", ""))
            else:
                self.overlay.set_error(message)
                _write_audio_status(status="ERROR", audio_state="ASR_ERROR", last_error=message, error_code=event.get("code", ""))
            _append_audio_event("AUDIO_ASR_ERROR", event)
            log(f"[AUDIO {APP_VERSION_TAG}][ASR] {event.get('code', 'ERROR')} | {message}")
        elif event_type == "metric":
            _write_audio_status(last_metric=event)

    def _handle_asr_runtime_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "ASR_PROCESS_STARTED":
            self.effective_mode = str(event.get("effective_mode") or self.effective_mode)
            self._update_mode_label()
            _write_audio_status(
                asr_process_state="STARTING",
                requested_mode=self.requested_mode,
                effective_mode=self.effective_mode,
                asr_device=event.get("worker_device", ""),
                asr_model=event.get("model", ""),
                asr_compute_type=event.get("compute_type", ""),
            )
        elif event_type == "HYBRID_FAILOVER":
            self.effective_mode = str(event.get("effective_mode") or "cpu_fallback")
            self._update_mode_label()
            self.overlay.set_state("Hybrid failover · memuat CPU replay")
            _write_audio_status(
                status="RUNNING",
                audio_state="HYBRID_FAILOVER",
                effective_mode=self.effective_mode,
                failover_reason=event.get("reason", ""),
                replay_segment_id=event.get("replay_segment_id", ""),
                gpu_failure_count=event.get("gpu_failures", 0),
                gpu_circuit_open=bool(event.get("circuit_open")),
            )
        elif event_type == "HYBRID_GPU_RETRY":
            self.effective_mode = "hybrid"
            self._update_mode_label()
            self.overlay.set_state("Replay CPU selesai · mencoba GPU kembali")
            _write_audio_status(
                status="RUNNING",
                audio_state="GPU_RETRY",
                effective_mode=self.effective_mode,
                gpu_failure_count=event.get("gpu_failures", 0),
                gpu_circuit_open=False,
            )
        elif event_type == "ASR_PROCESS_EXIT":
            _write_audio_status(
                asr_process_state="RECOVERING" if self.requested_mode == "hybrid" and (event.get("worker_device") == "cuda" or event.get("planned_switch")) else "STOPPED",
                asr_process_exit_code=event.get("exit_code"),
                asr_process_exit_label=event.get("exit_label", ""),
                replay_segment_id=event.get("replay_segment_id", ""),
            )
        elif event_type == "ASR_FILE_COMPLETE":
            self.overlay.set_state("Uji file selesai · tekan Stop")
            _write_audio_status(status="RUNNING", audio_state="FILE_COMPLETE")
        _append_audio_event(event_type or "AUDIO_ASR_RUNTIME_EVENT", event)

    def _handle_translation_runtime_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "state":
            state = str(event.get("state") or "").upper()
            _write_audio_status(
                translation_process_state=state,
                translation_process_mode="safe_argos" if event.get("safe_mode") else "isolated_ct2",
                translation_restart_count=self.translator.restart_count,
            )
            if state in {"TRANSLATOR_LOADING", "TRANSLATOR_READY"}:
                log(
                    f"[AUDIO {APP_VERSION_TAG}] translation_state={state} | "
                    f"mode={'safe_argos' if event.get('safe_mode') else 'isolated_ct2'} | "
                    f"engine={event.get('engine', '-')}"
                )
        elif event_type == "TRANSLATION_PROCESS_EXIT":
            _write_audio_status(
                translation_process_state="RECOVERING" if event.get("restart") else "STOPPED",
                translation_process_exit_code=event.get("exit_code"),
                translation_process_exit_label=event.get("exit_label", ""),
                translation_native_access_violation=bool(event.get("native_access_violation")),
                translation_process_mode="safe_argos" if event.get("safe_mode") else "isolated_ct2",
                translation_restart_count=event.get("restart_count", 0),
            )
        elif event_type == "TRANSLATION_PROCESS_STARTED":
            _write_audio_status(
                translation_process_state="STARTING",
                translation_process_mode="safe_argos" if event.get("safe_mode") else "isolated_ct2",
                translation_restart_count=event.get("restart_count", 0),
            )
        _append_audio_event(event_type or "AUDIO_TRANSLATION_RUNTIME_EVENT", event)

    def _translation_ready(self, payload: dict) -> None:
        source = str(payload.get("text") or "")
        translated = str(payload.get("translation") or source)
        engine = str(payload.get("translation_engine") or "unknown")
        status = f"{engine} · {int(payload.get('total_ms', 0) or 0)} ms"
        if payload.get("translation_error"):
            status = "ASR siap · backend terjemahan fallback"
        elif payload.get("translation_safe_mode"):
            status = f"{engine} · mode aman · {int(payload.get('total_ms', 0) or 0)} ms"
        local_live = bool(payload.get("local_realtime"))
        stable = bool(payload.get("stable", True))
        if local_live:
            self.overlay.set_cloud_translation(source, translated, stable, int(payload.get("total_ms", 0) or 0))
            if payload.get("specialist_correction"):
                label = "Kotoba · koreksi final"
            elif payload.get("provisional"):
                label = "Local Live · preview cepat" if not stable else "Local Live · final cepat"
            else:
                label = f"Local Live · {'final' if stable else 'live'}"
            self.overlay.status_label.setText(
                f"{label} · {int(payload.get('total_ms', 0) or 0)} ms"
            )
        else:
            self.overlay.set_translation(source, translated, status)
        _write_audio_status(
            status="RUNNING",
            audio_state=("LOCAL_REALTIME_FINAL" if stable else "LOCAL_REALTIME_INTERIM") if local_live else "DISPLAYED",
            generation_id=payload.get("generation_id"),
            last_transcript=source,
            last_translation=translated,
            translation_engine=engine,
            cache=payload.get("cache", "MISS"),
            asr_ms=int(payload.get("asr_ms", 0) or 0),
            translation_ms=int(payload.get("translation_ms", 0) or 0),
            total_ms=int(payload.get("total_ms", 0) or 0),
            translation_process_mode="safe_argos" if payload.get("translation_safe_mode") else "isolated_ct2",
            translation_restart_count=self.translator.restart_count,
            requested_mode=self.requested_mode,
            effective_mode=self.effective_mode,
            audio_usage=self.audio_usage,
            audio_engine_requested=self.engine_requested,
            audio_engine_effective=self.engine_effective,
            asr_device=payload.get("asr_device", ""),
            asr_quality=payload.get("quality") or {},
            displayed_at=time.time(),
            local_realtime=local_live,
            result_stable=stable,
            result_revision=payload.get("revision", 0),
            requested_language=payload.get("requested_language", os.environ.get("ORT_AUDIO_LANGUAGE_REQUESTED", "auto")),
            detected_language=payload.get("detected_language", ""),
            source_language=payload.get("source_language", payload.get("detected_language", "")),
            bridge_language=payload.get("bridge_language", "en"),
            asr_task=payload.get("asr_task", "transcribe"),
            japanese_specialist=bool(payload.get("japanese_specialist")),
        )
        _append_audio_event("AUDIO_TRANSLATION_DISPLAYED", {
            "generation_id": payload.get("generation_id"),
            "source": source,
            "translation": translated,
            "engine": engine,
            "cache": payload.get("cache", "MISS"),
            "asr_ms": payload.get("asr_ms", 0),
            "translation_ms": payload.get("translation_ms", 0),
            "total_ms": payload.get("total_ms", 0),
            "translation_safe_mode": bool(payload.get("translation_safe_mode")),
            "translation_restart_count": self.translator.restart_count,
            "segment_id": payload.get("segment_id", ""),
            "asr_device": payload.get("asr_device", ""),
            "quality": payload.get("quality") or {},
            "local_realtime": local_live,
            "stable": stable,
            "revision": payload.get("revision", 0),
        })
        log(
            f"[AUDIO {APP_VERSION_TAG}] displayed | generation={payload.get('generation_id')} | engine={engine} | "
            f"source_lang={payload.get('source_language') or payload.get('detected_language') or '-'} | "
            f"bridge={payload.get('bridge_language', 'en')} | task={payload.get('asr_task', '-')} | "
            f"total_ms={payload.get('total_ms')} | translation={translated}"
        )

    def _capture_finished(self, code: int) -> None:
        if self._closing:
            return
        message = f"Audio capture berhenti dengan code {code}"
        self.overlay.set_error(message)
        _write_audio_status(status="ERROR", audio_state="CAPTURE_STOPPED", capture_exit_code=code, last_error=message)
        log(f"[AUDIO {APP_VERSION_TAG}][ERROR] {message}")

    def _check_stop_request(self) -> None:
        path_text = str(os.environ.get("ORT_STOP_REQUEST_FILE", "") or "").strip()
        if path_text and Path(path_text).exists():
            self.shutdown()

    def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.app.quit()

    def _cleanup(self) -> None:
        if not self._closing:
            self._closing = True
        self.stop_timer.stop()
        self.cloud.stop()
        self.local_live.stop()
        self.capture.stop()
        self.asr.stop()
        self.translator.stop()
        if self._spool_dir is not None:
            try:
                shutil.rmtree(self._spool_dir)
            except Exception:
                pass
        _write_audio_status(status="STOP", audio_state="STOPPED", stopped_at=time.time())
        _append_audio_event("AUDIO_RUNTIME_STOPPED", {"reason": "shutdown"})
        log(f"[AUDIO {APP_VERSION_TAG}] shutdown complete")


def main() -> int:
    app = QApplication(sys.argv)
    controller = AudioApplication(app)

    def request_shutdown(*_args: Any) -> None:
        QTimer.singleShot(0, controller.shutdown)

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, request_shutdown)
            except Exception:
                pass
    try:
        controller.start()
    except Exception as exc:
        message = str(exc)
        log(f"[AUDIO {APP_VERSION_TAG}][FATAL] {message}")
        _write_audio_status(status="ERROR", audio_state="BOOT_ERROR", last_error=message)
        controller.overlay.set_error(message)
        controller.overlay.show_centered_bottom()
    return int(app.exec_())


if __name__ == "__main__":
    raise SystemExit(main())
