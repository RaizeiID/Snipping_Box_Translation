import json
import os

# ==============================================================================
#   TITAN X - FORMATTER CORE v1.1 (DYNAMIC DISPLAY)
#   Divisi: PRESENTATION & UX
#   Tugas: Merender HTML berdasarkan Konteks & Style Config
#   Status: PhD Level (Adaptive Design)
# ==============================================================================

class FormatterCore:
    def __init__(self):
        print("[FORMATTER] Initializing Adaptive Display Engine v1.1...")
        self.style_file = "formatter_styles.json"
        self.styles = {
            "default": {
                "speaker_color": "#FFD700", # Emas
                "text_color": "#FFFFFF",    # Putih
                "bg_color": "rgba(0,0,0,0.8)",
                "font_family": "Segoe UI, Arial"
            },
            "alert": {
                "speaker_color": "#FF4444", # Merah
                "text_color": "#FFDDDD"
            }
        }
        self.last_load = 0
        self._load_styles(force=True)

    def _load_styles(self, force=False):
        if not os.path.exists(self.style_file): return
        try:
            mtime = os.path.getmtime(self.style_file)
            if not force and mtime <= self.last_load: return
            
            with open(self.style_file, 'r') as f:
                self.styles = json.load(f)
            self.last_load = mtime
        except: pass

    def render(self, packet):
        """Mengubah Packet Data menjadi HTML Cantik"""
        self._load_styles() # Cek apakah ada update style?
        
        speaker = packet.get('speaker')
        text = packet.get('translation_final')
        tags = packet.get('context_tags', [])
        
        # Pilih Style berdasarkan Konteks (Evolusi Situasional)
        # Jika Sociologist bilang "Angry" atau "Combat", pakai style Alert
        current_style = self.styles["default"]
        if "Angry" in tags or "Combat" in tags:
            if "alert" in self.styles:
                current_style = self.styles["alert"]

        # Render HTML
        spk_html = ""
        if speaker:
            spk_color = current_style.get("speaker_color", "#FFD700")
            spk_html = f"<b style='color:{spk_color}; font-size:1.1em;'>{speaker}</b><br>"
        
        txt_color = current_style.get("text_color", "#FFFFFF")
        font = current_style.get("font_family", "Arial")
        
        # Bungkus Final
        html = f"""
        <div style='font-family:{font};'>
            {spk_html}
            <span style='color:{txt_color};'>{text}</span>
        </div>
        """
        return html