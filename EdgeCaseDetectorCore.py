import json
import os

# ==============================================================================
#   TITAN X - EDGE CASE DETECTOR CORE v1.0
#   Divisi: SURVEILLANCE & CRISIS MGMT
#   Tugas: Mendeteksi Anomali Loop & Spam
# ==============================================================================

class EdgeCaseDetectorCore:
    def __init__(self):
        print("[EDGE] Initializing Anomaly Detector...")
        self.config_file = "edge_patterns.json"
        self.history_buffer = [] # Menyimpan 10 teks terakhir
        self.max_history = 10
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def is_safe(self, text):
        """
        Cek apakah teks ini aman atau anomali (looping)?
        """
        if not text: return True
        self._load_config()
        
        # 1. Cek Repetisi (Infinite Loop Protection)
        # Jika teks ini sama persis dengan 5 teks sebelumnya berturut-turut
        limit = self.config.get("repetition_threshold", 5)
        recent = self.history_buffer[-limit:]
        
        if len(recent) >= limit and all(x == text for x in recent):
            # print(f"[EDGE] ⚠️ Infinite Loop Detected! Ignoring: '{text[:10]}...'")
            return False # ANOMALI

        # Update Buffer
        self.history_buffer.append(text)
        if len(self.history_buffer) > self.max_history:
            self.history_buffer.pop(0)

        # 2. Cek Rasio Simbol (Anti-Gibberish)
        # Jika isinya "!@#$%^&*" doang
        non_alnum = sum(1 for char in text if not char.isalnum() and not char.isspace())
        ratio = non_alnum / len(text)
        if ratio > self.config.get("suspicious_chars_ratio", 0.8):
            return False

        return True