# ORT Translation v8.8.1

**Release type:** Full project folder / structural refactor  
**Focus:** folder cleanup, launcher UX, GitHub-ready layout, and compatibility bridge.  
**Runtime behavior:** based on v8.7.9 Responsive Faithfulness & Turn-Safe Overlay. OCR/translation behavior is intentionally not refactored yet; that is planned for v8.8.2.

## Cara menjalankan

Untuk pengguna biasa, buka:

```text
START_HERE.bat
```

Pilihan utama:

1. **Buka WebUI / App Manager** — membuka dashboard ORT.
2. **Jalankan OCR Overlay** — memakai runtime terakhir yang sudah dikonfigurasi.
3. **Setup / pilih Runtime Python** — digunakan pertama kali atau saat runtime pindah folder.
4. **Buka folder logs** — melihat log runtime terbaru.
5. **Buka README** — membuka panduan ini.

## Struktur baru

```text
ORT_Translation_v8_8_1/
├── START_HERE.bat
├── Start WebUI.bat
├── Start OCR.bat
├── Runtime.bat
├── README.md
├── CHANGELOG.md
├── VERSION.txt
├── .gitignore
└── ORT/
    ├── runtime_app/        # Runtime aktual v8.8.1, kompatibel dengan struktur lama
    ├── docs/               # Dokumentasi, handoff, roadmap, migration map
    ├── user_data/          # Placeholder data aktif pengguna untuk struktur masa depan
    ├── logs/               # Placeholder log eksternal
    ├── cache/              # Placeholder cache eksternal
    ├── backups/            # Placeholder backup eksternal
    └── debug_bundles/      # Placeholder debug bundle eksternal
```

## Kenapa masih ada `ORT/runtime_app/`?

v8.8.1 adalah **structural refactor tahap aman**. File runtime lama tetap dipertahankan utuh di `ORT/runtime_app/` agar import/path lama tidak rusak. Root folder sudah bersih dan launcher baru mengarahkan pengguna ke runtime yang benar.

Refactor perilaku seperti Auto Smooth, Freeze OCR 100%, Interval Stable, Dialogue State Machine, dan Overlay Anti-Flicker ditargetkan untuk **v8.8.2** setelah struktur v8.8.1 stabil.

## Catatan GitHub

Paket lokal ini masih dapat menyertakan runtime/config kecil agar tetap mudah dipakai. Untuk upload GitHub publik, gunakan `.gitignore` yang sudah disediakan agar cache, logs, backup, debug bundle, runtime Python, dan data aktif tidak ikut terunggah.

## Update dari v8.7.9

- Root folder dibuat bersih.
- Launcher pengguna dipusatkan di root.
- Runtime lama dipindahkan ke folder terstruktur `ORT/runtime_app/`.
- Dokumentasi/handoff proyek disalin ke `ORT/docs/handoff/`.
- File generated lama seperti logs/cache/backups dibersihkan dari paket v8.8.1.
- Struktur awal GitHub-ready disiapkan.


## v8.8.1 R2 - Folder lokal besar dibuat satu tempat

Jika di laptop Anda ada folder/file besar seperti runtime Python, model, cache lokal, hasil log besar, backup, atau file web/runtime lokal yang tidak ingin ikut saat membuat ZIP/GitHub, kumpulkan semuanya di:

```text
ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/
```

Folder ini sengaja dibuat sebagai area lokal yang mudah dikecualikan. Saat Anda membuat ZIP manual untuk GitHub, cukup jangan centang folder tersebut. Untuk export source yang lebih aman, gunakan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Catatan: `ORT/runtime_app/` tetap berisi runtime aplikasi yang diperlukan oleh launcher agar program tetap berjalan. Folder `_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD` ditujukan untuk file besar/lokal seperti environment, model, cache, backup, log besar, dan export pribadi yang tidak perlu dibagikan.


---

## GitHub Safe Upload

v8.8.1 R3 menyertakan perlindungan agar folder runtime/cache/log/model besar tidak ikut terupload ke GitHub.

File penting:
- `.gitignore`
- `ORT/.gitignore`
- `.gitattributes`
- `EXPORT_GITHUB_SOURCE.bat`
- `CHECK_GITHUB_READY.bat`
- `UNTRACK_LOCAL_RUNTIME_FROM_GIT.bat`
- `ORT/docs/user_guide/GITHUB_UPLOAD_GUIDE_V8_8_1_R3.md`

Untuk upload paling aman, jalankan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Lalu upload ZIP `ORT_GITHUB_SOURCE_EXPORT.zip` ke GitHub atau gunakan Git dari root folder project.

