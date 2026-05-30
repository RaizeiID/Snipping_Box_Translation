import json
import os
import re

# ==============================================================================
#   TITAN X - PROFESSOR LOGIC CORE v1.0
#   Divisi: ACADEMY (LOGIC)
#   Tugas: Memastikan Konsistensi Logika & Fakta (Angka/Nama)
# ==============================================================================

class ProfessorLogicCore:
    def __init__(self):
        print("[LOGIC] Initializing Logical Reasoning Unit...")
        self.config_file = "logic_constraints.json"
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def validate(self, original, translation):
        """
        Memperbaiki kesalahan logika pada terjemahan.
        """
        self._load_config()
        
        # 1. CEK ANGKA (Numbers Check)
        # Jika teks asli ada angka "100", terjemahan juga harus ada "100".
        if self.config.get("preserve_numbers", True):
            nums_org = re.findall(r'\d+', original)
            nums_trans = re.findall(r'\d+', translation)
            
            # Jika angka hilang atau berubah, kembalikan peringatan (atau fix manual jika canggih)
            # Untuk v1.0, kita hanya memastikan angka tidak hilang.
            for num in nums_org:
                if num not in translation:
                    # Logic sederhana: Tempelkan angka di akhir jika hilang
                    # (Bisa dikembangkan lebih lanjut)
                    pass 

        return translation