import json
import os
import re

# ==============================================================================
#   TITAN X - IDENTITY CORE v60.0
#   Divisi: CONTEXT INTELLIGENCE
#   Tugas: Database Identitas NPC & Pemisahan Speaker
# ==============================================================================

class IdentityCore:
    def __init__(self):
        print("[IDENTITY] Initializing Entity Registry System...")
        
        self.db_file = "npc_database.json"
        
        # 1. MEMORY AWAL (Starter Pack)
        # Kita masukkan nama-nama yang ada di screenshot Anda agar langsung kenal
        self.known_identities = {
            "Darture", "Leva", "Alva", "Soppo", "Commander", 
            "Kalina", "Persica", "Helian", "Kryuger", "Architect", 
            "Ouroboros", "Dreamer", "Judge", "Gager", "Intruder"
        }
        
        # 2. BLACKLIST (Kata yang mirip nama tapi BUKAN nama)
        # Agar dia tidak salah belajar kata umum menjadi nama orang
        self.blacklist_names = {
            "The", "And", "But", "When", "Then", "If", "So", 
            "System", "Warning", "Error", "Mission", "Objective", 
            "Loading", "Connecting", "Chapter", "Episode", "Time",
            "Hp", "Sp", "Atk", "Def", "Ammo", "Reload", "Menu",
            "Yes", "No", "Cancel", "Confirm", "Auto", "Skip"
        }

        self.load_database()

    def load_database(self):
        """Memuat database nama dari file JSON"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Gabungkan database file dengan memory awal (union)
                    saved_names = set(data.get("names", []))
                    self.known_identities = self.known_identities.union(saved_names)
                    print(f"[IDENTITY] Database Loaded: {len(self.known_identities)} Entities Registered.")
            except Exception as e:
                print(f"[IDENTITY] ERR: Corrupt Database ({e}). Rebuilding new one.")
                self.save_database()
        else:
            print("[IDENTITY] No database found. Creating new registry.")
            self.save_database()

    def save_database(self):
        """Menyimpan database nama ke file JSON (Persistent Memory)"""
        try:
            data = {"names": list(self.known_identities)}
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            # print("[IDENTITY] Database Saved.") # Spam log dimatikan agar bersih
        except Exception as e:
            print(f"[IDENTITY] ERR: Save Failed ({e})")

    def identify(self, text):
        """
        Menganalisis teks: Apakah diawali nama orang?
        Input: "Darture Halo apa kabar"
        Output: ("Darture", "Halo apa kabar")
        """
        if not text: return None, ""

        # A. CEK DATABASE (MATCHING)
        # Kita cek apakah teks dimulai dengan salah satu nama di database
        # Kita urutkan nama dari yang terpanjang dulu agar akurat (misal "UMP45" vs "UMP")
        sorted_names = sorted(self.known_identities, key=len, reverse=True)
        
        for name in sorted_names:
            # Cek di awal kalimat (Case Insensitive sementara untuk deteksi)
            if text.lower().startswith(name.lower()):
                # Validasi batas kata (Agar "Commander" tidak match "Commanders")
                # Kita cek karakter setelah nama
                len_name = len(name)
                if len(text) == len_name: # Teks cuma nama doang
                    return name, ""
                
                char_after = text[len_name]
                if not char_after.isalnum(): # Jika setelah nama adalah spasi/titik/koma (Bukan huruf)
                    # KETEMU! Ini adalah Speaker.
                    
                    # Ambil sisa teks (Isi Dialog)
                    # Kita buang karakter pemisah seperti ':', ' ', atau '-'
                    remainder = text[len_name:].strip(" :.,-><")
                    
                    return name, remainder

        # B. AUTODIDACT (BELAJAR NAMA BARU)
        # Jika tidak ada di database, kita analisis apakah ini "Pola Nama"?
        # Pola: Kata pertama Uppercase, pendek, diikuti tanda baca dialog
        potential_speaker = self._autodidact_scan(text)
        if potential_speaker:
            # Daftarkan nama baru!
            self.known_identities.add(potential_speaker)
            self.save_database()
            print(f"[IDENTITY] NEW ENTITY DETECTED & REGISTERED: '{potential_speaker}'")
            
            # Kembalikan sebagai speaker
            remainder = text[len(potential_speaker):].strip(" :.,-><")
            return potential_speaker, remainder

        # Jika bukan nama siapapun
        return None, text

    def _autodidact_scan(self, text):
        """
        Logika Cerdas untuk menebak apakah kata pertama adalah nama baru.
        """
        # Ambil kata pertama
        parts = text.split(' ', 1)
        candidate = parts[0].strip(" :.,")

        # RULE 1: Panjang wajar (2-12 huruf)
        if not (2 < len(candidate) < 15): return None
        
        # RULE 2: Harus diawali Huruf Besar & Sisanya campuran (Alphanumeric)
        # Mencegah angka murni atau simbol
        if not candidate[0].isupper(): return None
        if not candidate.replace("-", "").isalnum(): return None # Boleh ada dash misal AR-15

        # RULE 3: Tidak boleh ada di Blacklist
        if candidate in self.blacklist_names: return None
        
        # RULE 4: Indikator Dialog Kuat
        # Nama biasanya diikuti titik dua (:) atau spasi lalu kutipan
        # Cek raw text aslinya
        if len(text) > len(candidate):
            char_after = text[len(candidate)]
            # Jika setelah kata ada ':', kemungkinan besar itu nama (Ex: "Soldier: Attack!")
            if char_after == ':':
                return candidate
            
            # Jika Uppercase semua (Ex: "WARNING System failure"), jangan anggap nama
            if candidate.isupper() and len(candidate) > 4: 
                return None

        return None