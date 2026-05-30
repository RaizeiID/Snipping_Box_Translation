import json
import os

# ==============================================================================
#   TITAN X - SMART CACHE ROUTER v1.0
#   Divisi: PERFORMANCE & OPTIMIZATION
#   Tugas: Routing Keputusan (Cache Hit vs Cache Miss)
#   Efek: Menurunkan Latensi drastis untuk teks berulang
# ==============================================================================

class SmartCacheRouterCore:
    def __init__(self):
        print("[CACHE] Initializing High-Speed Routing Protocol...")
        self.policy_file = "cache_policy.json"
        self.policy = {
            "min_length_to_cache": 3,
            "max_length_to_cache": 200
        }
        self._load_policy()

    def _load_policy(self):
        if os.path.exists(self.policy_file):
            try:
                with open(self.policy_file, 'r') as f:
                    self.policy = json.load(f)
            except: pass

    def check_cache_eligibility(self, text):
        """
        Apakah teks ini LAYAK disimpan di cache?
        (Jangan cache angka acak atau teks terlalu panjang)
        """
        if not text: return False
        
        length = len(text)
        if length < self.policy.get("min_length_to_cache", 3): return False
        if length > self.policy.get("max_length_to_cache", 200): return False
        
        # Jangan cache jika isinya cuma angka (misal "12345")
        if text.isdigit() and self.policy.get("ignore_numbers_only", True):
            return False
            
        return True