import re
import json
import os
import traceback

# ==============================================================================
#   TITAN X - SPELL WEAVER CORE v1.1 (SELF-HEALING)
#   Divisi: PRE-PROCESSING & POST-PROCESSING
#   Tugas: Memperbaiki Glitch Kata, Typo, dan Artefak Simbol
#   Kemampuan: Auto-Correction & Pattern Learning Request
# ==============================================================================

class SpellWeaverCore:
    def __init__(self):
        print("[SPELLWEAVER] Initializing Self-Healing Protocols v1.1...")
        self.rules_file = "spell_rules.json"
        self.last_load = 0
        self.glitch_patterns = []
        self.dictionary = {}
        
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        if not os.path.exists(self.rules_file): return
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.glitch_patterns = data.get("glitch_patterns", [])
                self.dictionary = data.get("known_corrections", {})
                
            self.last_load = mtime
        except Exception:
            traceback.print_exc()

    def fix(self, text):
        """
        Fungsi utama: Menerima teks rusak -> Mengembalikan teks bersih.
        """
        if not text: return ""
        self._load_rules() # Cek apakah ada evolusi baru?

        original_text = text

        # 1. PENYEMBUHAN GLITCH (REGEX DINAMIS)
        # Menangani kasus "1berada", "|saat", dsb.
        for rule in self.glitch_patterns:
            try:
                pattern = re.compile(rule["regex"])
                text = pattern.sub(rule["replacement"], text)
            except: pass

        # 2. PENYEMBUHAN KATA (DICTIONARY)
        # Menangani "yg" -> "yang"
        # Kita split jadi kata per kata agar akurat
        words = text.split()
        fixed_words = []
        for word in words:
            # Bersihkan tanda baca untuk pengecekan kamus
            clean_word = re.sub(r'[^\w]', '', word).lower()
            
            if clean_word in self.dictionary:
                # Pertahankan casing asli (Huruf besar/kecil)
                replacement = self.dictionary[clean_word]
                if word[0].isupper():
                    replacement = replacement.capitalize()
                fixed_words.append(replacement)
            else:
                fixed_words.append(word)
        
        text = " ".join(fixed_words)

        # 3. HEURISTIC CHECK (DETEKSI ANOMALI UNTUK EVOLUSI)
        # Jika setelah diperbaiki masih ada angka di tengah huruf (yang lolos regex),
        # Lapor ke LearningEngine (lewat return value atau logs)
        # (Nanti Nexus yang akan menangkap ini dan mengirim ke LearningEngine)
        
        return text.strip()