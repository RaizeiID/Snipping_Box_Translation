import json
import os

# ==============================================================================
#   TITAN X - SEMANTICS CORE v1.0
#   Divisi: ENGINE & LINGUISTICS
#   Tugas: Menyiapkan Prompt Konteks & Anti-Sensor
# ==============================================================================

class SemanticsCore:
    def __init__(self):
        print("[SEMANTICS] Initializing Meaning Analysis Unit...")
        self.rules_file = "semantics_rules.json"
        self.last_load = 0
        self.rules = {}
        self._load_rules(force=True)

    def _load_rules(self, force=False):
        if not os.path.exists(self.rules_file): return
        try:
            mtime = os.path.getmtime(self.rules_file)
            if not force and mtime <= self.last_load: return
            with open(self.rules_file, 'r') as f:
                self.rules = json.load(f)
            self.last_load = mtime
        except: pass

    def prepare(self, packet):
        """
        Memodifikasi teks input agar siap dimakan oleh Helsinki.
        Bisa menambahkan 'Prompt' di awal kalimat agar hasil lebih akurat.
        """
        self._load_rules()
        text = packet['clean_text']
        tags = packet.get('context_tags', [])
        
        # 1. Inject Prompt (Eksperimental untuk NMT)
        # Note: Helsinki Opus MT sebenarnya tidak terlalu butuh prompt seperti GPT,
        # tapi kita siapkan strukturnya jika nanti Anda ganti ke LLM (Llama/Mistral).
        # Untuk saat ini, kita biarkan text murni agar tidak merusak grammar Helsinki.
        
        # 2. Anti-Sensor (Soft)
        # Pastikan kata-kata kasar tidak dihapus oleh pre-processing sebelumnya
        # (Pass-through logic)
        
        return text