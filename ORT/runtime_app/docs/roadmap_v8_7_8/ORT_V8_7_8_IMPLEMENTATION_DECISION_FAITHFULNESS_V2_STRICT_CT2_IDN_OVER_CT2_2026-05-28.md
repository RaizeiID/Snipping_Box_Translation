# ORT Translation v8.7.8 — Implementation Decision
**Tanggal:** 28 Mei 2026  
**Basis:** Runtime v8.7.7 aktual, log gameplay/POV v8.7.7, audit semantic hallucination dan CT2.

## Tujuan Rilis
v8.7.8 memperketat keselamatan makna setelah v8.7.7 masih melewatkan output bertema tafsir/agama melalui variasi ejaan dan jalur Argos. Rilis ini tidak me-roll back keberhasilan CT2, EntitySpan, exact speaker, atau stable-commit, melainkan menambah lapisan yang memastikan output tidak setia tidak tampil, tidak dicache, dan tidak dijadikan data learning.

## Implementasi P0
1. **Faithfulness Gate v2** — normalisasi diakritik/apostrof/spasi menangkap `al-Qur 'ân`, `Qur’an`, `ayat`, `zakat`, `surat`, `neraka`, `kiamat`, `sekaratul maut`, `makkiyyah`, `mubtada`, pola tafsir `orang-orang yang`, dan injection lain bila tidak didukung source.
2. **Qur Corruption Quarantine** — bentuk OCR `Qur best`, `Qur reality`, dan `Qur division` diperbaiki terkontrol ke `our`; bentuk ambigu ditahan, bukan diterjemahkan sebagai konsep agama.
3. **Strict CT2 Story** — bila CT2 sudah aktif namun source progressive/noisy menyebabkan CT2 tidak memberi output aman, runtime menahan preview daripada jatuh ke `legacy_argos`/`mixed_ct2_legacy_argos`.
4. **IDN-over-CT2** — model IDN/Normal diarahkan memakai CT2 literal sebagai backend utama bila CT2 tersedia, lalu naturalization/QA/gate; Argos hanya fallback terbatas.
5. **Final-only Safe Commit** — model akurasi menahan source progressive awal dan output coverage rendah agar overlay final tidak diganti fragmen buruk.
6. **Unsafe QA Fallback Fix** — output Argos yang sudah ditolak QA tidak dikembalikan ke overlay; marker internal rejection ditangkap dan ditahan oleh TranslationEngine.
7. **Telemetry Safety Lengkap** — evaluation/event/report/debug bundle membawa status faithfulness, flags, Qur quarantine, strict CT2 hold, backend fallback reason, coverage, dan keputusan cache/training.

## Nama, Role, Alias, dan Term
### Penambahan exact-only / role exact
- `Kalina` — named story speaker exact-only; alias ROI-only `Kallna`, `Kalin`, `Kalna`.
- `Farkas` — named story speaker exact-only setelah bukti prefix log v8.7.7; tetap dipantau di live test.
- `Client` — approved role exact-only; alias ROI-only `Cllent`.

### Dipertahankan dari v8.7.7
- `Berryfield`, `Cocoon`, `Carmen`, `Another Unfamiliar Worker`.

### Review-only, tidak auto-live
- `Chief of Odesa` dari `Chief of Odega`/`Chlef Odesa`.
- `Municipal Broadcast` sebagai narration/source label candidate.
- `Zyevnadya`/`Yyevnadya` sebagai identity review prioritas tinggi; jangan otomatis dipetakan ke `Dushevnaya`.

### Term baru
- `Satellite City`.
- `ODE-01 Municipal Center`.

### Commander yang dikecualikan global
- `Vilyz`, `ARVITA ID`, `ATVITA ID` hanya boleh aktif sebagai `user_configured_commander` per profile/account.

## Kemandirian Sistem yang Aman
Program tidak boleh auto-promote kandidat speaker/term dari OCR mentah karena false speaker dan cache contamination pernah terbukti. v8.7.8 menambahkan `Candidate Miner` yang mengumpulkan kemunculan berulang dari log untuk panel review/manual approval. Dengan demikian sistem membantu menemukan data baru secara semi-otomatis, sedangkan keputusan aktivasi tetap aman dan dapat diaudit.

## Keputusan v9.0
Rilis v9.0 harus diberikan sebagai **ZIP proyek utuh** pada folder baru, bukan hanya patch. Struktur akan dirapikan untuk GitHub: root seminimal mungkin berisi launcher/shortcut `Start OCR` dan `Runtime`, sedangkan source, app, tools, configs, docs, assets, models/data runtime, logs/cache/backups, tests, dan migrations ditempatkan dalam folder terorganisasi. Migration plan dan master handoff wajib dibawa agar data/user setting serta seluruh fungsi v8.x tidak hilang.
