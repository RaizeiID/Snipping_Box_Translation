import json
import os
import re
import time

# ==============================================================================
#   TITAN X - LEARNING ENGINE CORE v1.0 (EVOLUTION)
#   Divisi: R&D (RESEARCH & DEVELOPMENT)
#   Tugas: Memperbarui Knowledge Base (.json) secara Otomatis berdasarkan Pola
# ==============================================================================

class LearningEngineCore:
    def __init__(self):
        print("[LEARNING] Initializing Evolutionary Algorithms...")
        
        # Daftar File Otak yang bisa diedit
        self.files = {
            "sanitizer": "sanitizer_rules.json",
            "stitcher": "stitcher_rules.json",
            "syntax": "syntax_knowledge.json"
        }
        
        # Memory jangka pendek untuk pola berulang (sebelum diputuskan masuk JSON)
        self.anomaly_buffer = {} 
        self.THRESHOLD_TO_LEARN = 3 # Jika anomali muncul 3x, anggap itu pola tetap

    def _load_json(self, key):
        """Helper untuk membaca file JSON dengan aman"""
        filepath = self.files.get(key)
        if not filepath or not os.path.exists(filepath): return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return None

    def _save_json(self, key, data):
        """Helper untuk menulis ulang file JSON (Evolusi Permanen)"""
        filepath = self.files.get(key)
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"[EVOLUTION] 🧬 Knowledge Base '{key}' has been UPDATED!")
        except Exception as e:
            print(f"[EVOLUTION] ERR: Failed to mutate {key}: {e}")

    # ==========================================================================
    #   FITUR 1: BELAJAR SAMPAH BARU (SANITIZER EVOLUTION)
    # ==========================================================================
    def analyze_garbage_candidate(self, text):
        """
        Ditebak oleh Nexus/Validator jika teks terlihat acak.
        Contoh: "zxcvbnm", "46z.8", "|||"
        """
        if not text: return
        
        # 1. Cek Pola Anomali (Heuristik)
        # Jika teks mengandung angka/simbol di tengah kata tanpa spasi
        # Contoh: "alarm isl 4623" -> "4623" aneh.
        potential_garbage = re.findall(r'\b[a-z]*\d+[a-z=]*\b', text) # Temukan kata campuran angka
        
        for junk in potential_garbage:
            # Masukkan ke buffer
            self.anomaly_buffer[junk] = self.anomaly_buffer.get(junk, 0) + 1
            
            # Jika sudah muncul sering, SAHKAN jadi aturan baru
            if self.anomaly_buffer[junk] >= self.THRESHOLD_TO_LEARN:
                self.commit_new_sanitizer_rule(junk)
                del self.anomaly_buffer[junk] # Reset buffer

    def commit_new_sanitizer_rule(self, pattern_str):
        """Menulis aturan baru ke sanitizer_rules.json"""
        data = self._load_json("sanitizer")
        if not data: return
        
        current_patterns = data.get("garbage_patterns", [])
        
        # Cek duplikasi
        if pattern_str not in current_patterns:
            # Tambahkan sebagai Regex yang aman
            # Kita escape agar aman, tapi izinkan variasi
            new_regex = re.escape(pattern_str) 
            current_patterns.append(new_regex)
            
            data["garbage_patterns"] = current_patterns
            self._save_json("sanitizer", data)
            print(f"[EVOLUTION] Learned to ignore new garbage: '{pattern_str}'")

    # ==========================================================================
    #   FITUR 2: BELAJAR STRUKTUR KALIMAT (SYNTAX EVOLUTION)
    # ==========================================================================
    def suggest_correction(self, original, corrected):
        """
        Jika User (Anda) melakukan koreksi manual nanti (lewat fitur Feedback),
        sistem akan mempelajarinya.
        """
        # (Fitur ini akan aktif jika kita buat UI untuk koreksi manual)
# Simpan koreksi sebagai memory (tidak melatih bobot model, hanya knowledge/corrections)
try:
    base_dir = os.getcwd()
    path = os.path.join(base_dir, "user_corrections.json")
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    data.setdefault("pairs", [])
    data["pairs"].append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "original": original,
        "corrected": corrected
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[EVOLUTION] Stored user correction -> user_corrections.json")
except Exception:
    pass

    # ==========================================================================
    #   FITUR 3: AUTO-TUNING (PARAMETER EVOLUTION)
    # ==========================================================================
    def adjust_stitcher_sensitivity(self, avg_name_length):
        """
        Jika rata-rata nama di game ini ternyata panjang (misal 20 huruf),
        otomatis update stitcher_rules.json agar max_name_length naik.
        """
        data = self._load_json("stitcher")
        if not data: return
        
        current_max = data.get("max_name_length", 15)
        if avg_name_length > current_max:
            data["max_name_length"] = int(avg_name_length + 5)
            self._save_json("stitcher", data)
            print(f"[EVOLUTION] Adapted Stitcher sensitivity to: {data['max_name_length']}")


# ==========================================================================
#   FITUR 4: APPLY FEEDBACK LOG (LEARNING FROM USER CORRECTIONS)
# ==========================================================================
def apply_feedback_log(self, feedback_file="feedback_log.json", memory_file="translation_memory.json"):
    """Apply pending feedback corrections into translation memory (persistent cache)."""
    try:
        if not os.path.exists(feedback_file):
            print("[EVOLUTION] No feedback_log.json found.")
            return 0

        with open(feedback_file, "r", encoding="utf-8") as f:
            fb = json.load(f) or {}
        pending = fb.get("pending_reviews", []) or []
        if not pending:
            print("[EVOLUTION] No pending reviews.")
            return 0

        mem = {}
        if os.path.exists(memory_file):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    mem = json.load(f) or {}
            except Exception:
                mem = {}
        if not isinstance(mem, dict):
            mem = {}

        applied = 0
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for entry in pending:
            original = (entry.get("original") or "").strip()
            corr = (entry.get("user_correction") or "").strip()
            if not original or not corr:
                continue
            if mem.get(original) != corr:
                mem[original] = corr
                applied += 1
            entry["applied"] = True
            entry["applied_ts"] = now_str

        fb.setdefault("applied", [])
        fb["applied"].extend(pending)
        fb["pending_reviews"] = []

        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(fb, f, ensure_ascii=False, indent=2)

        print(f"[EVOLUTION] Applied {applied} corrections -> {memory_file}")
        return applied
    except Exception as e:
        print(f"[EVOLUTION] apply_feedback_log failed: {e}")
        return 0
