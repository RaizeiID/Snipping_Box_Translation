import json
import os
import time

# ==============================================================================
#   TITAN X - CONSISTENCY AUDITOR CORE v1.0
#   Divisi: QA & INTEGRITY
#   Tugas: Memeriksa Kesehatan File Database JSON
# ==============================================================================

class ConsistencyAuditorCore:
    def __init__(self):
        print("[AUDITOR] Initializing Database Inspector...")
        self.config_file = "audit_rules.json"
        self.last_check = time.time()
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def perform_audit(self):
        """Cek apakah file JSON valid (tidak corrupt syntax error)"""
        now = time.time()
        interval = self.config.get("check_interval_seconds", 300)
        
        if now - self.last_check < interval:
            return # Belum waktunya cek

        self.last_check = now
        targets = self.config.get("files_to_audit", [])
        
        for filename in targets:
            if os.path.exists(filename):
                try:
                    with open(filename, 'r') as f:
                        json.load(f) # Coba baca
                    # print(f"[AUDITOR] {filename} is HEALTHY.")
                except json.JSONDecodeError:
                    print(f"[AUDITOR] ⚠️ CORRUPTION DETECTED in {filename}!")
                    # Di sini bisa tambahkan logika restore backup