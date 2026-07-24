import warnings

# ==============================================================================
#   TITAN X - HELSINKI CORE v3.0 (OFFLINE ARGOS)
#   Divisi: ENGINE & LINGUISTICS
#   Tugas: Translasi offline (en->id) + bridge zh->en->id (untuk teks CN)
#   Catatan: sengaja tidak pakai torch (anti-crash).
# ==============================================================================

warnings.filterwarnings("ignore")

try:
    import argostranslate.package as argos_package
    import argostranslate.translate as argos_translate
except Exception:
    argos_package = None
    argos_translate = None


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in text)


class HelsinkiCore:
    def __init__(self):
        print("[HELSINKI] Initializing Offline Translator v3.0 (ARGOS)...")
        self.ready = False
        self._ensure_languages()

    def _ensure_languages(self):
        if not argos_package or not argos_translate:
            print("[HELSINKI] Argos not available; running in passthrough mode.")
            return

        try:
            installed = argos_translate.get_installed_languages()
            codes = {l.code for l in installed}
            if 'id' not in codes:
                argos_package.update_package_index()
                pkgs = argos_package.get_available_packages()
                for frm, to in [('en', 'id'), ('zh', 'en')]:
                    p = next((x for x in pkgs if x.from_code == frm and x.to_code == to), None)
                    if p:
                        argos_package.install_from_path(p.download())

            self.ready = True
            print("[HELSINKI] Engine Ready: Argos Offline")
        except Exception as e:
            print(f"[HELSINKI] Init error: {e}")
            self.ready = False

    def reload_device(self):
        # OCR GPU/CPU switch ada di TITANMAIN, bukan di translator.
        return "CPU (ARGOS)"

    def translate(self, text, context_tags=None):
        if not text:
            return ""
        if not self.ready or not argos_translate:
            return text

        try:
            if _has_cjk(text):
                temp = argos_translate.translate(text, 'zh', 'en')
                return argos_translate.translate(temp, 'en', 'id')
            return argos_translate.translate(text, 'en', 'id')
        except Exception:
            return text
