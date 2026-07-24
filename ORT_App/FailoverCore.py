import json
import os

# ==============================================================================
#   TITAN X - FAILOVER CORE v1.0
#   Divisi: CRISIS MANAGEMENT
#   Tugas: Mesin Cadangan (Emergency Backup)
#   Status: Standby (Hanya aktif jika Helsinki mati)
# ==============================================================================

class FailoverCore:
    def __init__(self):
        print("[FAILOVER] Backup Systems Standing By...")
        self.config_file = "backup_model_config.json"
        self.dictionary = {}
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.dictionary = data.get("emergency_dictionary", {})
            except: pass

    def translate_emergency(self, text):
        """
        Terjemahan kasar kata-per-kata saat darurat.
        """
        if not text: return "[SYSTEM ERROR]"
        
        # Cek Kamus Darurat dulu
        for en, id_ in self.dictionary.items():
            if en.lower() == text.lower():
                return f"[BACKUP] {id_}"
        
        # Jika tidak ada di kamus, kembalikan teks asli dengan tanda bahaya
        return f"⚠️ {text}"