# ORT Translation v8.8.6 — Mandatory Final Commit, Temporal OCR Consensus, Mode Buffer

## Fokus
v8.8.6 adalah stabilization patch di atas v8.8.5. Targetnya mengurangi masalah hasil terjemahan tidak full, overlay stale, cache terlalu percaya OCR rusak, dan low-OCR churn tanpa membuat Auto Story terasa lamban.

## Perubahan utama
- Mandatory Final Commit v2: setiap turn punya deadline final agar preview tidak menjadi output terakhir.
- Temporal OCR Consensus final-lane only: consensus dari beberapa OCR frame terakhir tidak memblokir preview.
- Mode Buffer: checkbox eksperimental default OFF di bawah `Pilih Model`, dengan tooltip dan tombol `?`.
- Low-OCR Visual Rescue planner: mendeteksi frame OCR 40–45% yang tampak muddy/noisy dan menandainya untuk final-lane rescue/cache guard.
- Bad Cache Shield v2: lebih ketat pada cache final jika corruption score tinggi.
- Stale Overlay Limit telemetry: repaint last-good tetap ada, tetapi dipantau agar tidak menyembunyikan final miss.

## Prinsip performa
Preview tetap cepat. Consensus, buffer, dan final completeness bekerja di final lane atau hanya saat Mode Buffer ON.
