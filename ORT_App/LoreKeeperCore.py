import json
import os
import re

# ==============================================================================
#   TITAN X - LORE KEEPER CORE v1.0
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Menjaga Konsistensi Istilah Khusus Game (Hard Constraints)
# ==============================================================================

class LoreKeeperCore:
    def __init__(self):
        print("[LORE] Initializing Terminology Database...")
        self.db_file = "lore_dictionary.json"
        self.last_load = 0
        self.dictionary = {}
        self._load_db(force=True)

    def _load_db(self, force=False):
        if not os.path.exists(self.db_file): return
        try:
            mtime = os.path.getmtime(self.db_file)
            if not force and mtime <= self.last_load: return
            with open(self.db_file, 'r') as f:
                self.dictionary = json.load(f).get("hard_constraints", {})
            self.last_load = mtime
        except: pass

    def enforce_lore(self, text):
        """
        Memaksa teks mematuhi kamus Lore.
        Biasanya dijalankan SETELAH translasi untuk memperbaiki istilah yang 'terlanjur' diterjemahkan,
        atau SEBELUM translasi untuk mengunci kata.
        """
        self._load_db()
        if not text: return ""

        # Sederhana: Find & Replace
        # (Nanti bisa diupgrade jadi Token Matching biar lebih pinter)
        for term_en, term_id in self.dictionary.items():
            # Regex \b agar hanya mengganti kata utuh
            pattern = re.compile(r'\b' + re.escape(term_en) + r'\b', re.IGNORECASE)
            text = pattern.sub(term_id, text)
            
        return text