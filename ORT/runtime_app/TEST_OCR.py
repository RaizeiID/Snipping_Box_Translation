import sys
import os
import pytesseract
import mss
import numpy as np
import cv2
import time

# ==============================================================================
#   ALAT DIAGNOSA MATA TITAN
# ==============================================================================

# 1. CEK LOKASI TESSERACT (GANTI JIKA LOKASI ANDA BEDA)
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# TESSERACT_PATH = r'C:\Users\Raizei\AppData\Local\Tesseract-OCR\tesseract.exe' # Coba ini jika yg atas gagal

print("--- MULAI DIAGNOSA ---")

# CEK 1: APAKAH FILE EXE ADA?
if os.path.exists(TESSERACT_PATH):
    print(f"[OK] Tesseract ditemukan di: {TESSERACT_PATH}")
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print(f"[FATAL ERROR] Tesseract TIDAK ADA di: {TESSERACT_PATH}")
    print("Solusi: Install Tesseract-OCR atau perbaiki path di script ini!")
    sys.exit()

# CEK 2: COBA AMBIL GAMBAR
print("[INFO] Mengambil screenshot layar dalam 3 detik...")
time.sleep(3)

try:
    with mss.mss() as sct:
        # Ambil area tengah layar
        monitor = sct.monitors[1]
        width = monitor["width"]
        height = monitor["height"]
        
        # Kotak dialog game biasanya di bawah
        region = {'top': int(height * 0.7), 'left': int(width * 0.2), 'width': int(width * 0.6), 'height': 200}
        
        print(f"[INFO] Area Capture: {region}")
        img = np.array(sct.grab(region))
        
        # Convert ke Hitam Putih (Sama seperti Titan asli)
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        print("[INFO] Gambar berhasil diambil. Mencoba membaca teks...")

        # CEK 3: COBA BACA TEKS (OCR)
        text = pytesseract.image_to_string(thresh)
        
        print("\n=== HASIL PENGLIHATAN TITAN ===")
        if text.strip():
            print(f"TEKS DIBACA: \n{text}")
            print("=== DIAGNOSA: SUKSES ===")
            print("Mata Titan berfungsi! Masalah ada di logika NexusCore.")
        else:
            print("[KOSONG]")
            print("=== DIAGNOSA: RABUN ===")
            print("Tesseract jalan, tapi tidak melihat teks. Coba geser game ke area capture.")

except Exception as e:
    print(f"\n[FATAL CRASH] Error saat proses OCR: {e}")
    print("Kemungkinan Library Tesseract belum terinstall sempurna atau path salah.")

input("\nTekan Enter untuk menutup...")