# ORT v8.9.9 R2 F2 — Long-Turn Context & Japanese Accuracy Fix

## Scope

Hotfix ini mempertahankan nomor versi v8.9.9. Basis pemasangan adalah v8.9.9 R2 F1.

## Runtime changes

- Satu speaking turn dipertahankan sampai endpoint silence; rolling audio window tidak lagi membuat `segment_id` baru.
- Rolling window: Speed 8 detik, Normal 12 detik, Accurate 16 detik.
- Context assembler menyimpan maksimal 240 kata dan mengirim display window 56/72/92 kata.
- GPU Japanese Specialist memakai search beam yang lebih lebar daripada English, dengan final beam lebih tinggi daripada partial.
- Jeda singkat dipertahankan melalui endpoint 460/620/760 ms.
- Final kosong memakai last useful partial sebagai final context fallback.
- Previous final mendapat grace 1,8 detik bila turn baru belum mempunyai empat kata bermakna.

## Compatibility

- Model dan runtime GPU R2 tidak perlu dipasang ulang.
- Azure credential dan runtime cloud tidak diubah.
- CPU Normal mempertahankan batas inference pendek agar tetap responsif.
