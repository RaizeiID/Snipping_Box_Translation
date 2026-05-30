# Migrasi ke ORT Translation v7.6

1. Extract ZIP v7.6 sebagai folder baru.
2. Jalankan `Start_ORT_Translation.bat`.
3. Untuk cache lama:
   - Salin `translation_memory.json` lama ke root folder v7.6.
   - Jalankan `python tools/migrate_legacy_cache.py`.
   - Setelah migrasi, arsipkan/hapus `translation_memory.json` dari root v7.6.
4. Untuk Fast Engine penuh:
   - Jalankan `pip install -r requirements_fast_optional.txt` pada runtime Python ORT.
   - Letakkan model CT2 en-id di `models/ct2_opus_mt_en_id`.
   - Cek dari Runtime & Tools.
5. Untuk V4 Online Assist:
   - Edit `online_assist_config.json` atau set env `ORT_ONLINE_*`.
   - Gunakan Test Online Assist dari Runtime & Tools.

## Setelah v7.6

Update berikutnya sebaiknya kembali changed-files-only, kecuali Anda meminta full folder lagi.
