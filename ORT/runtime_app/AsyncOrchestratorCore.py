import json
import os
import threading
import queue
import time

# ==============================================================================
#   TITAN X - ASYNC ORCHESTRATOR CORE v1.0
#   Divisi: BACKBONE & PARALLELISM
#   Tugas: Mengelola Threading agar UI tidak Freeze
# ==============================================================================

class AsyncOrchestratorCore:
    def __init__(self):
        print("[ASYNC] Initializing Thread Manager...")
        self.config_file = "async_config.json"
        self.task_queue = queue.PriorityQueue()
        self.active = True
        self._load_config(force=True)
        
        # Mulai Worker Threads
        self.workers = []
        self.start_workers()

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except: self.config = {}

    def start_workers(self):
        """Membuat pasukan pekerja di latar belakang"""
        count = self.config.get("max_worker_threads", 2)
        print(f"[ASYNC] Spawning {count} worker threads...")
        
        for i in range(count):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            t.start()
            self.workers.append(t)

    def submit_task(self, priority, task_func, args=()):
        """
        Mendaftarkan tugas baru.
        Priority: 0 (Critical), 1 (Normal), 2 (Background)
        """
        # Masukkan ke antrian
        self.task_queue.put((priority, task_func, args))

    def _worker_loop(self, worker_id):
        while self.active:
            try:
                # Ambil tugas dari antrian (tunggu max 1 detik)
                priority, task_func, args = self.task_queue.get(timeout=1.0)
                
                # Kerjakan tugas
                # print(f"[WORKER-{worker_id}] Executing task (Prio: {priority})")
                task_func(*args)
                
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[WORKER-{worker_id}] Error: {e}")