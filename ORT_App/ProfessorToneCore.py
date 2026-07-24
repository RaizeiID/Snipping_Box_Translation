import json
import os
import re

# ==============================================================================
#   TITAN X - PROFESSOR TONE CORE v1.0
#   Divisi: THE ACADEMY
#   Tugas: Menyuntikkan Emosi & Nuansa ke dalam Teks
# ==============================================================================

class ProfessorToneCore:
    def __init__(self):
        print("[TONE] Initializing Emotional Intelligence Unit...")
        self.rules_file = "tone_profiles.json"
        self.last_load = 0
        self.profiles = {}
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        if not os.path.exists(self.rules_file): return
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            with open(self.rules_file, 'r') as f:
                self.profiles = json.load(f)
            self.last_load = mtime
        except: pass

    def polish(self, text, context_tags):
        """
        Input: "Aku tidak mau." (Tag: Angry)
        Output: "Gua tidak mau!"
        """
        if not text: return ""
        self._load_rules()
        
        # Cari profil emosi yang cocok (Prioritas: Angry > Formal > Casual)
        active_profile = None
        for tag in context_tags:
            if tag in self.profiles:
                active_profile = self.profiles[tag]
                break
        
        if not active_profile:
            return text

        # 1. Lakukan Penggantian Kata (Replacements)
        replacements = active_profile.get("replacements", {})
        for origin, target in replacements.items():
            # Case insensitive replace
            pattern = re.compile(r'\b' + re.escape(origin) + r'\b', re.IGNORECASE)
            text = pattern.sub(target, text)

        # 2. Tambahkan Suffix (Akhiran)
        suffix = active_profile.get("suffix", "")
        if suffix:
            # Jika kalimat belum diakhiri tanda baca yang sama
            if not text.endswith(suffix):
                # Hapus titik biasa jika mau ganti tanda seru
                if text.endswith(".") and suffix == "!":
                    text = text[:-1]
                text += suffix
                
        return text