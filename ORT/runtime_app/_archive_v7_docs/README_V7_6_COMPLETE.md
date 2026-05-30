# ORT Translation v7.6 Complete Ready

v7.6 adalah **Cache, Benchmark & Runtime Cleanliness Patch** yang dibuat sebagai folder baru penuh dari v7.5.

## Fokus utama v7.6

1. **Legacy cache OFF default**
   - `translation_memory.json` besar tidak disertakan dan tidak dimuat otomatis.
   - Cache utama memakai scoped cache per game/model di folder `cache/`.
   - Migrasi manual tersedia lewat `python tools/migrate_legacy_cache.py`.

2. **Nama internal aktif dibersihkan**
   - Jalur aktif sekarang memakai `runtime_bridge.py`, `runtime_actions.py`, dan `status/` canonical.
   - File wrapper lama v71/v72/v73/v75 hanya kompatibilitas, bukan jalur aktif.

3. **Status runtime bersih**
   - Semua status ditulis ke `status/*.json`.
   - Tidak lagi memakai status aktif campur v72/v73/v74.

4. **Fast Engine Setup Wizard**
   - `fast_model_manager.py` sekarang memvalidasi dependency, folder, dan marker model CT2.
   - Runtime & Tools tetap bisa menyiapkan folder Fast Engine.

5. **Online Assist Config**
   - `online_assist_config.json` menjadi file konfigurasi user-friendly untuk V4 online/offline hybrid.
   - Wuthering Waves Safe Game tetap mematikan online assist secara default melalui strategi runtime.

6. **Benchmark lebih nyata**
   - `benchmark_real_translation.py` mencoba Argos asli jika tersedia.
   - `benchmark_cache_hit.py` menguji scoped cache.
   - Benchmark lama tetap ada sebagai smoke test.

7. **Session log lebih siap untuk AI recap**
   - Session log tetap menyimpan full log dan JSONL events.
   - Tambahan helper structured translation event tersedia.

## Catatan penting

File besar lama tidak disertakan:
- `translation_memory.json`
- `training_log.jsonl`

Jika Anda ingin membawa memory lama, salin manual file tersebut ke root v7.6 lalu jalankan migrasi cache.
