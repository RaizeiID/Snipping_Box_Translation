# ORT Translation v8.8.2 — Runtime Behavior Refactor

## Fokus
v8.8.2 melanjutkan v8.8.1. v8.8.1 merapikan struktur folder/GitHub; v8.8.2 mulai memperbaiki perilaku runtime yang sebelumnya terlihat terlalu gelisah pada Auto Story.

## Perubahan utama
1. **Auto Smooth**: mengurangi flicker dengan coalescing update kecil dari OCR progresif.
2. **Freeze OCR Override**: Freeze dapat menaikkan OCR ke 100% karena mode ini bersifat screenshot/manual dan tidak mengejar typewriter.
3. **Interval Stable/Story-aware**: Interval menjadi mode semi-stabil otomatis; cocok untuk user yang mematikan auto story game atau memanfaatkan jeda VA.
4. **Turn Transcript Accumulator**: menyimpan sumber terbaik per dialog agar final tidak berhenti di 20–90% kalimat.
5. **No-Downgrade Source Rule**: OCR yang lebih pendek/rusak tidak menggantikan source terbaik.
6. **Anti-Flicker Overlay Buffer**: hold/fragmen pendek mempertahankan overlay terakhir, bukan membuat blink.
7. **Speaker Prefix Sanitizer v3**: membersihkan duplikasi `Phaetusa(?)` dan pola sejenis dari body dialog.

## Yang tidak diubah
- Tidak mengganti engine utama.
- Tidak menambah model berat di preview.
- Tidak mengaktifkan Argos story sebagai fallback default.
- Tidak mengubah struktur GitHub-safe v8.8.1.

## Cara apply
Ekstrak patch ini di atas folder `ORT_Translation_v8_8_1` / branch v8.8.1 R3, pilih overwrite/replace.
