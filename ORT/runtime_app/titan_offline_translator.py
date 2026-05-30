# titan_offline_translator.py
import os
from typing import Callable


class OfflineTranslatorCore:
    """
    Offline translator:
    - Prefer CTranslate2 (kalau model tersedia)
    - Fallback ke offline_translate_ram bawaan TITANMAIN (Argos)
    """

    def __init__(self, base_dir: str, log_fn: Callable[[str], None], fallback_translate: Callable[[str], str]):
        self.log = log_fn
        self.fallback_translate = fallback_translate

        self.ct2 = None
        self.ct2_translate = None

        en_id_dir = os.path.join(base_dir, "models", "ct2_opus_mt_en_id")
        if os.path.isdir(en_id_dir):
            try:
                from fast_mt_core_ct2 import CT2Config, FastCT2Translator
                cfg = CT2Config(model_dir_en_id=en_id_dir, beam_size=1, device="auto")
                self.ct2 = FastCT2Translator(cfg)
                self.ct2.warmup()
                self.ct2_translate = self.ct2.translate
                self.log("[OFFLINE] Using CTranslate2 (ct2_opus_mt_en_id)")
            except Exception as e:
                self.log(f"[OFFLINE] CT2 init failed -> fallback Argos: {e}")
                self.ct2 = None
                self.ct2_translate = None
        else:
            self.log("[OFFLINE] CT2 model not found -> using Argos fallback")

    def translate(self, text: str) -> str:
        if not text:
            return ""
        if self.ct2_translate:
            try:
                return self.ct2_translate(text)
            except Exception:
                return self.fallback_translate(text)
        return self.fallback_translate(text)
