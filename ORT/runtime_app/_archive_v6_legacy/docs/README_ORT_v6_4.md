
# ORT Translation v6.4

Fokus update ini:
- WebUI diganti menjadi ORT Translation v6.4.
- Dropdown model disederhanakan: hanya menampilkan nama model sederhana seperti ORTCore V4 Lite.
- Ada tombol **Kolom model** untuk memfilter **Model dasar / Lite / IDN**.
- Legacy V3 Option A/B/C dihapus dari registry dan paket v6.4.
- Shortcut dipusatkan ke `shortcut_config.json`; ESC exit default dimatikan.
- Pengaturan UI dipusatkan ke `ui_settings.json` dan `ort_ui_theme.json`.
- Ada halaman **Pengolahan Data** untuk mengelola nama tersimpan per game.
- Runtime custom dapat dipakai ulang; launcher akan menawarkan reuse `.venv` lama.

Catatan integrasi:
- Fondasi UI universal dan pengaturan shortcut sudah dipusatkan.
- V1/V2/TITANMAIN sudah dihubungkan ke konfigurasi shortcut bersama.
- Wrapper V3/V4/V5 dijalankan tanpa popup HUD tambahan agar tampilan model tidak lagi memunculkan pop-up kanan atas.
- Integrasi total renderer overlay legacy ke satu file masih tahap fondasi; perubahan besar berikutnya cukup diteruskan dari `ORTUnifiedUIBox.py` dan adapter terkait.
