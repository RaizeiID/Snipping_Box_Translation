import json
import os
import cv2
import numpy as np

# ==============================================================================
#   TITAN X - VISION ANALYST CORE v1.0
#   Divisi: SURVEILLANCE & INPUT
#   Tugas: Menganalisis Konteks Visual (Menu vs Gameplay vs Loading)
# ==============================================================================

class VisionAnalystCore:
    def __init__(self):
        print("[VISION] Initializing Scene Analysis Unit...")
        self.config_file = "vision_rules.json"
        self.rules = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.rules = json.load(f)
            except: pass

    def analyze_scene(self, image_array):
        """
        Menganalisis gambar screenshot untuk menentukan konteks.
        Return: "SAFE_TO_TRANSLATE" atau "SKIP"
        """
        # Jika input kosong, skip
        if image_array is None or len(image_array) == 0:
            return "SKIP"

        # 1. Deteksi Kegelapan (Loading Screen biasanya hitam)
        # Hitung rata-rata kecerahan pixel
        try:
            # Konversi array mss ke format cv2 yang aman
            img = np.array(image_array)
            avg_color_per_row = np.average(img, axis=0)
            avg_color = np.average(avg_color_per_row, axis=0)
            brightness = np.mean(avg_color[:3]) # RGB average

            # Jika layar terlalu gelap (Hitam total < 10)
            if brightness < 10:
                return "SKIP" # Jangan terjemahkan layar hitam
        except:
            pass
            
        return "SAFE_TO_TRANSLATE"

    def scan_for_keywords(self, text_list):
        """
        Cek apakah teks berisi kata kunci 'Loading' atau 'Menu'
        """
        self._load_config()
        combined_text = " ".join(text_list).lower()
        
        # Cek Loading
        for kw in self.rules.get("skip_detection", {}).get("loading_screen_keywords", []):
            if kw.lower() in combined_text:
                return "LOADING_SCREEN"
                
        # Cek Menu
        menu_hits = 0
        menu_kws = self.rules.get("skip_detection", {}).get("menu_keywords", [])
        for kw in menu_kws:
            if kw.lower() in combined_text:
                menu_hits += 1
        
        if menu_hits >= 2: # Jika ada minimal 2 kata menu (misal "Start" dan "Exit")
            return "MAIN_MENU"
            
        return "DIALOG"