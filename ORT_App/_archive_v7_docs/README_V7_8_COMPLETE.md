# ORT Translation v7.9 Complete Ready

v7.9 adalah package folder baru yang berfokus pada **Launcher, Session Telemetry & Final Cleanup**.

## Perubahan utama dari v7.6

1. Launcher `Start_ORT_Translation.bat` memakai `requirements.txt`, bukan `requirements_v6_2.txt`.
2. Optional dependency Fast/Online bisa dipilih saat bootstrap runtime.
3. Nama fungsi aktif lama seperti `v71_core_summary_text` diganti menjadi `core_summary_text`.
4. Wrapper bridge lama `v71/v72/v73/v75` tidak ada lagi di root; dipindahkan ke `_archive_v7_compat/`.
5. Online Assist V4 punya panel konfigurasi di Runtime & Tools:
   - enable/disable
   - provider
   - endpoint URL
   - API key opsional
   - timeout
   - save config
   - test connection
6. Config Online Assist disuntikkan ke environment proses runtime saat Start.
7. Structured session event log sekarang dipanggil langsung dari titik OCR/translation.
8. Ditambahkan `benchmark_session_report.py` untuk membaca log sesi nyata.
9. Ditambahkan `runtime_dependency_checker.py` untuk validasi dependency runtime.
10. Status aktif tetap canonical di folder `status/`.

## Catatan penting

- Data besar seperti `translation_memory.json` dan `training_log.jsonl` tidak disertakan.
- Cache aktif memakai scoped cache per game/model di folder `cache/`.
- Untuk membawa memory lama, gunakan `tools/migrate_legacy_cache.py`.
- UI box terjemahan, indikator utama, engine/mode/shortcut, dan daftar model tetap dipertahankan.

## Jalur utama

```text
Start_ORT_Translation.bat
↓
webui.py
↓
launcher_backend.py
↓
model_strategy.py + online_assist_config.py
↓
TITANMAIN.py
↓
runtime_bridge.py + runtime_actions.py + translation_engine.py
↓
status/ + logs/ + cache/
```
