# ORT Translation v8.8.1 R3 — Panduan Upload GitHub Aman

Dokumen ini dibuat untuk mencegah folder runtime/cache/log/model besar ikut terupload ketika proyek dibuka lewat VSCode.

## 1. Folder yang direkomendasikan dibuka di VSCode

Buka VSCode dari root project:

```text
D:\AI TRANSLATOR\ORT_Translation_v8_8_1
```

Jangan mulai repository dari:

```text
D:\AI TRANSLATOR\ORT_Translation_v8_8_1\ORT
```

Namun R3 tetap menyertakan `ORT/.gitignore` agar lebih aman bila Anda tidak sengaja membuka Git dari folder `ORT/`.

## 2. Folder yang tidak boleh masuk GitHub

Folder berikut bersifat lokal/berat/generated dan sudah diabaikan oleh `.gitignore`:

```text
ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/
ORT/runtime_app/ORT_Runtime/
ORT/runtime_app/.venv/
ORT/runtime_app/cache/
ORT/runtime_app/logs/
ORT/runtime_app/backups/
ORT/runtime_app/debug_bundles/
ORT/cache/
ORT/logs/
ORT/backups/
ORT/debug_bundles/
```

## 3. Cara upload lewat VSCode

1. Buka folder root `ORT_Translation_v8_8_1` di VSCode.
2. Pastikan file `.gitignore`, `ORT/.gitignore`, dan `.gitattributes` ada.
3. Buka Terminal di VSCode.
4. Jalankan:

```powershell
git init
git status
```

5. Pastikan folder besar seperti `_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD`, `ORT_Runtime`, `cache`, `logs`, dan `backups` tidak muncul di daftar file yang akan di-commit.

6. Tambahkan file source:

```powershell
git add .
git status
```

7. Jika aman, commit:

```powershell
git commit -m "Initial ORT Translation project structure"
```

8. Buat repository baru di GitHub, lalu ikuti instruksi GitHub:

```powershell
git branch -M main
git remote add origin https://github.com/USERNAME/NAMA_REPO.git
git push -u origin main
```

## 4. Jika folder besar sudah terlanjur muncul di Git

Jalankan:

```powershell
.\UNTRACK_LOCAL_RUNTIME_FROM_GIT.bat
```

Atau manual:

```powershell
git rm -r --cached ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD
git rm -r --cached ORT/runtime_app/ORT_Runtime
git rm -r --cached ORT/runtime_app/cache
git rm -r --cached ORT/runtime_app/logs
git rm -r --cached ORT/runtime_app/backups
git rm -r --cached ORT/runtime_app/debug_bundles
```

Lalu commit ulang `.gitignore`.

## 5. Cara paling aman: export source ZIP

Jalankan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Script ini membuat:

```text
ORT_GITHUB_SOURCE_EXPORT.zip
```

ZIP tersebut otomatis mengecualikan folder runtime/cache/log/backup/debug dan lebih aman untuk diupload manual ke GitHub.

## 6. Catatan penting

- `.gitignore` hanya bekerja untuk file yang belum pernah di-track Git.
- Jika file besar sudah pernah di-commit, harus dilepas dari tracking dengan `git rm --cached`.
- Jangan upload folder runtime/model besar ke GitHub biasa; gunakan release asset atau storage terpisah bila diperlukan.
