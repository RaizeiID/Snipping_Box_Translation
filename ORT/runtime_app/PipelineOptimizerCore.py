import json
import os

# ==============================================================================
#   TITAN X - PIPELINE OPTIMIZER CORE v1.0
#   Divisi: PERFORMANCE & OPTIMIZATION
#   Tugas: Memilih Strategi Eksekusi Terbaik
# ==============================================================================

class PipelineOptimizerCore:
    def __init__(self):
        print("[OPTIMIZER] Initializing Execution Strategy Manager...")
        self.config_file = "pipeline_strategies.json"
        self.strategies = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.strategies = json.load(f)
            except: pass

    def get_optimization_plan(self, throttle_recommendation):
        """
        Menggabungkan rekomendasi Throttle dengan strategi Pipeline.
        """
        self._load_config()
        
        disabled = throttle_recommendation.get("disabled_cores", [])
        
        # Jika throttle bilang disable ProfessorTone, kita buat plan khusus
        plan = {
            "skip_academy": False,
            "skip_context": False,
            "active_cores_mask": [] # List core yang BOLEH jalan
        }
        
        # Logika Sederhana: Translate rekomendasi Throttle menjadi Flag Boolean
        # agar mudah dibaca Nexus
        if "ProfessorTone" in disabled or "ProfessorSyntax" in disabled:
            plan["skip_academy"] = True
            
        if "Sociologist" in disabled or "EntityDiscovery" in disabled:
            plan["skip_context"] = True
            
        return plan