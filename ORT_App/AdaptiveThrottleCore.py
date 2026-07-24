import json
import os
import time

# ==============================================================================
#   TITAN X - ADAPTIVE THROTTLE CORE v1.0
#   Divisi: PERFORMANCE & OPTIMIZATION
#   Tugas: Mengatur Kecepatan Eksekusi (Dynamic FPS)
# ==============================================================================

class AdaptiveThrottleCore:
    def __init__(self):
        print("[THROTTLE] Initializing Dynamic Speed Control...")
        self.config_file = "throttle_config.json"
        self.policy = {}
        self.current_mode = "NORMAL"
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.policy = json.load(f).get("modes", {})
            except: pass

    def recommend_action(self, system_status):
        """
        Menerima status dari Sentinel (NORMAL/WARNING/CRITICAL)
        Mengembalikan rekomendasi delay & fitur yang harus dimatikan.
        """
        self._load_config()
        self.current_mode = system_status
        
        rule = self.policy.get(system_status, self.policy.get("NORMAL"))
        
        return {
            "sleep": rule.get("sleep_interval", 0.1),
            "skip": rule.get("skip_frames", 0),
            "disabled_cores": rule.get("disable_components", [])
        }