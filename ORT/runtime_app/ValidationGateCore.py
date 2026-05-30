import json
import os
import re

# ==============================================================================
#   TITAN X - VALIDATION GATE CORE v1.0
#   Divisi: QA & SECURITY
#   Tugas: Pemeriksaan Terakhir Sebelum Display (Final Barrier)
# ==============================================================================

class ValidationGateCore:
    def __init__(self):
        print("[GATE] Initializing Final Security Checkpoint...")
        self.config_file = "safety_policy.json"
        self.policy = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.policy = json.load(f)
            except: pass

    def inspect(self, text):
        """
        Memeriksa apakah teks aman untuk ditampilkan di UI.
        Return: (Safe_Text, Is_Modified)
        """
        self._load_config()
        if not text: return "", False
        
        original = text
        
        # 1. Block HTML Tags (Mencegah UI rusak/injection)
        if self.policy.get("block_html_tags", True):
            # Hapus tag <...> kecuali <b>, <i>, <br> yang diizinkan Formatter
            # Regex sederhana: cari <tag> yang bukan b, i, br, span
            cleaner = re.compile(r'<(?!/?(b|i|br|span|font)(>|\\s))[^>]+>')
            text = re.sub(cleaner, '', text)

        # 2. Max Length (Mencegah UI tertutup teks panjang)
        limit = self.policy.get("max_output_length", 500)
        if len(text) > limit:
            text = text[:limit] + "... [TRUNCATED]"

        return text, (text != original)