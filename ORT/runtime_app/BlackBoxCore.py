import json
import os
import time
import traceback

# ==============================================================================
#   TITAN X - BLACK BOX CORE v1.0
#   Divisi: SECURITY & REPORTING
#   Tugas: Perekam Kejadian Kritis (Flight Recorder)
# ==============================================================================

class BlackBoxCore:
    def __init__(self):
        print("[BLACKBOX] Initializing Flight Recorder...")
        self.config_file = "logging_config.json"
        self.log_file = "titan_flight_record.log"
        self._load_config()

    def _load_config(self):
        self.config = {
            "log_level": "ERROR",
            "enable_console_output": True
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def log_event(self, source, event_type, details):
        """
        Mencatat kejadian penting.
        Input: source="Helsinki", event_type="CRASH", details="Error info..."
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        # Format Log Standar Militer
        log_entry = f"[{timestamp}] [{source.upper()}] [{event_type}] {details}\n"
        
        # 1. Tulis ke Console (Jika diizinkan)
        if self.config.get("enable_console_output", True):
            print(f"[REC] {source}: {event_type} - {details[:50]}...")

        # 2. Tulis ke File (Append Mode)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass # Jangan crash jika gagal nulis log

    def read_last_errors(self, limit=5):
        """
        Dibaca oleh Overseer atau LearningEngine untuk diagnosa.
        """
        if not os.path.exists(self.log_file): return []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return lines[-limit:]
        except: return []