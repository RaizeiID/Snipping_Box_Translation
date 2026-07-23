# ORT Translation v8.9.2

Rilis stabilisasi OCR dan overlay berbasis runtime v8.9.1.

## Perubahan utama

- Menambahkan Text-aware ROI Change Gate agar EasyOCR tidak terus dipanggil pada area dialog statis.
- Menambahkan satu OCR konfirmasi setelah perubahan untuk membedakan teks progresif dari teks stabil.
- Menggabungkan antrean progressive text sehingga frame terbaru menjadi sumber kerja aktif.
- Menambahkan `TurnStateMachine` dengan `turn_id` dan `generation_id` monotonik.
- Menolak hasil OCR/terjemahan lama pada setiap tahap sebelum commit overlay.
- Mempertahankan overlay lama sampai payload dialog baru siap, lalu menggantinya secara atomik.
- Clear hanya terjadi setelah dialog benar-benar tidak terdeteksi melewati debounce; tidak ada clear otomatis pada awal turn baru.
- Mengunci satu final commit per turn untuk mencegah hasil akhir berubah berulang kali.
- Menyatukan penulisan JSONL melalui writer dengan lock lintas thread dan proses.
- Menambahkan telemetry change gate, generation, stale drop, atomic swap, explicit clear, serta multi-final prevention.
- Menambahkan satu sumber identitas build melalui `build_info.py`.

## Bawaan profil

- Auto: static probe 15 detik dan stability confirmation 450 ms.
- Interval: static probe 8 detik.
- Freeze/manual: selalu dapat melewati gate dan static probe 900 ms sebagai cadangan.
- Mode Buffer tetap OFF secara default.
- Placeholder terjemahan dan ID waiting preview tetap tidak ditampilkan.

## Kompatibilitas yang dipertahankan

- Prediction Guard, UI/Dialog Filter, OCR repair, entity registry, dan CT2 routing v8.9.1.
- Pemisahan identitas Helen/Helena.
- Speaker/body separation serta label entity seperti Sweeper.
- Cache guard untuk OCR rusak atau terlalu pendek.

## Tidak termasuk

Mode Audio, VAD, Isolasi Suara, dan profil Speed/Normal/Accurate tidak termasuk dalam v8.9.2. Fitur tersebut tetap menjadi pekerjaan versi sesudah fondasi OCR/overlay stabil.
