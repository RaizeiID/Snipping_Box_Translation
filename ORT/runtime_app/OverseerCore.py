import json
import os
import time

# ==============================================================================
#   TITAN X - OVERSEER CORE v1.0
#   Divisi: SECURITY & INTEGRITY
#   Tugas: Memantau Kesehatan Sistem & Self-Repair Trigger
# ==============================================================================

class OverseerCore:
    def __init__(self):
        print("[OVERSEER] Initializing System Health Monitor...")
        self.config_file = "overseer_rules.json"
        self.error_counts = {}
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def report_issue(self, core_name):
        """
        Dipanggil oleh Nexus jika ada Core yang error/crash.
        """
        self._load_config()
        self.error_counts[core_name] = self.error_counts.get(core_name, 0) + 1
        
        threshold = self.config.get("max_errors_before_restart", 3)
        current_errors = self.error_counts[core_name]
        
        print(f"[OVERSEER] ⚠️ Warning: {core_name} failed ({current_errors}/{threshold})")

        if current_errors >= threshold:
            return self._trigger_protocol(core_name)
        
        return "MONITORING"

    def _trigger_protocol(self, core_name):
        """
        Menentukan tindakan perbaikan.
        """
        # Jika core kritis (Mesin/Mata) mati, kita butuh tindakan drastis
        if core_name in self.config.get("critical_cores", []):
            print(f"[OVERSEER] 🚨 CRITICAL FAILURE in {core_name}. Initiating Failover Protocol.")
            self.error_counts[core_name] = 0 # Reset counter
            return "ACTIVATE_FAILOVER"
        
        # Jika core biasa (misal Tone/Syntax), matikan saja sementara
        print(f"[OVERSEER] {core_name} unstable. Disabling temporarily.")
        return "DISABLE_CORE"

    def reset_status(self, core_name):
        """Jika Core berhasil jalan, reset error count"""
        if core_name in self.error_counts:
            self.error_counts[core_name] = 0