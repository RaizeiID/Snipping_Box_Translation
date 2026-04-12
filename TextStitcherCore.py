import re
import json
import os

# ==============================================================================
#   TITAN X - TEXT STITCHER CORE v2.0 (DYNAMIC)
#   Divisi: PRE-PROCESSING
#   Tugas: Menjahit Baris & Memisahkan Nama (Configurable)
# ==============================================================================

class TextStitcherCore:
    def __init__(self):
        print("[STITCHER] Initializing Dynamic Logic Unit v2.0...")
        self.config_file = "stitcher_rules.json"
        self.last_load = 0
        self.config = {
            "name_extraction_regex": r"^([A-Z][a-zA-Z0-9\-\.]+)[:\s]+(.*)",
            "max_name_length": 18,
            "line_connector_chars": ["-"],
            "sentence_end_chars": [".", "?", "!", "\"", "'"]
        }
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                mtime = os.path.getmtime(self.config_file)
                if not force and mtime <= self.last_load: return
                
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                self.last_load = mtime
            except: pass

    def stitch(self, raw_list_data):
        if not raw_list_data: return ""
        self._load_config()
        
        first_line = raw_list_data[0].strip()
        
        # 1. Cek Apakah Baris Pertama Adalah Nama? (Pakai Regex JSON)
        pattern = re.compile(self.config["name_extraction_regex"])
        match = pattern.match(first_line)
        
        cleaned_lines = []
        if match:
            potential_name = match.group(1)
            potential_text = match.group(2)
            
            # Validasi Panjang Nama
            if len(potential_name) < self.config["max_name_length"]:
                # Pisahkan nama dari teks (Nama akan diurus IdentityCore nanti)
                if potential_text: cleaned_lines.append(potential_text)
                cleaned_lines.extend(raw_list_data[1:])
            else:
                cleaned_lines = raw_list_data
        else:
            cleaned_lines = raw_list_data

        # 2. Jahit Kalimat (Stitching)
        final_text = ""
        connectors = self.config["line_connector_chars"]
        enders = self.config["sentence_end_chars"]
        
        for i, line in enumerate(cleaned_lines):
            line = line.strip()
            if not line: continue
            
            if i == 0:
                final_text = line
            else:
                last_char = final_text[-1] if final_text else ""
                # Jika diakhiri tanda hubung (-), sambung langsung (connec- tion)
                if last_char in connectors:
                    final_text = final_text[:-1] + line
                # Jika belum ada titik/tanda baca, sambung pakai spasi (kalimat lanjut)
                elif last_char not in enders:
                    final_text += " " + line
                # Jika sudah titik, sambung pakai spasi (kalimat baru)
                else:
                    final_text += " " + line
                    
        return final_text