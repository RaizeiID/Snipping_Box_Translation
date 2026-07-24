ORT Translation v6.6 Patch 1

Fokus patch ini:
1. UI Pengolahan Data dibuat ramah user awam.
2. Kandidat nama/istilah baru dicatat sementara saat OCR/log berjalan.
3. Setelah Stop, kandidat bisa langsung dikonfirmasi atau di-skip.
4. Blacklist kata ditambahkan.
5. Stop dibuat hard-stop agar OCR tidak perlu di-spam.

File baru/berubah:
- webui.py
- launcher_backend.py
- data_processing_backend.py
- data_processing_store.json
- data_processing_settings.json
- runtime_candidates.json

Catatan:
- Patch ini sengaja tidak mengubah indikator mode/engine/game yang sudah rapi di v6.5.
- Kandidat baru diproses di tab Pengolahan Data.
- Nama dan istilah memakai warna berbeda. Warna yang sama tidak diizinkan.
