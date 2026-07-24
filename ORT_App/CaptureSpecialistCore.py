import mss
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
