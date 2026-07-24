import json
import os
import hashlib
import time

# ==============================================================================
#   TITAN X - MEMORY VAULT CORE v1.0
#   Divisi: ARCHIVES & MEMORY
#   Tugas: Penyimpanan Jangka Panjang (Persistent Storage)
#   Optimasi: Hash-based Indexing (Pencarian O(1) / Instan)
# ==============================================================================

class MemoryVaultCore:
    def __init__(self):
        print("[VAULT] Initializing Long-Term Memory Storage...")
        self.db_file = "vault_index.json"
        self.memory = {}
        self.last_save = 0
        self.SAVE_INTERVAL = 30 # Auto-save setiap 30 detik agar tidak lag
        self._load_memory()

    def _load_memory(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memory = data.get("entries", {})
                print(f"[VAULT] {len(self.memory)} memories loaded.")
            except: 
                self.memory = {}

    def _save_memory(self):
        """Menyimpan ke disk. Dilakukan secara periodik/async."""
        try:
            current_time = time.time()
            if current_time - self.last_save < self.SAVE_INTERVAL:
                return # Jangan spam save ke hardisk
            
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({"version": "1.0", "entries": self.memory}, f, indent=4)
            self.last_save = current_time
        except Exception as e:
            print(f"[VAULT] Save Error: {e}")

    def _generate_hash(self, text):
        """Membuat sidik jari unik untuk teks (MD5)"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def retrieve(self, text):
        """Mengingat kembali terjemahan lama"""
        if not text: return None
        text_hash = self._generate_hash(text)
        return self.memory.get(text_hash)

    def store(self, original_text, translated_text):
        """Menyimpan terjemahan baru"""
        if not original_text or not translated_text: return
        
        text_hash = self._generate_hash(original_text)
        
        # Hanya simpan jika belum ada atau ada revisi
        if text_hash not in self.memory or self.memory[text_hash] != translated_text:
            self.memory[text_hash] = translated_text
            self._save_memory() # Coba trigger save
            # print(f"[VAULT] Memorized: '{original_text[:20]}...'")