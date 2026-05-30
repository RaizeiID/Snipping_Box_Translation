# ORT Translation v7.2 Complete Ready

Versi ini adalah refactor besar dari v7.1 dengan fokus utama: **model benar-benar punya strategi berbeda**, bukan hanya beda nama di UI.

## Hal baru v7.2

1. `model_strategy.py`
   - Mengubah pilihan model menjadi kontrak runtime nyata.
   - Mengatur engine, OCR resolution, interval, queue, CPU thread, cache scope, core profile, postprocess level, QA level, dan online policy.

2. `translation_engine.py`
   - Memisahkan mesin terjemahan dari `TITANMAIN.py`.
   - Mendukung cache per game/model, Fast CT2 opsional, V4 online/offline assist dengan timeout pendek, dan fallback Argos.

3. `runtime_health_manager.py`
   - Memantau CPU/RAM/VRAM/queue/latency.
   - Memberi rekomendasi sleep/OCR/force CPU saat beban tinggi.

4. `v72_runtime_bridge.py`
   - Bridge core/insinyur sekarang membaca model strategy.
   - Core aktif disesuaikan dengan profil: fast, safe_game, balanced, quality, natural.

5. Dashboard v7.2
   - Ada Diagnostic Dashboard untuk melihat model strategy, runtime health, dan core bridge.

## Identitas model v7.2

- Normal V1 = ringan
- Normal V2 = balanced/default
- Normal V3 = akurasi tinggi
- Normal V4 = offline-first + online assist timeout pendek
- Normal V5 = naturalisasi presisi
- Lite = hemat resource untuk game berat
- IDN = naturalisasi Bahasa Indonesia
- Lite IDN = hemat + naturalisasi ringan
- Fast = latency rendah, cache-first, postprocess minimal

## Catatan penting

- UI box terjemahan utama tetap tidak dirombak.
- Indikator ping/ms/game/engine tetap dijaga.
- Wuthering Waves default diarahkan ke Safe Game, tetapi normal override tetap tersedia.
- CT2/Fast dan Online Assist bersifat opsional; jika dependency/model tidak ada, sistem fallback ke Argos offline.
