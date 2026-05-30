# TITAN_DEBUG_MAIN.py (DEPRECATED)
# ==============================================================================
# This file used to contain an old debug snipper UI.
# To keep the project synchronized, it now launches TITANMAIN.py (full feature set),
# including CAS + hotkeys.
# ==============================================================================
import TITANMAIN as tm

def main():
    if hasattr(tm, "main") and callable(tm.main):
        return tm.main()
    if hasattr(tm, "run") and callable(tm.run):
        return tm.run()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
