import re

# ==============================================================================
#   TITAN X - ENTITY DISCOVERY CORE v60.0 (NEW)
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Menganalisis & Memvalidasi Calon Nama Baru (Strict Filter)
# ==============================================================================

class EntityDiscoveryCore:
    def __init__(self):
        print("[DISCOVERY] Initializing Entity Detective Unit...")
        
        # 1. KAMUS PENOLAKAN (NEGATIVE LIST)
        # Jika kata ada di sini, SKOR -100 (Langsung Ditolak)
        self.blacklist_vocab = {
            # System
            "SYSTEM", "WARNING", "ERROR", "MISSION", "OBJECTIVE", "FAILED",
            "LOADING", "CONNECTING", "AUTO", "SKIP", "LOG", "REC", "LIVE",
            "HP", "SP", "MP", "EXP", "LV", "LEVEL", "RANK",
            # Kata Benda/Kerja Umum (Benda Mati)
            "DOOR", "GATE", "WALL", "FLOOR", "TABLE", "CHAIR", "GUN", "AMMO",
            "ENEMY", "UNIT", "SQUAD", "TEAM", "TARGET", "BOSS", "LEADER",
            "RUN", "WALK", "JUMP", "SHOOT", "OPEN", "CLOSE", "LOOK", "STOP",
            "HELLO", "HEY", "WOW", "OH", "AH", "HMM", "PLEASE", "SORRY"
        }

        # 2. INDIKATOR KUAT (POSITIVE LIST)
        # Jika ada gelar ini, SKOR +50
        self.honorifics = {"MR", "MRS", "MS", "DR", "CAPT", "SGT", "LT", "CMDR", "AGENT"}

    def investigate(self, text, known_names_list):
        """
        Menganalisis teks untuk mencari nama baru.
        Input: "Stranger: Who are you?"
        Output: "Stranger" (Jika valid), atau None (Jika tidak valid)
        """
        if not text: return None

        # A. EKSTRAKSI KANDIDAT (Kata pertama sebelum spasi/titik dua)
        parts = re.split(r'[ :]', text, 1)
        candidate = parts[0].strip()
        
        # Bersihkan simbol sisa (misal "Darture." -> "Darture")
        candidate = re.sub(r'[^a-zA-Z0-9\-]', '', candidate)

        # Jika kosong atau sudah dikenal, abaikan
        if not candidate or candidate in known_names_list:
            return None

        # B. HITUNG SKOR KEPERCAYAAN (CONFIDENCE SCORE)
        score = 0
        
        # 1. Validasi Dasar (Wajib)
        if not (2 < len(candidate) < 18): return None # Kepanjangan/kependekan
        if not candidate[0].isupper(): return None    # Harus kapital depan
        if not re.match(r'^[A-Za-z0-9\-]+$', candidate): return None # Alphanumeric only

        # 2. Cek Blacklist (Veto)
        if candidate.upper() in self.blacklist_vocab:
            # print(f"[DISCOVERY] Rejected '{candidate}' (Blacklisted)")
            return None
        if candidate.upper() == candidate and len(candidate) > 4:
            # ALL CAPS biasanya UI System, bukan nama (kecuali pendek spt M4A1)
            return None

        # 3. Analisis Konteks (Scoring)
        
        # [CRITICAL] Indikator Visual Novel (Titik Dua)
        # Cek di teks ASLI, bukan candidate yg sudah distrip
        if len(text) > len(candidate):
            char_after = text[len(candidate)]
            if char_after == ':':
                score += 60  # Poin SANGAT TINGGI (Hampir pasti nama)
            elif char_after == ' ' and len(text) > len(candidate)+1 and text[len(candidate)+1] == '(':
                score += 40  # Format "Nama (Something)"

        # [BONUS] Gelar Kehormatan
        if candidate.upper() in self.honorifics:
            # Jika kata pertama adalah gelar, ambil kata kedua sebagai nama sebenarnya
            # (Logic ini bisa dikembangkan lagi nanti)
            pass

        # [PENALTI] Kata Umum Bahasa Inggris
        # (Idealnya kita punya kamus english, tapi sementara pakai logika huruf kecil)
        # Jika sisa kalimat dimulai huruf kecil, kemungkinan kata pertama bukan nama tapi awal kalimat
        # Contoh: "Running is fun" -> 'Running' diikuti 'is'.
        # Tapi di game biasanya semua kapital di awal. Jadi kita skip logika ini untuk game.

        # C. KEPUTUSAN FINAL
        # Ambang batas (Threshold) skor minimal 50
        if score >= 50:
            return candidate
        else:
            # Jika skor rendah (misal cuma huruf besar di awal tanpa titik dua),
            # kita tolak agar tidak mendaftarkan "Table" atau "The".
            return None