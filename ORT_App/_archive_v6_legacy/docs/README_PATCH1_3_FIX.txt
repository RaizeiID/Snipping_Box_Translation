ORT Translation v6.6 Patch 1.3 Fix

Perbaikan utama:
- Model Browser kembali lengkap memakai registry dinamis dari file model yang benar-benar ada.
- Pengaturan Pengolahan diberi indikator/preview warna yang lebih jelas dan menarik.
- Kandidat baru lebih cerdas:
  * item yang sudah ada di daftar nama/kata khusus/blacklist/original tidak dicatat lagi
  * item yang sangat mirip juga diabaikan
  * frasa kalimat/noise seperti STABLE, MISS, DIALOG, HIT, atau potongan kalimat tidak dipromosikan lagi
- Tombol Reset Kandidat dan toggle reset otomatis tetap tersedia.
- Tombol Copy Live Log tetap tersedia.

File yang ditimpa:
- webui.py
- data_processing_backend.py
- model_registry.py
