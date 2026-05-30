import sys

print("--- UJI COBA TOKENIZER ---")

# 1. CEK LIBRARY SENTENCEPIECE
try:
    import sentencepiece
    print("[OK] Library 'sentencepiece' ditemukan.")
    print(f"     Versi: {sentencepiece.__version__}")
except ImportError:
    print("[FATAL] Library 'sentencepiece' BELUM TERINSTALL!")
    print("Solusi: Jalankan 'pip install sentencepiece' di terminal.")
    sys.exit()

# 2. CEK LOAD TOKENIZER
try:
    from transformers import MarianTokenizer
    print("[INFO] Mencoba memuat Tokenizer Helsinki...")
    
    # Kita paksa download jika belum ada
    tokenizer = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-id")
    
    print("[SUKSES] Tokenizer berhasil dimuat!")
    print("Malah crash tadi sudah teratasi.")
    
except Exception as e:
    print(f"[ERROR] Masih gagal memuat Tokenizer: {e}")

print("--- SELESAI ---")