import json
import os
import re

# ==============================================================================
#   TITAN X - PROFESSOR SYNTAX CORE v1.0 (FINAL)
#   Divisi: ACADEMY (LINGUISTICS)
#   Tugas: Memperbaiki Tata Bahasa Indonesia (Grammar Polish)
# ==============================================================================

class ProfessorSyntaxCore:
    def __init__(self):
        print("[SYNTAX] Initializing Grammar Correction Unit...")
        self.config_file = "syntax_rules.json"
        self.rules = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.rules = json.load(f)
            except: pass

    def correct(self, text):
        """Memoles kalimat agar lebih alami bagi pembaca Indonesia"""
        if not text: return ""
        self._load_config()
        
        # 1. Simple Replacement (Kamus Sinonim)
        replacements = self.rules.get("replacements", {})
        for src, dst in replacements.items():
            pattern = re.compile(r'\b' + re.escape(src) + r'\b', re.IGNORECASE)
            text = pattern.sub(dst, text)
            
        # 2. Pattern Matching (Regex untuk struktur kalimat)
        patterns = self.rules.get("patterns", [])
        for p in patterns:
            try:
                text = re.sub(p['regex'], p['replace'], text, flags=re.IGNORECASE)
            except: pass
            
        return text