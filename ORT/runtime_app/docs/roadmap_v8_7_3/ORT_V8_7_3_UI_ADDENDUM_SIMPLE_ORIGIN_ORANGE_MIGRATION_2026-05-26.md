# ORT Translation v8.7.3 — UI Addendum: Orange Simple-Origin Name & Category Migration
**Tanggal:** 26 Mei 2026  
**Status:** Diimplementasikan pada source v8.7.3

## Keputusan UI
Nama speaker/karakter/NPC approved yang ditambahkan melalui **Tampilan Sederhana** disimpan sebagai entity valid tetapi belum disortir, dengan origin `unsorted_protected` / `simple_view`.

Saat halaman berpindah ke Mode Normal/Detail:
- entity asal Tampilan Sederhana ditampilkan sebagai item **orange**;
- user dapat mengklik item tersebut untuk memilihnya dan menjalankan aksi **Hapus** atau **Migrasi Nama**;
- migrasi menempatkan entity utuh ke kategori rinci sesuai game, tanpa perlu menghapus lalu mengetik ulang.

Entity yang sudah berada pada kategori detail ditampilkan sebagai item kategori normal/hijau:
- dapat dipilih dengan klik untuk penghapusan/edit;
- tidak menawarkan migrasi asal-Sederhana karena kategorinya sudah final.

## Compound Entity
Aksi selection/delete/migration bekerja untuk entity penuh, bukan token terpisah:
- `Alya Kujou`
- `URNC Leader`
- `M4 SOPMOD II`
- `Descender Zero`

## Kategori Tujuan Migrasi
- GFL2: Character/Doll, Commander/User Configured, NPC/Role Speaker.
- WUWA: Playable Resonator, Story NPC/Approved Role.
- GFL: T-Doll; Karakter Penting/Griffin & Allies; Karakter Faksi Cerita — Paradeus; Karakter Faksi Cerita — Sangvis Ferri; NPC/Role.

## Regression Acceptance
- nama yang ditambah pada mode Sederhana terlihat orange di mode Normal;
- item orange dapat dipilih dan dimigrasi;
- setelah migrasi, item berubah menjadi kategori tersortir/hijau;
- item kategori tersortir menolak aksi migrasi asal-Sederhana;
- aksi tidak memecah nama multi-kata.
