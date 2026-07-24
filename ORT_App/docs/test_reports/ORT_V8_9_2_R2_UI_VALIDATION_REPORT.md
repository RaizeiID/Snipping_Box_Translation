# ORT v8.9.2-R2 UI Validation Report

**Tanggal:** 23 Juli 2026  
**Basis:** ORT Translation v8.9.2  
**Ruang lingkup:** WebUI utama, eksklusivitas sumber, identitas versi, dan regresi runtime yang diwarisi.

## Hasil

| Pemeriksaan | Hasil |
|---|---|
| Kompilasi 303 file Python | PASS |
| Regression UI v8.9.2-R2 | PASS |
| Regression inti v8.9.2 | PASS |
| Regression hotfix v8.9.1 | PASS |
| Sinkronisasi VERSION/ORTCORE/TITANCORE/build info | PASS |
| OCR/Audio saling eksklusif pada UI | PASS |
| Start guard menolak Audio preview | PASS |
| Basic/Terpandu/Expert visibility contract | PASS |
| Audio unavailable state tidak menyesatkan | PASS |
| CSS responsive dan transition contract | PASS |

## Kontrak yang divalidasi

- Tab utama bernama `Mulai`.
- Pemilih sumber selalu menampilkan `OCR · Siap` dan `Audio · Preview`.
- Beralih ke Audio memperbarui UI segera dan menghentikan OCR melalui worker latar belakang.
- Workspace OCR dan Audio tidak pernah ditampilkan sebagai runtime aktif bersamaan.
- Tombol mulai Audio tidak interaktif.
- Basic/Terpandu tidak menampilkan seluruh kontrol teknis.
- Expert menampilkan advanced OCR controls, runtime summary, hardware, performance policy, dan diagnostic.
- Runtime OCR, overlay, cache, registry, dan telemetry v8.9.2 tidak diubah.

## Batas validasi lingkungan

Lingkungan validasi Linux tidak menyediakan paket Gradio/browser GUI, sehingga rendering interaktif penuh tidak dijalankan di sini. Kontrak komponen, event, CSS, sintaks, dan wiring diuji secara statis; uji visual akhir tetap perlu dilakukan ketika WebUI dibuka pada runtime Windows pengguna.
