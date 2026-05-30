import re
import json
import os
import traceback

# ==============================================================================
#   TITAN X - SANITIZER CORE v2.0 (DYNAMIC)
#   Divisi: PRE-PROCESSING
#   Tugas: Membersihkan Sampah (Noise) Berdasarkan JSON
# ==============================================================================

class SanitizerCore:
    def __init__(self):
        print("[SANITIZER] Initializing Dynamic Cleaning Unit v2.0...")
        self.rules_file = "sanitizer_rules.json"
        self.last_load = 0
        self.patterns = []
        self.fixes = {}
        
        # Load aturan pertama kali
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        """Memuat regex sampah dari file external"""
        if not os.path.exists(self.rules_file): return
        
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.patterns = data.get("garbage_patterns", [])
                self.fixes = data.get("quick_fixes", {})
                
            self.last_load = mtime
        except Exception:
            traceback.print_exc()

    def clean(self, text):
        if not text: return ""
        self._load_rules() # Cek update otomatis
        
        # 1. Regex Garbage Removal (Hapus 'isl 4623', '46=3')
        for p in self.patterns:
            try:
                text = re.sub(p, '', text, flags=re.IGNORECASE)
            except: pass 

        # 2. Quick Fixes (Perbaikan Typo Kecil)
        for bad, good in self.fixes.items():
            pattern = re.compile(r'\b' + re.escape(bad) + r'\b', re.IGNORECASE)
            text = pattern.sub(good, text)
            
        # 3. Normalisasi Spasi
        text = re.sub(r'\s+', ' ', text).strip()
        return text