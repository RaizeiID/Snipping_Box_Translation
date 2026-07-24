import json
import os
import time

# ==============================================================================
#   TITAN X - FALLBACK STRATEGY CORE v1.0
#   Divisi: DISPLAY & CRISIS MANAGEMENT
#   Tugas: Menangani Kegagalan Tampilan Utama (UI Crash)
# ==============================================================================

class FallbackStrategyCore:
    def __init__(self):
        print("[FALLBACK] Initializing Emergency Display Protocol...")
        self.config_file = "display_fallback.json"
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def execute(self, text):
        """
        Dipanggil jika Formatter utama gagal/crash.
        """
        self._load_config()
        
        # 1. Print ke Console (Minimal User bisa baca di terminal)
        if self.config.get("enable_console_print", True):
            print(f"\n[FALLBACK DISPLAY] >> {text}\n")
            
        # 2. Log ke File Darurat
        if self.config.get("log_to_file", True):
            try:
                with open("emergency_subtitles.txt", "a", encoding="utf-8") as f:
                    timestamp = time.strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] {text}\n")
            except: pass