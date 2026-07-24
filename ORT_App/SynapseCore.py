import threading
import time

# ==============================================================================
#   TITAN X - SYNAPSE CORE v1.0
#   Divisi: COMMAND & SIGNALS
#   Tugas: Event Bus (Jalur Komunikasi Internal Antar Core)
#   Konsep: Pub/Sub (Publisher-Subscriber)
# ==============================================================================

class SynapseCore:
    def __init__(self):
        print("[SYNAPSE] Initializing Neural Network Signals...")
        self.subscribers = {} # { "EVENT_NAME": [callback_function, ...] }

    def subscribe(self, event_name, callback):
        """Core lain mendaftar untuk mendengarkan event tertentu"""
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(callback)

    def publish(self, event_name, data=None):
        """Core mengirim sinyal ke seluruh sistem"""
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                try:
                    # Jalankan di thread terpisah agar tidak memblokir sistem utama
                    threading.Thread(target=callback, args=(data,)).start()
                except Exception as e:
                    print(f"[SYNAPSE] Signal Error: {e}")