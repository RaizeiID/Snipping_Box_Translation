# ORT Translation v8.9.2-R2

## Guided & Expert UI Refresh

Rilis ini memperbaiki hierarki halaman utama tanpa mengubah mesin OCR dan overlay v8.9.2.

### UI utama

- Alur halaman menjadi Persiapan → Sumber terjemahan → Workspace.
- OCR dan Audio tampil pada kontrol utama dan selalu saling eksklusif.
- Basic menjaga UI minimal.
- Terpandu menampilkan rekomendasi dan pilihan model yang relevan.
- Expert membuka kontrol model, capture, engine, interval, resolusi, policy, runtime, hardware, dan diagnostic.
- Live Log dan AI Recap berada di panel lipat.

### Audio

- Audio mudah ditemukan melalui pilihan `Audio · Preview`.
- Preview memperlihatkan rancangan Normal, VAD, Isolasi Suara, Speed, Normal, dan Accurate.
- Backend Audio belum tersedia pada rilis ini.
- Tidak ada tombol start Audio yang aktif dan tidak ada proses palsu.
- Memilih Audio menghentikan OCR aktif untuk menjaga eksklusivitas sumber.

### Preserved

- Text-aware ROI Change Gate.
- Turn/generation state dan stale-result guard.
- Atomic overlay swap, explicit clear, dan single-final lock.
- Atomic JSONL writer.
- Mode Buffer OFF secara default.
