# TITAN_ONLINE.py
import os
import sys
import atexit
import inspect
from datetime import datetime

import TITANMAIN as tm

from glossarycore import GlossaryCore
from titan_traininglog import TrainingLogCore
from titan_online_translator import OnlineTranslatorCore


WRAPPER_NAME = "TITAN_ONLINE"
WRAPPER_VERSION = "v1.0"
ENGINE_INFO = "Online HTTP Translator (LibreTranslate-style) + Fallback Offline + Glossary + TrainingLog"
BEST_FOR = "Kualitas lebih natural jika endpoint online kamu lebih cerdas; tetap aman karena ada fallback offline."
DATA_FILES = [
    "translation_memory.json",
    "npc_database.json",
    "unique_terms.json",
    "punctuation_stats.json",
    "glossary.json",
    "training_log.jsonl",
]


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _fallback_log(msg: str):
    print(f"[{_ts()}] {msg}", flush=True)


def _get_log():
    return getattr(tm, "log", _fallback_log)


def _call_save_cache(save_fn, reason: str):
    try:
        sig = inspect.signature(save_fn)
        if len(sig.parameters) == 0:
            return save_fn()
        return save_fn(reason)
    except Exception:
        # last resort
        try:
            return save_fn()
        except Exception:
            return None


def _start_titanmain():
    """
    Start TITANMAIN tanpa merusak kompatibilitas versi.
    """
    if hasattr(tm, "main") and callable(tm.main):
        return tm.main()
    if hasattr(tm, "run") and callable(tm.run):
        return tm.run()

    # Fallback: manual start (untuk variasi struktur)
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    if not hasattr(tm, "Controller"):
        raise RuntimeError("TITANMAIN.Controller tidak ditemukan.")
    Controller = tm.Controller
    try:
        # Controller(app) jika butuh argumen
        if Controller.__init__.__code__.co_argcount > 1:
            _ = Controller(app)
        else:
            _ = Controller()
    except Exception:
        _ = Controller()
    return app.exec_()


def _print_banner(log, base_dir: str):
    url = os.environ.get("TITAN_ONLINE_URL", "http://localhost:5000/translate")
    src = os.environ.get("TITAN_ONLINE_FROM", "en")
    dst = os.environ.get("TITAN_ONLINE_TO", "id")
    timeout = os.environ.get("TITAN_ONLINE_TIMEOUT", "2.5")

    os.system("cls" if os.name == "nt" else "clear")
    print(f"{WRAPPER_NAME} {WRAPPER_VERSION}")
    print("=" * 60)
    print(f"[{_ts()}] Engine   : {ENGINE_INFO}")
    print(f"[{_ts()}] Best for : {BEST_FOR}")
    print(f"[{_ts()}] Endpoint : {url}  ({src}->{dst}, timeout={timeout}s)")
    print(f"[{_ts()}] Shared data dir: {base_dir}")
    print("-" * 60)
    print("Shared learning files (dipakai semua mode):")
    for f in DATA_FILES:
        print(f" - {f}")
    print("-" * 60)
    print("Shortcuts & UI mengikuti TITANMAIN (sama persis).")
    print("=" * 60)
    print("")  # spacing


def main():
    log = _get_log()
    base_dir = getattr(tm, "BASE_DIR", None) or os.path.dirname(os.path.abspath(__file__))

    # Banner profesional sebelum TITANMAIN boot
    _print_banner(log, base_dir)

    # Setup cores (shared learning)
    glossary = GlossaryCore(base_dir, log)
    trainer = TrainingLogCore(base_dir, log, buffer_size=25)
    online = OnlineTranslatorCore(log)

    # Backup original functions
    original_translate = tm.offline_translate_ram
    original_save_cache = tm.save_cache

    def wrapped_translate(text: str) -> str:
        masked, ph_map = glossary.protect_source(text)
        try:
            out = online.translate(masked)
        except Exception as e:
            log(f"[ONLINE] translate fail -> fallback offline | err={e}")
            out = original_translate(masked)

        out = glossary.apply_placeholders(out, ph_map)
        out = glossary.post_replace(out)

        # training log ringan
        try:
            trainer.record("ONLINE", src=text, norm=masked, out=out, meta={"engine": "online_http"})
        except Exception:
            pass
        return out

    def wrapped_save_cache(reason: str = "manual"):
        # Panggil save_cache TITANMAIN dulu, lalu flush learning extra
        _call_save_cache(original_save_cache, reason)
        try:
            glossary.flush(f"save_cache:{reason}")
        except Exception:
            pass
        try:
            trainer.flush(f"save_cache:{reason}")
        except Exception:
            pass

    # Patch into TITANMAIN runtime
    tm.offline_translate_ram = wrapped_translate
    tm.save_cache = wrapped_save_cache

    @atexit.register
    def _flush_all():
        try:
            wrapped_save_cache("atexit")
        except Exception:
            pass

    # Marker log
    try:
        log(f"[MODE] Runtime -> {WRAPPER_NAME} ({WRAPPER_VERSION})")
    except Exception:
        pass

    # Start TITANMAIN (boot + shortcuts + logs tetap dari TITANMAIN)
    code = _start_titanmain()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
