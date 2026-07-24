import json
import os

# ==============================================================================
#   TITAN X - MULTI CANDIDATE GENERATOR CORE v1.0
#   Divisi: ENGINE OPS
#   Tugas: Menghasilkan & Memilih Opsi Terjemahan Terbaik
# ==============================================================================

class MultiCandidateGeneratorCore:
    def __init__(self):
        print("[GEN] Initializing Candidate Generator...")
        self.config_file = "generator_config.json"
        self.config = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: pass

    def process(self, engine_instance, text):
        """
        Meminta engine menghasilkan beberapa opsi (jika didukung).
        Untuk Helsinki (NMT), kita simulasi pass-through dulu di v1.0.
        """
        # Di masa depan: Loop range(candidate_count) dengan temperature berbeda
        # Saat ini: Langsung return hasil tunggal
        if engine_instance:
            return engine_instance.translate(text)
        return text