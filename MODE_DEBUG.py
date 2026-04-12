import os
import sys
import traceback

# ==============================================================================
#   TITAN X - MODE_DEBUG v1.0
#   Tujuan:
#   - Mode debug: mengimpor & menginisialisasi semua core
#   - Jika ada error di salah satu core (typo/import), laporkan nama file/core
#   - Jika semua OK, rekomendasikan menjalankan TITANMAIN.py
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print('TITAN X - MODE_DEBUG v1.0')
    print('==============================================')
    print('[DEBUG] Scanning & syncing all cores...')

    errors = []

    # 1) Try Nexus orchestration load (closest to real run)
    try:
        from NexusCore import Brain
        brain = Brain(strict=False)
    except Exception as e:
        errors.append(('NexusCore', str(e), traceback.format_exc(limit=6)))
        brain = None

    # 2) Import every *.py (catch SyntaxError etc.)
    for fn in sorted(os.listdir(BASE_DIR)):
        if not fn.endswith('.py'):
            continue
        if fn in {'TITANMAIN.py'}:
            continue
        mod_name = fn[:-3]
        try:
            __import__(mod_name)
        except Exception as e:
            errors.append((fn, str(e), traceback.format_exc(limit=6)))

    # 3) If Brain exists, validate core init status
    if brain is not None:
        for core, info in brain.core_status.items():
            if info.get('status') == 'ERROR':
                errors.append((f"{core}Core.py", info.get('error',''), ''))

    print('\n==============================================')
    if errors:
        print(f'[RESULT] FAILED: {len(errors)} issue(s) detected.')
        for i, (src, msg, tb) in enumerate(errors, 1):
            print(f"\n#{i} -> {src}")
            print(f"   Error: {msg}")
            if tb:
                print('   Trace:')
                for line in tb.splitlines()[-10:]:
                    print('    ', line)

        print('\n[RECOMMENDATION] Fix core errors above, then run MODE_DEBUG again.')
        print('[NOTE] Setelah semua OK, jalankan: TITANMAIN.py')
        sys.exit(1)

    print('[RESULT] ALL CORES OK ✅')
    print('[RECOMMENDATION] Jalankan kode utama: TITANMAIN.py')
    sys.exit(0)


if __name__ == '__main__':
    main()
