import json
import os

# ==============================================================================
#   TITAN X - NARRATIVE CORE v1.0
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Membedakan Dialog (Percakapan) vs Monolog (Narasi)
# ==============================================================================

class NarrativeCore:
    def __init__(self):
        print("[NARRATIVE] Initializing Story Structure Analysis...")
        self.rules_file = "narrative_patterns.json"
        self.last_load = 0
        self.patterns = {}
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        if not os.path.exists(self.rules_file): return
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            with open(self.rules_file, 'r') as f:
                self.patterns = json.load(f)
            self.last_load = mtime
        except: pass

    def analyze(self, text):
        """
        Menentukan apakah teks ini Dialog atau Narasi.
        Return: (Speaker_Name_Guess, Clean_Text)
        """
        self._load_rules()
        
        # Cek Indikator Dialog (Tanda kutip, kata ganti orang)
        is_dialog = False
        for ind in self.patterns.get("dialog_indicators", []):
            if ind in text:
                is_dialog = True
                break
        
        if is_dialog:
            # Jika dialog tapi tidak ada nama (Identity gagal), 
            # kita kembalikan "Unknown" sebagai speaker sementara
            return "Unknown", text
        else:
            # Jika narasi, speakernya None
            return None, text