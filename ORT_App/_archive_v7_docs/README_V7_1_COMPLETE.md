# ORT Translation v7.1 Complete

Versi ini adalah paket lengkap v7.1 yang dirapikan dari v7. Fokusnya bukan menambah UI besar, melainkan membersihkan arsitektur dan membuat file-file `*Core.py` yang relevan benar-benar ikut bekerja di runtime.

## Cara menjalankan

Jalankan:

```bat
Start_ORT_Translation.bat
```

Jalur utama produksi:

```text
Start_ORT_Translation.bat
→ webui.py
→ launcher_backend.py
→ model_registry.py + v7_system_profile.py
→ TITANMAIN.py
→ v71_runtime_bridge.py
→ core aktif yang relevan
```

## Perubahan utama v7.1

- Menambahkan `v71_runtime_bridge.py` sebagai penghubung aman untuk core lama/eksperimen.
- Mengaktifkan core relevan untuk preprocessing, throttle, cache, memory vault, QA, terminology, dan telemetry.
- Menjaga UI box terjemahan tetap dari `TITANMAIN.py`, sehingga desain utama tidak diubah.
- Menurunkan risiko game berat dengan adaptive throttle berbasis `ResourceSentinelCore` dan `AdaptiveThrottleCore`.
- Menambahkan status `v71_core_status.json` saat runtime berjalan.
- Mengarsipkan dokumen/launcher/patch lama ke `_archive_v6_legacy` agar root folder tidak ambigu.
- Menambahkan `_tools/audit_py_usage_v71.py` untuk audit file Python.
- Memperbarui requirements dan memecah optional requirements.

## Core aktif

Lihat `V7_1_ACTIVE_ENGINEERS.md` untuk daftar insinyur aktif dan insinyur yang diparkir.

## Catatan penting

Beberapa core sengaja tidak dijalankan langsung di loop produksi karena dapat menambah beban, membutuhkan dependency eksternal, atau bisa mengubah UI box yang sudah dikunci. Core tersebut tidak dihapus, tetapi diparkir dan dijelaskan alasannya.
