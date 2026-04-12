import json
import os
import time

# ==============================================================================
#   TITAN X - REGRESSION TEST CORE v1.0
#   Divisi: QA & TESTING
#   Tugas: Menguji Integritas Sistem (Sanity Check)
# ==============================================================================

class RegressionTestCore:
    def __init__(self):
        print("[TEST] Initializing Simulator Unit...")
        self.suite_file = "test_suite.json"
        self.tests = []
        self._load_suite(force=True)

    def _load_suite(self, force=False):
        if os.path.exists(self.suite_file):
            try:
                with open(self.suite_file, 'r') as f:
                    self.tests = json.load(f).get("sanity_check", [])
            except: pass

    def run_diagnostics(self, translation_engine_callback):
        """
        Menjalankan tes otomatis.
        Butuh akses ke fungsi translate() dari HelsinkiCore.
        """
        print("[TEST] Running System Diagnostics...")
        score = 0
        total = len(self.tests)
        
        if total == 0:
            print("[TEST] No tests defined.")
            return True

        for case in self.tests:
            inp = case["input"]
            expected = case["expected_keyword"]
            
            # Coba terjemahkan (Simulasi)
            try:
                result = translation_engine_callback(inp)
                if expected.lower() in result.lower():
                    score += 1
                else:
                    print(f"[TEST] ❌ FAIL: '{inp}' -> '{result}' (Expected: {expected})")
            except Exception as e:
                print(f"[TEST] 💥 CRASH: {e}")

        success_rate = (score / total) * 100
        print(f"[TEST] Diagnostics Complete. Health: {success_rate:.1f}%")
        
        return success_rate == 100