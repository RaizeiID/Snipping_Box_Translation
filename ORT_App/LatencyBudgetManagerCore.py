import json
import os
import time

# ==============================================================================
#   TITAN X - LATENCY BUDGET MANAGER CORE v1.0
#   Divisi: OPTIMIZATION & PERFORMANCE
#   Tugas: Memantau Waktu Eksekusi per Frame
# ==============================================================================

class LatencyBudgetManagerCore:
    def __init__(self):
        print("[BUDGET] Initializing Time Accountant...")
        self.config_file = "latency_budget.json"
        self.frame_start = 0
        self.budget_ms = 16.6
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.budget_ms = data.get("max_frame_time_ms", 16.6)
            except: pass

    def start_frame(self):
        """Panggil ini di awal setiap loop"""
        self.frame_start = time.time() * 1000 # convert to ms

    def get_remaining_budget(self):
        """Berapa milidetik tersisa sebelum frame drop?"""
        now = time.time() * 1000
        elapsed = now - self.frame_start
        remaining = self.budget_ms - elapsed
        return max(0, remaining)

    def is_over_budget(self):
        return self.get_remaining_budget() <= 0