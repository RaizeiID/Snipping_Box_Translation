import json
import os
import difflib # <-- INI YANG BENAR (SEBELUMNYA difflibit)

# ==============================================================================
#   TITAN X - DUPLICATE SUBTITLE SUPPRESSOR CORE v1.1 (FIXED)
#   Divisi: INPUT & OPTIMIZATION
#   Tugas: Mencegah Terjemahan Berulang pada Frame yang Sama
# ==============================================================================

class DuplicateSubtitleSuppressorCore:
    def __init__(self):
        print("[SUPPRESSOR] Initializing Anti-Spam Filter...")
        self.config_file = "suppressor_config.json"
        self.last_text = ""
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def should_process(self, new_text):
        """
        Cek apakah teks baru ini beda dari teks sebelumnya?
        Return: True (Proses) atau False (Skip)
        """
        if not new_text: return False
        self._load_config()
        
        # 1. Exact Match (Cepat)
        if new_text == self.last_text:
            return False

        # 2. Similarity Match (Lambat tapi Akurat untuk OCR glitch)
        threshold = self.config.get("similarity_threshold", 0.95)
        
        # Menggunakan difflib yang sudah benar import-nya
        ratio = difflib.SequenceMatcher(None, self.last_text, new_text).ratio()
        
        if ratio >= threshold:
            return False # Terlalu mirip, anggap sama
            
        # Jika lolos, update last_text
        self.last_text = new_text
        return True