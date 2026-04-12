import json
import os

# ==============================================================================
#   TITAN X - CONTEXT BUFFER CORE v1.0
#   Divisi: MEMORY & CONTEXT
#   Tugas: Mengingat Percakapan Jangka Pendek (Short-Term Memory)
# ==============================================================================

class ContextBufferCore:
    def __init__(self):
        print("[BUFFER] Initializing Short-Term Memory...")
        self.config_file = "buffer_config.json"
        self.buffer = [] # List untuk menyimpan histori percakapan
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def push(self, speaker, text):
        """Menambahkan percakapan baru ke ingatan"""
        self._load_config()
        limit = self.config.get("buffer_size", 5)
        
        entry = {"speaker": speaker, "text": text}
        self.buffer.append(entry)
        
        # Jaga agar buffer tidak kepenuhan
        if len(self.buffer) > limit:
            self.buffer.pop(0)

    def get_context_string(self):
        """
        Mengembalikan teks gabungan untuk membantu Helsinki memahami konteks.
        Contoh output: "A: Halo. B: Hai. A: Apa kabar? [TARGET]"
        """
        context_str = ""
        for item in self.buffer:
            spk = item['speaker'] if item['speaker'] else "?"
            txt = item['text']
            context_str += f"{spk}: {txt} | "
        return context_str
        
    def clear(self):
        self.buffer = []