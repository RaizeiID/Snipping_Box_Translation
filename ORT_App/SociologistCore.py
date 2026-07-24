import json
import os

# ==============================================================================
#   TITAN X - SOCIOLOGIST CORE v1.0
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Menganalisis Nada Bicara (Tone) & Tingkat Kesopanan
#   Sifat: Adaptif berdasarkan JSON
# ==============================================================================

class SociologistCore:
    def __init__(self):
        print("[SOCIOLOGIST] Initializing Social Analysis Unit...")
        self.rules_file = "sociology_rules.json"
        self.last_load = 0
        self.rules = {}
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        if not os.path.exists(self.rules_file): return
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            with open(self.rules_file, 'r') as f:
                self.rules = json.load(f)
            self.last_load = mtime
        except: pass

    def profile(self, speaker_name, text_content=""):
        """
        Menganalisis profil sosial untuk menentukan "Context Tags"
        Output: ['Formal', 'Military'] atau ['Aggressive', 'Casual']
        """
        self._load_rules()
        tags = []
        
        # 1. Analisis Berdasarkan Kata Kunci (Tone Triggers)
        text_lower = text_content.lower()
        triggers = self.rules.get("tone_triggers", {})
        
        for tone, keywords in triggers.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    tags.append(tone.capitalize())
                    break # Cukup satu keyword per kategori
        
        # 2. Analisis Berdasarkan Speaker (Bisa dikembangkan nanti dg IdentityCore)
        # Misal: Jika speaker == "Commander", otomatis Formal.
        if "Commander" in str(speaker_name):
            tags.append("Formal")
            
        # Default jika tidak ada trigger
        if not tags:
            tags.append("Casual")
            
        return list(set(tags)) # Hapus duplikat