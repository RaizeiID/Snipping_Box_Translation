# ORT v8.9.1 Handoff Addendum

v8.9.1 adalah hotfix setelah pengujian v8.9.0.

## Masalah yang ditangani
- v8.9.0 membuat output terasa lebih bersih, tetapi terlalu sering menampilkan ID waiting preview/placeholder sehingga terasa seperti masalah baru pada rekaman.
- `Sweeper` sudah ada di registry v8.9.0, tetapi launcher masih default ke registry v8.8.8-r2, sehingga `Sweeper` tidak terlabel Green di log.
- UI/battle/loading noise seperti `Coading Resources`, `Marionette Repalr`, `Marlonette Repalr`, dan mixed-script garbage masih masuk sebagai DIALOG.

## Keputusan
- Silent pending default lebih aman daripada menampilkan `Menerjemahkan dialog baru…` terlalu sering.
- Source English tetap tidak boleh tampil di overlay utama.
- Registry default harus selalu menunjuk versi terbaru.
- Setiap update wajib global search label versi lama dan registry path lama sebelum packaging.
