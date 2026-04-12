Patch ORT Translation v6.5 - Mode / Engine / Popup / Remember Settings

File yang ditimpa:
- webui.py
- launcher_backend.py
- TitanMainV1.py
- TitanMainV2.py
- TITANMAIN.py

Perubahan:
1. Mode dan engine dari WebUI sekarang diteruskan ke mesin model.
   - Engine: CPU / GPU / Hybrid-Auto
   - Mode: Auto / Freeze / Interval
2. Pengaturan launcher diingat di runtime aktif:
   - model group
   - model terakhir
   - game
   - mode
   - engine
   - default interval
   - interval ms
3. Tombol Exit dipindah ke pojok kanan atas dengan warna merah.
4. Popup loading Start dibuat sebagai toast pojok kanan atas.
5. Basis engine lama (V1, V2, dan TITANMAIN untuk V3-V5) sekarang membaca preset WebUI saat boot.

Cara pakai:
- Ekstrak patch ini ke folder ORT_Translation_v6_5
- Pilih overwrite / replace
- Jalankan ulang Start_ORT_Translation.bat

Catatan:
- File preferensi launcher akan tersimpan otomatis di runtime aktif sebagai webui_prefs.json
- Popup loading hilang segera setelah proses model berhasil diluncurkan
