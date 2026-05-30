# ORT Translation v8.7.9 — Changelog dan Apply Notes

## Fokus Rilis
`Responsive Faithfulness & Turn-Safe Overlay` dibangun ulang dari runtime v8.7.8 yang diuji pengguna, menggunakan temuan audit log dan video POV yang tersimpan pada handoff proyek.

## Perubahan Inti
- **Trusted Preview**: preview CT2-only untuk subtitle progresif yang ditahan v8.7.8; tidak boleh masuk cache atau training.
- **Stable Final**: final tetap melalui faithfulness/completeness dan baru dapat tersimpan saat aman.
- **Hard Strict CT2 Story**: pada GFL2 saat CT2 tersedia, kegagalan/identity CT2 tidak lagi otomatis jatuh ke Argos untuk dialog story.
- **Turn-Safe Overlay**: progressive extension tidak berkedip; turn dialog baru membersihkan overlay lama.
- **Scene Exit Guard**: reward/map/menu UI seperti `Collect more to claim rewards` tidak diperlakukan sebagai dialog.
- **Semantic Fidelity Guard**: mendeteksi kehilangan negasi, entity, angka, aksi penting, dan omission umum; final IDN dapat fallback ke CT2 literal anchor.
- **Versi/UI**: title UI, version file, log backend, dan namespace cache diselaraskan ke v8.7.9.

## Kebijakan Data
Safe exact/role retained: Berryfield, Cocoon, Carmen, Another Unfamiliar Worker, Kalina, Farkas, Client. Kandidat seperti Blondie, DKRIN, NOMFA, Perslcarla, Beepy, Chief of Odesa, Municipal Broadcast, dan Zyevnadya/Yyevnadya tetap review-only. Vilyz, ARVITA ID, dan ATVITA ID tetap Commander per akun dan tidak masuk speaker global.
