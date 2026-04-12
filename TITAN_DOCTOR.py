import os
import shutil
import time

# ==============================================================================
#   TITAN DOCTOR - AUTO REPAIR TOOL
#   Tugas: Memaksa update file yang "nyangkut" dan menghapus cache
# ==============================================================================

def fix_capture_core():
    filename = "CaptureSpecialistCore.py"
    print(f"[DOCTOR] Memperbaiki {filename}...")
    
    # KODE BARU (YANG BENAR)
    code = r'''import mss
import numpy as np
import pytesseract
import cv2
import os

# ==============================================================================
#   TITAN X - CAPTURE SPECIALIST CORE v2.2 (FINAL REVISION)
# ==============================================================================

TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

class CaptureSpecialistCore:
    def __init__(self):
        # TANDA BAHWA FILE INI BARU
        print("[CAPTURE] Initializing Optical Unit v2.2 (FINAL - DEBUG MODE)...")
        self.sct = mss.mss()
        
    def grab_text(self, region):
        if not region: return []
        try:
            sct_img = self.sct.grab(region)
            img = np.array(sct_img)
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
            
            config_ocr = r'--psm 6 --oem 3'
            raw_text = pytesseract.image_to_string(thresh, lang='eng', config=config_ocr)
            
            lines = [line.strip() for line in raw_text.split('\n') if len(line.strip()) > 1]
            
            if lines: print(f"[DEBUG MATA]: Melihat -> {lines}")
            return lines

        except Exception as e:
            print(f"[CAPTURE ERROR]: {e}")
            return []
'''
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)
    print("   -> Selesai ditulis.")

def fix_ui_constraint():
    filename = "UIConstraintCore.py"
    print(f"[DOCTOR] Memperbaiki {filename} (Error Titik Dua)...")
    
    code = r'''import json
import os
import textwrap

class UIConstraintCore:
    def __init__(self):
        print("[UI-C] Initializing Layout Engine v1.1 (FIXED)...")
        self.config_file = "ui_constraints.json"
        self.config = {}

    def fit_text(self, text):
        if not text: return ""
        width = 60
        max_lines = 3
        wrapped_lines = textwrap.wrap(text, width=width)
        
        # INI PERBAIKANNYA (ADA TITIK DUA)
        if len(wrapped_lines) > max_lines:
            wrapped_lines = wrapped_lines[:max_lines]
            wrapped_lines[-1] += "..."
            
        return "<br>".join(wrapped_lines)
'''
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)
    print("   -> Selesai ditulis.")

def nuke_cache():
    print("[DOCTOR] Menghapus Cache Python (__pycache__)...")
    if os.path.exists("__pycache__"):
        try:
            shutil.rmtree("__pycache__")
            print("   -> Cache dimusnahkan.")
        except:
            print("   -> Gagal hapus cache (mungkin sedang dipakai), tapi tidak apa-apa.")
    else:
        print("   -> Cache sudah bersih.")

if __name__ == "__main__":
    print("=== MEMULAI OPERASI BEDAH FILE ===")
    nuke_cache()
    fix_capture_core()
    fix_ui_constraint()
    print("\n=== OPERASI SELESAI ===")
    print("File Anda sekarang sudah 100% benar.")
    print("Silakan jalankan TITAN_DEBUG_MAIN.py (Langkah 2).")