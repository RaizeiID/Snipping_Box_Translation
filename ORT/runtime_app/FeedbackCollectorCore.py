import json
import os
import time

# ==============================================================================
#   TITAN X - FEEDBACK COLLECTOR CORE v1.0
#   Divisi: LEARNING & IMPROVEMENT
#   Tugas: Menampung Data Koreksi untuk Evolusi
# ==============================================================================

class FeedbackCollectorCore:
    def __init__(self):
        print("[FEEDBACK] Initializing User Input Channel...")
        self.log_file = "feedback_log.json"

    def log_correction(self, original, wrong_translation, user_correction):
        """
        Mencatat koreksi manual user.
        Data ini nanti akan diambil oleh LearningEngine untuk update JSON.
        """
        entry = {
            "timestamp": time.time(),
            "original": original,
            "wrong": wrong_translation,
            "correct": user_correction
        }
        
        self._append_to_log(entry)
        print(f"[FEEDBACK] Correction logged. Evolution pending.")

    def _append_to_log(self, entry):
        data = {"pending_reviews": []}
        
        # Load existing
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except: pass
            
        # Append new
        data["pending_reviews"].append(entry)
        
        # Save
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[FEEDBACK] Log Error: {e}")