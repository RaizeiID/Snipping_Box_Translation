import json
import os
import re

# ==============================================================================
#   TITAN X - STYLE GUIDE CORE v1.0
#   Divisi: ACADEMY (STYLE)
#   Tugas: Memperbaiki Format & Tanda Baca (Polishing)
# ==============================================================================

class StyleGuideCore:
    def __init__(self):
        print("[STYLE] Initializing Formatting Rules...")
        self.config_file = "style_rules.json"
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def format(self, text):
        """Mempercantik teks sesuai aturan EYD"""
        if not text: return ""
        self._load_config()
        
        # 1. Hapus Spasi Ganda
        if self.config.get("remove_double_spaces", True):
            text = re.sub(r'\s+', ' ', text)
            
        # 2. Perbaiki Spasi Tanda Baca (misal "Halo , dunia" -> "Halo, dunia")
        if self.config.get("fix_punctuation_spacing", True):
            text = re.sub(r'\s+([.,?!:;])', r'\1', text)
            
        # 3. Auto Capitalize Awal Kalimat
        if self.config.get("auto_capitalize", True) and len(text) > 0:
            text = text[0].upper() + text[1:]
            
        return text.strip()