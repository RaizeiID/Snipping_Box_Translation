# ORT Translation v7.4 — Stability & Runtime Control Patch

Versi ini adalah patch lanjutan dari v7.3. Fokusnya bukan menambah model baru, melainkan menutup celah stabilitas runtime agar model, cache, online assist, dan stop process bekerja lebih aman.

## Perubahan utama

1. **Graceful Stop**
   - WebUI tidak langsung melakukan hard kill.
   - WebUI membuat stop request file.
   - `TITANMAIN.py` membaca request tersebut, menghentikan worker, flush cache, menutup session log, lalu keluar.
   - Jika proses tidak berhenti dalam timeout, WebUI baru memakai hard-kill fallback.

2. **Runtime Health Closed Loop**
   - `runtime_health_applier.py` sekarang memberi directive lebih lengkap:
     - OCR resolution dinamis.
     - force CPU OCR.
     - disable online assist saat pressure.
     - temporary fast mode hint saat queue/latency tinggi.
     - restore hint bertahap.

3. **V4 Online/Offline Hybrid Router**
   - `translation_engine.py` sekarang memakai `OnlineAssistRouter` untuk V4/hybrid.
   - Offline tetap menjadi utama.
   - Online assist hanya membantu bila endpoint tersedia dan runtime tidak berat.
   - Router memakai timeout dan circuit breaker.

4. **Scoped Cache Pruning**
   - `cache_store.py` menambahkan batas entries/file size.
   - Cache noise UI/OCR pendek tidak disimpan.
   - Legacy `translation_memory.json` tetap read-only warmup.

5. **Legacy Cache Migration Tool**
   - `tools/migrate_legacy_cache.py` membantu memindahkan `translation_memory.json` lama ke scoped cache per game/model.

6. **Diagnostic & Benchmark v7.4**
   - Dashboard membaca status baru:
     - `v74_runtime_actions.json`
     - `v74_cache_status.json`
     - `v74_online_assist_status.json`
     - `v74_translation_engine_status.json`
     - `v74_shutdown_status.json`
     - `v74_session_log_status.json`
   - `benchmark_runtime.py` membuat `v74_benchmark_report.json` dan `.txt`.

## Cara pasang

Extract ZIP patch ini ke root folder ORT Translation v7.3 lalu overwrite file lama.

## Catatan

Patch ini tidak mengubah UI box terjemahan utama. Perubahan difokuskan ke runtime, stop, cache, router online, dan diagnostic.
