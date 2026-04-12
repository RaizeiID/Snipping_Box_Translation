import json
import os

# ==============================================================================
#   TITAN X - CHARACTER ARC CORE v1.0
#   Divisi: CONTEXT & NARRATIVE
#   Tugas: Melacak Perkembangan Karakter (Dinamis)
# ==============================================================================

class CharacterArcCore:
    def __init__(self):
        print("[ARC] Initializing Character Profiler...")
        self.db_file = "character_arcs.json"
        self.database = {}
        self._load_db(force=True)

    def _load_db(self, force=False):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    self.database = json.load(f).get("characters", {})
            except: pass

    def get_status(self, name):
        """Mengambil status hubungan karakter (Friendly/Hostile)"""
        self._load_db()
        if name in self.database:
            return self.database[name]
        return {"alignment": "Neutral", "trust_level": 50} # Default

    def update_arc(self, name, new_alignment):
        """Update status jika plot twist terjadi (Belum otomatis, manual trigger)"""
        if name not in self.database:
            self.database[name] = {"alignment": "Neutral", "trust_level": 50}
            
        self.database[name]["alignment"] = new_alignment
        # Simpan ke file (Logic save sederhana)
        # (Nanti diintegrasikan dengan LearningEngine untuk auto-save)