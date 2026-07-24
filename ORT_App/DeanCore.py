import json
import os

# ==============================================================================
#   TITAN X - DEAN CORE v1.0
#   Divisi: THE ACADEMY (HEAD)
#   Tugas: Validasi Akhir & Pengambilan Keputusan (Quality Control)
# ==============================================================================

class DeanCore:
    def __init__(self):
        print("[DEAN] Initializing Final Review Board...")
        self.policy_file = "dean_policy.json"
        self.last_load = 0
        self.policy = {}
        self._load_policy(force=True)

    def _load_policy(self, force=False):
        if not os.path.exists(self.policy_file): return
        try:
            mtime = os.path.getmtime(self.policy_file)
            if not force and mtime <= self.last_load: return
            with open(self.policy_file, 'r') as f:
                self.policy = json.load(f)
            self.last_load = mtime
        except: pass

    def conduct_review(self, packet):
        """
        Memeriksa paket sebelum dikirim ke Formatter.
        Jika hasil Profesor Syntax/Tone merusak teks, Dean bisa membatalkannya.
        """
        self._load_policy()
        
        final_text = packet['translation_final']
        
        # 1. Cek Forbidden Words (Glitch parah)
        for bad_word in self.policy.get("forbidden_words", []):
            if bad_word in final_text:
                return "[REDACTED: GLITCH DETECTED]"

        # 2. Cek Rasio Panjang (Anti-Overflow)
        # Jika terjemahan 3x lebih panjang dari aslinya, curigai halusinasi mesin
        raw_len = len(packet['clean_text'])
        if raw_len > 5: # Hanya cek jika teks cukup panjang
            ratio = len(final_text) / raw_len
            if ratio > self.policy.get("max_length_ratio", 3.0):
                # Kembalikan teks raw terjemahan (sebelum dipoles profesor) jika polesan merusak
                return packet['translation_raw']

        return final_text