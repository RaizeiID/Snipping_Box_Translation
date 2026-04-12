import json
import os
import time

# ==============================================================================
#   TITAN X - LQA REPORT CORE v1.0
#   Divisi: REPORTING & ANALYTICS
#   Tugas: Linguistic Quality Assurance (Laporan Kinerja)
# ==============================================================================

class LQAReportCore:
    def __init__(self):
        print("[LQA] Initializing Analytics Reporter...")
        self.stats = {
            "total_translated": 0,
            "cache_hits": 0,
            "errors": 0,
            "start_time": time.time()
        }
        
        # Buat folder report jika belum ada
        if not os.path.exists("reports"):
            os.makedirs("reports")

    def track_event(self, event_type):
        """Mencatat kejadian (translated, cache_hit, error)"""
        if event_type in self.stats:
            self.stats[event_type] += 1
        else:
            self.stats[event_type] = 1

    def generate_report(self):
        """Menulis laporan ke file .txt"""
        runtime = (time.time() - self.stats["start_time"]) / 60 # menit
        filename = f"reports/session_{int(time.time())}.txt"
        
        report = f"""
        ========================================
        TITAN X - SESSION REPORT
        ========================================
        Runtime     : {runtime:.2f} minutes
        Total Text  : {self.stats.get('total_translated', 0)}
        Cache Hits  : {self.stats.get('cache_hits', 0)}
        Errors      : {self.stats.get('errors', 0)}
        ========================================
        """
        
        try:
            with open(filename, 'w') as f:
                f.write(report)
            # print(f"[LQA] Report saved to {filename}")
        except: pass