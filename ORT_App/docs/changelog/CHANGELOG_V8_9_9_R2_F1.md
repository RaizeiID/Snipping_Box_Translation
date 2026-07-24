# CHANGELOG — ORT Translation v8.9.9 R2 F1

## Hybrid Startup & Subtitle Continuity Fix

### Fixed
- Hybrid + Accurate + Japanese tidak lagi dipaksa ke CPU Guard hanya karena marker `validated_cuda_medium.json` belum ada. Marker Small hasil inferensi nyata dipakai sebagai baseline CUDA, lalu Kotoba melakukan preflight spesifik sebelum streaming.
- Runtime capture mengikuti GPU runtime ketika mode efektif GPU/Hybrid.
- Output `.` atau tanda baca tunggal tidak lagi masuk antrean penerjemah maupun menggantikan overlay.
- Pesan `[Terjemahan ditahan: ...]` tetap dicatat di log tetapi tidak menimpa subtitle terakhir yang berguna.
- Partial rolling yang hanya berubah sedikit digabung agar preview Inggris dan Indonesia lebih stabil.
- Spam `EMPTY,NO_SPEECH` dibatasi tanpa memperketat penerimaan dialog bermakna.

### Preserved
- Nomor versi tetap v8.9.9.
- GPU preflight nyata dan CPU fallback R2 tetap aktif.
- Partial pertama tetap dapat muncul segera; hotfix bukan final-only mode.

