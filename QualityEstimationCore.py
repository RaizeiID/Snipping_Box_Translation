import json
import os

# ==============================================================================
#   TITAN X - QUALITY ESTIMATION CORE v1.0
#   Divisi: ACADEMY (QA)
#   Tugas: Menilai Kualitas Terjemahan sebelum Ditampilkan
# ==============================================================================

class QualityEstimationCore:
    def __init__(self):
        print("[QA] Initializing Quality Control Inspector...")
        self.config_file = "qa_standards.json"
        self.standards = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.standards = json.load(f)
            except: pass

    def assess(self, original, translation):
        """
        Menilai terjemahan.
        Return: (Valid: Bool, Reason: Str)
        """
        self._load_config()
        
        if not translation: return False, "EMPTY_OUTPUT"
        
        # 1. Cek Simbol Rusak
        for junk in self.standards.get("garbage_indicators", []):
            if junk in translation:
                return False, "GARBAGE_DETECTED"
                
        # 2. Cek Rasio Panjang (Hallucination Check)
        # Jika input "Hai" (3 huruf) tapi output 50 huruf, pasti error.
        len_org = len(original)
        len_trans = len(translation)
        ratio = self.standards.get("length_ratio_tolerance", 3.5)
        
        if len_org > 5 and len_trans > (len_org * ratio):
            return False, "HALLUCINATION_DETECTED"
            
        return True, "OK"