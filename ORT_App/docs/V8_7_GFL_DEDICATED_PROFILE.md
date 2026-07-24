# ORT Translation v8.7 — GFL Dedicated Dialogue Profile & OCR Contamination Guard

## Tujuan Update

v8.7 merupakan rilis penuh untuk folder baru. Fokusnya adalah memperkenalkan profil khusus **Girls' Frontline (GFL seri pertama)** yang tidak lagi diproses sebagai `GFL2_EXILIUM`. Dasar perubahan berasal dari hasil pengujian pengguna: panel dialog GFL memiliki elemen tetap di kanan bawah berupa ikon/label `GFsystem` dan garis kuning, sehingga OCR membaca token sampah berulang seperti `gFn`, `ngf`, `nifn`, `ni5e`, dan `nfe`.

## Implementasi Utama

1. **Game Profile Baru: `GFL`**
   - Opsi `Girls' Frontline (GFL)` ditambahkan ke pilihan game.
   - Profil menerapkan pengaturan khusus GFL, terpisah dari GFL2 Exilium.

2. **GFL Dialogue Layout Resolver**
   - Menggunakan bounding box hasil OCR untuk membedakan kandidat area nama pembicara di kiri atas dan isi dialog.
   - Hanya kandidat nama yang cocok dengan daftar aman/roster GFL yang diterima sebagai speaker.
   - Narasi tanpa nama tidak lagi boleh mempromosikan kata pertama menjadi NPC.

3. **GFsystem/Footer Mask**
   - Hanya area tetap kanan bawah kotak dialog yang dimask; baris dialog bagian bawah lainnya tetap tersedia.
   - Footer token juga dibersihkan pada jalur teks untuk menahan variasi OCR yang lolos dari mask visual.

4. **Dialogue Presence Guard dan Credit Guard**
   - Guard visual konservatif menahan frame non-dialog setelah kegagalan deteksi berulang, agar ending/menu/credit tidak mencemari OCR/learning.
   - Filter teks menolak marker kredit seperti `GAME DESIGN`, `SUNBORN`, `CHARACTER VO`, dan `TRUE ENDING`.

5. **Speaker Learning Quarantine GFL**
   - Nama yang valid seperti `AK-12`, `AN-94`, `Dandelion`, dan `Tokarev` dapat dikenali dari ROI aman.
   - Kata narasi/credit seperti `Familiar`, `Conference`, `Official`, `Programming`, dan `Sunborn` diblokir dari pembelajaran otomatis.

6. **Seeded Glossary GFL**
   - Program memuat daftar awal nama dan istilah yang berkeyakinan tinggi untuk membantu speaker gate dan koreksi OCR.
   - Kamus ini sengaja konservatif, bukan daftar seluruh karakter tanpa verifikasi; pengguna tetap dapat menambah/meninjau nama dari WebUI.

7. **Perbaikan Cache All-MISS**
   - Untuk profil GFL, cache menggunakan teks yang telah dibersihkan dari footer/noise dan dinormalisasi.
   - Prefix dialog sangat pendek yang masih sedang mengetik tidak mengisi cache secara berlebihan.
   - Ini mengatasi sumber fragmentasi cache; cache hit aktual tetap harus diverifikasi setelah dialog berulang dimainkan kembali.

8. **Analyze Last Session v8.7**
   - Laporan menambahkan hitungan footer artifact GFL, teks credit/non-dialog, frame/teks yang ditahan Scene Guard, cache, dan rekomendasi profile.

## Cara Menggunakan Profil GFL

1. Ekstrak ZIP v8.7 sebagai folder baru.
2. Jalankan aplikasi seperti biasa.
3. Pada pilihan game, pilih **Girls' Frontline (GFL)**, bukan `Girls' Frontline 2 Exilium`.
4. Snip kotak dialog GFL dengan tetap memasukkan teks dialog; v8.7 akan mem-mask sudut kanan bawah `GFsystem` secara otomatis.
5. Untuk tes awal, gunakan **Lite IDN V3** sebagai profil seimbang.
6. Setelah sesi selesai, buka **Analyze Last Session** dan cek artifact/suppression/cache/engine.

## Prioritas Validasi Setelah Rilis

- Pastikan token `gFn/ngf/nifn/ni5e/nfe` jauh berkurang atau tidak muncul pada teks terjemahan.
- Pastikan credit/ending tidak lagi menambah NPC palsu.
- Pastikan dialog speaker `AK-12`, `AN-94`, dan `Dandelion` terbaca benar.
- Ulangi dialog yang sama untuk mengukur apakah cache mulai HIT setelah teks bersih.
- Jangan menyimpulkan kecepatan Fast/Lite apabila applied engine masih `argos_offline` akibat CT2 fallback.
