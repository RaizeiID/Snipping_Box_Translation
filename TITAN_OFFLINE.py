# TITAN_OFFLINE.py
import sys
import atexit

import TITANMAIN as tm

from glossarycore import GlossaryCore
from titan_traininglog import TrainingLogCore
from titan_offline_translator import OfflineTranslatorCore


def main():
    log = getattr(tm, "log", lambda s: print(s, flush=True))
    base_dir = getattr(tm, "BASE_DIR", None) or __import__("os").path.dirname(__file__)

    glossary = GlossaryCore(base_dir, log)
    trainer = TrainingLogCore(base_dir, log, buffer_size=25)

    original_translate = tm.offline_translate_ram
    original_save_cache = tm.save_cache

    offline = OfflineTranslatorCore(base_dir, log, fallback_translate=original_translate)

    def wrapped_translate(text: str) -> str:
        masked, ph_map = glossary.protect_source(text)
        out = offline.translate(masked)
        out = glossary.apply_placeholders(out, ph_map)
        out = glossary.post_replace(out)

        try:
            trainer.record("OFFLINE", src=text, norm=masked, out=out, meta={"engine": "ct2_or_argos"})
        except Exception:
            pass
        return out

    def wrapped_save_cache(reason="manual"):
        try:
            original_save_cache(reason)
        finally:
            glossary.flush(f"save_cache:{reason}")
            trainer.flush(f"save_cache:{reason}")

    tm.offline_translate_ram = wrapped_translate
    tm.save_cache = wrapped_save_cache

    @atexit.register
    def _flush_all():
        try:
            wrapped_save_cache("atexit")
        except Exception:
            pass

    log("[TITAN_OFFLINE] Offline translator active + glossary + training_log")

    if hasattr(tm, "main") and callable(tm.main):
        return tm.main()
    if hasattr(tm, "run") and callable(tm.run):
        return tm.run()

    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    controller = tm.Controller(app) if tm.Controller.__init__.__code__.co_argcount > 1 else tm.Controller()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
