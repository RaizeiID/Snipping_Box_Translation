ORT v6.5 - Small Patch Tahap 2

Patch kecil ini dibuat agar Anda tidak perlu merge manual dari helper patch kecil tahap 1.
Isi patch ini langsung menyediakan file inti untuk ditimpa ke folder ORT_Translation_v6_5:
- webui.py
- launcher_backend.py

Agar patch ini langsung bekerja, file helper berikut juga ikut disertakan:
- webui_prefs.py
- ui_toast_patch.js
- legacy_boot_patch.py

Tujuan patch:
1. Menyimpan preferensi user (engine/mode/game/model/interval)
2. Mengirim pilihan Engine dan Mode dari WebUI ke proses model lewat ENV
3. Menambahkan tombol Exit merah di pojok kanan atas
4. Menyediakan toast / popup loading saat Start ditekan
5. Menyediakan backend start/stop yang tidak menutup web server

Cara pakai:
1. Ekstrak ZIP ini ke folder ORT_Translation_v6_5
2. Pilih overwrite/replace
3. Pastikan patch helper tahap 1 boleh tertimpa file dari patch ini
4. Jalankan Start_ORT_Translation.bat lagi

Catatan:
- Patch ini adalah drop-in patch kecil untuk jalur v6.5.
- Jika struktur v6.5 Anda sudah berbeda jauh dari patch sebelumnya, mungkin masih perlu merge tambahan.
