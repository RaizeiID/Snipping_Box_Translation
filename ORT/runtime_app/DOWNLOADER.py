import sys
import os
import shutil

# ==============================================================================
#   TITAN X - MANUAL DOWNLOADER & REPAIR TOOL
#   Tugas: Membersihkan Cache & Download Model Helsinki Secara Paksa
# ==============================================================================

def clean_huggingface_cache():
    # Lokasi Cache standar di Windows
    user_home = os.path.expanduser("~")
    cache_dir = os.path.join(user_home, ".cache", "huggingface", "hub")
    
    print(f"[1/3] Memeriksa Cache di: {cache_dir}")
    
    if os.path.exists(cache_dir):
        print("      Ditemukan file lama. Membersihkan potensi korupsi...")
        try:
            # Kita tidak hapus semua, tapi kita biarkan Transformers menimpa nanti.
            # Namun jika parah, user harus hapus folder ini manual.
            print("      Mode Aman: Cache tidak dihapus otomatis, tapi akan ditimpa.")
        except Exception as e:
            print(f"      Gagal akses cache: {e}")
    else:
        print("      Cache bersih.")

def install_dependencies():
    print("\n[2/3] Memastikan 'sentencepiece' terinstall...")
    try:
        import sentencepiece
        print("      SUCCESS: SentencePiece library detected.")
    except ImportError:
        print("      MISSING: SentencePiece belum ada!")
        print("      Sedang menginstall otomatis...")
        os.system("pip install sentencepiece")

def force_download_model():
    print("\n[3/3] MULAI DOWNLOAD MODEL (Internet Wajib Aktif!)")
    print("      Target: Helsinki-NLP/opus-mt-en-id")
    print("      Mohon tunggu... (Size: ~300MB)")
    
    try:
        from transformers import MarianMTModel, MarianTokenizer
        
        model_name = "Helsinki-NLP/opus-mt-en-id"
        
        # Force Download = True akan memaksa menimpa file cache yang rusak
        print("      ...Downloading Tokenizer...")
        tokenizer = MarianTokenizer.from_pretrained(model_name, force_download=True)
        
        print("      ...Downloading Model (Otak Utama)...")
        model = MarianMTModel.from_pretrained(model_name, force_download=True)
        
        print("\n[SUKSES] MODEL BERHASIL DIDOWNLOAD SEMPURNA!")
        print("Sekarang Anda bisa menjalankan TITANMAIN.py dengan aman.")
        
    except Exception as e:
        print(f"\n[GAGAL] Download Error: {e}")
        print("Pastikan internet stabil dan coba lagi.")

if __name__ == "__main__":
    print("=== TITAN SUPPLY DROP PROTOCOL ===\n")
    install_dependencies()
    clean_huggingface_cache()
    force_download_model()
    input("\nTekan Enter untuk keluar...")