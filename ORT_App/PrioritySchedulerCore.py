import json
import os

# ==============================================================================
#   TITAN X - PRIORITY SCHEDULER CORE v1.0
#   Divisi: BACKBONE & OPTIMIZATION
#   Tugas: Menentukan Urutan Eksekusi Tugas
# ==============================================================================

class PrioritySchedulerCore:
    def __init__(self):
        print("[SCHEDULER] Initializing Priority Queue...")
        self.config_file = "scheduler_policy.json"
        self.policy = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.policy = json.load(f).get("priorities", {})
            except: pass

    def get_priority_level(self, task_type):
        """
        Input: "TRANSLATE_REQUEST" -> Output: 1 (HIGH)
        Input: "SAVE_LOG" -> Output: 3 (LOW)
        """
        # Default Normal
        if not task_type: return 2
        
        task_type = task_type.upper()
        if "UI" in task_type or "RENDER" in task_type:
            return self.policy.get("CRITICAL", 0)
        elif "TRANSLATE" in task_type or "OCR" in task_type:
            return self.policy.get("HIGH", 1)
        elif "SAVE" in task_type or "LOG" in task_type:
            return self.policy.get("LOW", 3)
            
        return self.policy.get("NORMAL", 2)