ORT v6.5 - Small Patch (Mode / Engine / UI)

Isi patch ini dibuat ulang sebagai patch kecil karena link patch sebelumnya tidak bisa diunduh.
Patch ini fokus ke inti perubahan yang diminta:
1. Menyimpan preferensi user dari WebUI
2. Meneruskan mode dan engine dari WebUI ke engine legacy lewat ENV
3. Menyediakan helper untuk popup loading/toast dan tombol Exit

Cara pakai:
- Ekstrak ZIP ini ke folder ORT_Translation_v6_5
- File di dalam patch ini bersifat tambahan / helper kecil
- Gunakan isi snippet untuk menimpa atau menambahkan ke file v6.5 Anda:
  - webui.py
  - launcher_backend.py
  - TITANMAIN.py
  - TitanMainV1.py
  - TitanMainV2.py

File yang disediakan:
- webui_prefs.py
  Helper baca/simpan preferensi user di runtime aktif
- legacy_boot_patch.py
  Helper baca preset mode/engine dari ENV untuk engine lama
- ui_toast_patch.js
  Contoh toast/loading pojok kanan atas
- example_webui_integration.py
  Contoh integrasi WebUI untuk save prefs + tombol Exit merah + toast loading
- example_launcher_integration.py
  Contoh integrasi backend untuk pass ENV ke model

Catatan:
- Patch kecil ini aman untuk didownload dan ditimpa ringan.
- Kalau Anda ingin, langkah berikutnya saya bisa kirim paket penuh yang sudah langsung menyatu ke struktur v6.5 Anda.
