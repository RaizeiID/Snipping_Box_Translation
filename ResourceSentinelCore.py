import json
import os
import time

# Coba import psutil untuk monitoring hardware
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[SENTINEL] WARNING: 'psutil' library not found. Hardware monitoring disabled.")

# ==============================================================================
#   TITAN X - RESOURCE SENTINEL CORE v1.0
#   Divisi: PERFORMANCE & OPTIMIZATION
#   Tugas: Memantau Kesehatan Hardware (CPU/RAM)
# ==============================================================================

class ResourceSentinelCore:
    def __init__(self):
        print("[SENTINEL] Initializing Hardware Monitor...")
        self.config_file = "resource_thresholds.json"
        self.config = {
            "cpu_warning_percent": 80.0,
            "cpu_critical_percent": 95.0
        }
        self.last_check = 0
        self.current_status = "NORMAL" # NORMAL, WARNING, CRITICAL
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def check_vital_signs(self):
        """
        Mengembalikan status kesehatan PC saat ini.
        Dipanggil oleh AdaptiveThrottle.
        """
        if not PSUTIL_AVAILABLE:
            return "NORMAL" # Asumsikan sehat jika tidak bisa cek

        # Rate Limiting (Jangan cek terlalu sering agar hemat CPU)
        now = time.time()
        interval = self.config.get("check_interval_seconds", 2.0)
        if now - self.last_check < interval:
            return self.current_status

        self.last_check = now
        self._load_config() # Auto-reload config

        # 1. Cek CPU
        cpu_usage = psutil.cpu_percent(interval=None)
        
        # 2. Cek RAM
        ram_usage = psutil.virtual_memory().percent

        # 3. Tentukan Status
        cpu_warn = self.config.get("cpu_warning_percent", 80)
        cpu_crit = self.config.get("cpu_critical_percent", 95)
        
        if cpu_usage > cpu_crit or ram_usage > 95:
            self.current_status = "CRITICAL"
            # print(f"[SENTINEL] ⚠️ CRITICAL LOAD: CPU {cpu_usage}% / RAM {ram_usage}%")
        elif cpu_usage > cpu_warn or ram_usage > 85:
            self.current_status = "WARNING"
        else:
            self.current_status = "NORMAL"
            
        return self.current_status