# ORT Translation v7.3 — Runtime Execution & Model Optimization Patch

Versi ini adalah patch lanjutan dari v7.2. Fokusnya bukan menambah UI besar, tetapi membuat strategi v7.2 benar-benar dieksekusi saat runtime.

## Fokus utama

1. `runtime_health_applier.py`
   - Mengubah rekomendasi `runtime_health_manager.py` menjadi aksi nyata.
   - Dapat menurunkan OCR resolution runtime.
   - Dapat memaksa OCR CPU saat VRAM/CPU/RAM kritis.
   - Dapat menonaktifkan online assist sementara saat sistem berat.

2. `core_profile_manager.py`
   - Core/"insinyur" tidak aktif semuanya secara buta.
   - Fast, Lite, Safe Game, Quality, Hybrid, dan Natural punya komposisi core berbeda.
   - Core berisiko tetap diparkir dengan alasan jelas.

3. `cache_store.py`
   - Cache per game/model menjadi jalur utama.
   - `translation_memory.json` lama dibaca sebagai warmup, tetapi tidak ditulis ulang secara default.

4. `fast_model_manager.py`
   - Mengecek status Fast Engine.
   - Dashboard dapat membedakan `ACTIVE`, `FALLBACK_ARGOS`, atau `NOT_INSTALLED`.

5. `online_assist_router.py`
   - Online assist V4 dibuat timeout-bounded dan punya circuit breaker.
   - Offline tetap utama.
   - Online assist otomatis dipause saat runtime pressure.

6. `session_log_manager.py`
   - Log lengkap sesi disimpan ke folder `logs/`.
   - UI boleh menampilkan tail agar tidak berat, tetapi AI Recap membaca full session log bila tersedia.

7. `benchmark_runtime.py`
   - Tool manual untuk mengumpulkan status strategy/health/cache/Fast/online/session.

## File utama yang berubah

- `TITANMAIN.py`
- `launcher_backend.py`
- `webui.py`
- `translation_engine.py`
- `v72_runtime_bridge.py`
- `v73_runtime_bridge.py`
- `core_profile_manager.py`
- `runtime_health_applier.py`
- `cache_store.py`
- `fast_model_manager.py`
- `online_assist_router.py`
- `session_log_manager.py`
- `benchmark_runtime.py`

## Catatan penting

- UI box terjemahan utama tidak dirombak.
- Runtime & Tools tetap fokus ke runtime/GPU.
- V7.3 adalah patch changed-files-only. Extract/overwrite ke folder project v7.2 Anda.
- `translation_memory.json` lama tidak dihapus, hanya tidak ditulis ulang default agar tidak menyebabkan stutter.
