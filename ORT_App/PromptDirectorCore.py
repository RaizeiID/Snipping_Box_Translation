import json
import os

# ==============================================================================
#   TITAN X - PROMPT DIRECTOR CORE v1.0
#   Divisi: ENGINE OPS
#   Tugas: Menyusun Instruksi/Prompt untuk Mesin
# ==============================================================================

class PromptDirectorCore:
    def __init__(self):
        print("[PROMPT] Initializing Instruction Director...")
        self.config_file = "prompt_templates.json"
        self.templates = {}
        self._load_config(force=True)

    def _load_config(self, force=False):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.templates = json.load(f)
            except: pass

    def construct(self, text, context_tags=[]):
        """
        Menyusun input final untuk mesin.
        """
        self._load_config()
        
        # Jika ada tag konteks (misal: "Military", "Angry"), suntikkan ke prompt
        # (Fitur ini sangat efektif jika nanti pakai GPT/LLM)
        if context_tags:
            tags_str = ", ".join(context_tags)
            template = self.templates.get("context_injection", "[{tags}] {text}")
            return template.format(tags=tags_str, text=text)
            
        return text