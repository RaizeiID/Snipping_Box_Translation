import json
import os
import time

# ==============================================================================
#   TITAN X - TIMELINE TRACKER CORE v1.0
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Melacak Kronologi Event & Waktu Sesi
# ==============================================================================

class TimelineTrackerCore:
    def __init__(self):
        print("[TIME] Initializing Chronometer...")
        self.start_time = time.time()
        self.events = []

    def log_event(self, event_type, description):
        """Mencatat event penting (misal: Pindah Scene)"""
        timestamp = time.time() - self.start_time
        entry = {
            "time": f"{timestamp:.2f}s",
            "type": event_type,
            "desc": description
        }
        self.events.append(entry)
        # print(f"[TIME] +{timestamp:.1f}s: {event_type}")

    def get_session_duration(self):
        return time.time() - self.start_time