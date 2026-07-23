# ORT Translation v8.8.9 Changelog

## Nama patch
**Prediction Guard Activation, Full Translation Commit, and Anti-Stale Overlay Patch**

## Ringkasan
v8.8.9 tidak merombak tuning OCR 40–50% yang sudah membaik. Patch ini bekerja di atas pipeline OCR: entity repair, dialog lifecycle, coverage/final output, overlay commit, UI filtering, dan cache safety.

## Perubahan utama
1. **Prediction Guard v2**
   - Registry default naik ke `gfl2_entity_registry_v8_8_9.json`.
   - `Kenny` ditambahkan sebagai approved exact story speaker.
   - Alias typo seperti `bathildel`, `Bathildel`, `balthildel`, dan `Balthildel` diarahkan ke canonical alias-family `Balthilde` secara guarded.
   - Alias prefix sekarang bisa menjadi speaker/entity label, bukan hanya replacement body.
   - Exact `Heli`, `Helen`, dan `Helena` tetap dipisah.

2. **Prediction badge propagation fix**
   - `speaker_confidence_label`, `speaker_confidence_kind`, dan `prediction_events` diisi ke `ocr_meta`.
   - Log `[PREDICT v8.8.9]` menampilkan source, candidate, label, dan reason.

3. **Anti-stale new-turn behavior**
   - Saat turn baru terdeteksi, overlay tidak langsung repaint dialog lama.
   - Sistem menampilkan current OCR source preview sementara hingga final translation siap.
   - Translation hold dan commit-gate suppression pada turn baru memilih source-preview lebih dulu daripada last-good lama.

4. **Full Output Guard**
   - Output final yang coverage-nya terlalu rendah tidak lagi memicu hold/stale terus-menerus.
   - Guard memakai anchor output bila lebih lengkap, atau source-safe preview no-cache.
   - Yellow/Red/low-coverage preview tetap diblok dari cache/training.

5. **Manual Burst Detection**
   - Auto/Interval lebih tahan terhadap story yang diklik manual cepat.
   - Dialog panjang yang muncul sekaligus dapat langsung diproses tanpa menunggu stabilitas typewriter lama.

6. **UI Filter v3**
   - Filter fuzzy untuk Loading/Loadlng/Coadlng Resources, Challenge Mode, Part Supply, Story/Supply %, Damage Stats, rewards/progress text.

## Prinsip yang dipertahankan
- OCR 40–50% tidak dinaikkan paksa.
- Preview tetap ringan dan cepat.
- CT2 story tetap diutamakan; Argos bukan fallback default ketika CT2 tersedia.
- Prediction Guard bukan autocorrect semua kata, hanya registry entity/term/alias yang guarded.
