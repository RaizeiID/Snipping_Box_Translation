import json
import os
import time

# ==============================================================================
#   TITAN X - DYNAMIC BATCHING CORE v1.0
#   Divisi: OPTIMIZATION & ENGINE
#   Tugas: Menggabungkan Request Kecil Menjadi Satu Paket Besar
# ==============================================================================

class DynamicBatchingCore:
    def __init__(self):
        print("[BATCH] Initializing Request Aggregator...")
        self.config_file = "batch_config.json"
        self.queue = []
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def pack(self, text_list):
        """
        Input: ["Halo", "Apa kabar", "Pilihan A"]
        Output: "Halo <sep> Apa kabar <sep> Pilihan A"
        (Format ini nanti dipecah lagi setelah translate)
        """
        # Di v1.0 kita return raw list dulu agar kompatibel dengan HelsinkiCore v1.7
        # Helsinki v1.7 mendukung list input secara native
        return text_list