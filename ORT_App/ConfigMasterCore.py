import json
import os

# ==============================================================================
#   TITAN X - CONFIG MASTER CORE v1.0
#   Divisi: COMMAND & LOGISTICS
#   Tugas: Mengelola User Preferences (Settings) yang Persisten
# ==============================================================================

class ConfigMasterCore:
    def __init__(self):
        print("[CONFIG] Initializing Settings Manager...")
        self.config_file = "user_config.json"
        self.settings = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.settings = json.load(f)
            except: 
                print("[CONFIG] Corrupt config. Using defaults.")
                self.settings = {}
        else:
            print("[CONFIG] No config found. Creating new.")
            self._save_config() # Create default

    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"[CONFIG] Save Failed: {e}")

    def get(self, section, key, default=None):
        """Ambil settingan dengan aman"""
        try:
            return self.settings.get(section, {}).get(key, default)
        except:
            return default

    def set(self, section, key, value):
        """Ubah settingan dan simpan permanen"""
        if section not in self.settings:
            self.settings[section] = {}
        
        self.settings[section][key] = value
        self._save_config()
        # print(f"[CONFIG] Updated {section}.{key} = {value}")