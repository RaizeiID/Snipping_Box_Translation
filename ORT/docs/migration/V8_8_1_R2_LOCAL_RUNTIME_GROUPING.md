# v8.8.1 R2 — Local Runtime Grouping & GitHub Export Guide

Tujuan revisi R2 adalah membuat folder besar/lokal mudah dikecualikan ketika pengguna ingin membuat ZIP source atau upload ke GitHub.

## Folder yang boleh dikecualikan

```text
ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/
```

Folder ini disiapkan untuk runtime Python, model, cache, log besar, backup, debug bundle, dan file lokal lain yang tidak perlu ikut GitHub.

## Cara manual

Saat membuat ZIP manual, jangan centang folder:

```text
ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD
```

## Cara otomatis

Jalankan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Script akan membuat ZIP source dengan mengecualikan folder lokal/berat, cache, logs, backups, debug bundles, runtime Python, models, dan file sementara.

## Batas perubahan R2

R2 tidak mengubah OCR, translation engine, scheduler, Auto/Freeze/Interval behavior, atau cache namespace. R2 hanya memperbaiki struktur packaging agar lebih nyaman untuk ZIP/GitHub.
