import json
import os
import re

# ==============================================================================
#   TITAN X - TERMINOLOGY CONSTRAINT CORE v1.0
#   Divisi: QA & INTEGRITY
#   Tugas: Memastikan Output Bersih dari Kata Terlarang (Post-Processing)
# ==============================================================================

class TerminologyConstraintCore:
    def __init__(self):
        print("[TERM] Initializing Vocabulary Enforcer...")
        self.config_file = "term_constraints.json"
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def enforce(self, text):
        """Membersihkan output terjemahan"""
        if not text: return ""
        self._load_config()
        
        # 1. Sensor Kata Kasar (Output)
        forbidden = self.config.get("forbidden_output_words", [])
        for word in forbidden:
            # Ganti dengan bintang ****
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            text = pattern.sub("*" * len(word), text)
            
        return text