# ORT Translation v8.7.7 — Audit Pengujian Log + POV dan Roadmap Perbaikan Berikutnya
**Tanggal audit:** 28 Mei 2026  
**Basis:** log v8.7.7 dari berbagai model, ZIP runtime `ORT_Translation_v8_7_7.zip`, dan rekaman POV yang dilampirkan pengguna.  
**Status:** Analisis profesional dan roadmap perbaikan; belum merupakan patch runtime.

## 1. Kesimpulan Eksekutif

v8.7.7 memperbaiki beberapa masalah penting:
- CT2 kini benar-benar aktif pada Lite/Lite IDN/Fast.
- Cache namespace baru `v8_7_7_faithful_complete_ct2_safe` aktif.
- Stable-commit mulai menahan source terlalu pendek lewat `hold=source_too_short_progressive`.
- Sebagian semantic hallucination berhasil diblok di event log.

Namun, pengujian terbaru membuktikan v8.7.7 belum sepenuhnya aman:
1. **Hallucination semantik masih lolos** pada beberapa output IDN/Argos, terutama varian yang tidak masuk daftar injection detector seperti `al-Qur 'ân`, `ayat`, `zakat`, dan pola tafsir.
2. **Job-level fallback ke `legacy_argos` / `mixed_ct2_legacy_argos` masih sering muncul** walaupun CT2 aktif, terutama pada source pendek, noise OCR, atau span tertentu.
3. **Normal/IDN V1/V5 masih memakai Argos Offline**, sehingga tetap menjadi jalur paling berisiko untuk hallucination.
4. **OCR 40% masih diagnostic**, bukan mode story aman; CT2 mempercepat backend tetapi tidak memperbaiki OCR mentah.
5. **Completeness gate mulai bekerja, tetapi masih perlu final-only safe commit** agar output partial/aneh tidak mudah tampil sebagai final.
6. **IDN evaluation belum mencatat metadata faithfulness/hold secara lengkap**, sehingga debug sulit memastikan kenapa output buruk lolos.

## 2. Bukti Perbaikan yang Berhasil

### 2.1 CT2 aktif pada Lite/Lite IDN/Fast
Log Lite IDN V2 menunjukkan:
```text
[TRANSLATION] Lite CT2 efficient engine active
[PIPE] ... engine=ct2_fast
```

Log Lite V2 dan Fast V1 juga menunjukkan CT2 aktif:
```text
[TRANSLATION] Lite CT2 efficient engine active
[TRANSLATION] Fast CT2 engine active
```

Ini membuktikan rebind CT2/SPM v8.7.7 berhasil dalam runtime live.

### 2.2 Stable-commit mulai menahan source terlalu pendek
Contoh event:
```text
[PIPE] hold=source_too_short_progressive | engine=held_preview
```

Ini menunjukkan `Dialogue Completeness / Stable Commit Gate` mulai bekerja, terutama untuk potongan seperti nama saja atau prefix pendek.

### 2.3 Semantic gate sebagian bekerja
Dalam event session v8.7.7 ditemukan beberapa `SEMANTIC_HALLUCINATION_BLOCKED`, misalnya output bertema `AL-MURSALAT` atau `Quran` dari source yang tidak mendukung. Ini menandakan konsep gate sudah benar, tetapi cakupan deteksinya belum cukup.

## 3. Masalah P0: Hallucination Masih Lolos

### 3.1 Contoh hallucination yang lolos ke final/evaluation

Dari `idn_evaluation_v8_7_7.jsonl`, ditemukan output seperti:

```text
Source:
tel that We have managed to gather suggests that the order comes from above, from

Output:
(1) Ayat ini mengisyaratkan suatu fakta ilmiah yang belum ditemukan
pada saat diturunkannya al-Qur 'ân...
```

Contoh lain:

```text
Source:
Thank you very much for your help. and Will do Qur best to cooperate with you in

Output:
Terima kasih banyak atas bantuanmu. (Dan orang-orang yang terhadap zakat mereka menunaikannya) membayarnya.
```

Masalah ini membuktikan bahwa daftar injection detection v8.7.7 masih terlalu sempit.

### 3.2 Akar penyebab

`faithfulness_gate.py` sudah mendeteksi kata seperti:
```text
nabi
quran / qur'an / alquran / koran
mekah
luth
syuaib
malaikat
kafir
mukmin
al-masyariq
```

Tetapi output nyata memakai bentuk yang belum tertangkap:
```text
al-Qur 'ân
ayat
zakat
surat
neraka
kiamat
sekaratul maut
makkiyyah
mubtada
pola tafsir: "orang-orang yang ..."
```

Selain itu, OCR `Qur` dari `your/our` masih dapat memicu output aneh seperti `Al-Rahasia`, `Informan Kepemilikan Al`, atau tafsir religius.

## 4. Masalah P0: CT2 Aktif, tetapi Legacy Argos Masih Masuk

Walaupun CT2 aktif, log v8.7.7 masih memuat:
```text
engine=legacy_argos
engine=mixed_ct2_legacy_argos
```

Contoh masalah:
```text
[22:46:13] [PIPE] cache=MISS | 2357ms | engine=mixed_ct2_legacy_argos | backend=2269ms
```

Contoh lain:
```text
[22:55:21] [PIPE] cache=MISS | 1213ms | engine=legacy_argos
```

Dampak:
- latency spike;
- risiko hallucination kembali karena Argos adalah backend yang sebelumnya terbukti menghasilkan output mengada-ngada;
- mixed engine membuat debugging sulit karena satu dialog dapat separuh CT2 dan separuh Argos.

## 5. Masalah P0/P1: Normal/IDN Masih Argos Offline

Normal V1/V5 pada v8.7.7 tetap menggunakan profile offline/Argos:
```text
engine_policy=offline
Argos models OK
engine=argos_offline
```

Model IDN/Normal seharusnya menjadi model paling akurat, tetapi bila backend utama masih Argos, maka risiko hallucination tetap tinggi. Solusi yang disarankan adalah arsitektur **IDN-over-CT2**:
```text
CT2 literal translation
→ IDN naturalization / polish
→ faithfulness gate
→ stable commit
```

Argos hanya boleh menjadi fallback terakhir yang sangat dibatasi.

## 6. Masalah P1: OCR 40% Tetap Tidak Layak Story

Fast V1 dan Lite V1 memakai OCR 40%, CT2 aktif, tetapi raw OCR masih sangat rusak:
```text
Vew Too hve Ueen LlAIMILR
ayllng Commanderl
Krollk Nenesls Su she Hah?Youvegotn
```

CT2 mempercepat translation, tetapi tidak memperbaiki OCR mentah. Maka:
- 40% tetap diagnostic/ultra-speed;
- 45% adalah adaptive minimum;
- baseline story aman tetap 50–55%;
- model IDN sebaiknya tidak turun agresif di bawah baseline ketika user mengutamakan akurasi.

## 7. Masalah P1: Evaluation/Telemetry Belum Cukup untuk Audit

`idn_evaluation_v8_7_7.jsonl` belum mencatat field seperti:
```text
faithfulness_allowed
faithfulness_reason
semantic_flags
overlay_hold
hold_reason
coverage_score
fallback_backend_reason
cache_allowed_after_gate
```

Akibatnya, ketika output buruk lolos, debugging harus dilakukan manual dari source/cache/event. v8.7.8 perlu menambahkan field ini pada setiap `TRANSLATION_RESULT`, `FINAL_OVERLAY`, dan `IDN_EVALUATION`.

## 8. Rekomendasi Update Berikutnya: v8.7.8 atau v8.7.7.1

### P0-A — Faithfulness Gate v2
- Tambahkan regex untuk varian `al-Qur 'ân`, `Qur 'an`, `al Qur an`, `Qur’an`, dan bentuk diakritik.
- Tambahkan indikator tafsir:
  `ayat`, `zakat`, `surat`, `neraka`, `kiamat`, `sekaratul maut`, `makkiyyah`, `mubtada`, `orang-orang yang`.
- Buat mode `semantic_suspect_output` untuk output yang terlalu bernuansa kitab/tafsir meski tidak memuat kata `nabi`.
- Output suspect tidak boleh tampil, cache, memo, training, atau eval final.

### P0-B — Qur Corruption Quarantine
Jika source OCR memuat bare `Qur`, `Qur best`, `Qur ownership`, `Qur secret`, `Qur reality`, jangan langsung diterjemahkan. Terapkan:
- normalisasi konteks ke `your` atau `our` bila pola mendukung;
- bila tidak yakin, tahan preview dan tunggu frame stabil;
- jangan biarkan token `Qur` memicu output religius.

### P0-C — Disable Argos for Progressive/Noisy Snippets
Saat CT2 aktif:
- `legacy_argos` tidak boleh dipakai untuk source pendek/noisy/progressive;
- jika CT2 gagal pada source pendek, lebih baik `held_preview` daripada fallback Argos;
- `mixed_ct2_legacy_argos` harus diberi reason event dan bisa dimatikan via setting `strict_ct2_story`.

### P0-D — IDN-over-CT2
Untuk IDN/Normal:
- gunakan CT2 literal sebagai backend utama;
- Argos hanya fallback terakhir setelah CT2 benar-benar gagal;
- IDN naturalization menjadi post-process, bukan mengganti backend ke Argos.

### P0-E — Final-only Safe Commit untuk Mode Akurasi
Untuk IDN/Normal dan Lite IDN:
- jangan tampilkan preview yang belum stabil sebagai final;
- tampilkan overlay lama yang aman atau status kecil “menunggu kalimat stabil”;
- final baru muncul saat source stabil dan coverage cukup.

### P1 — OCR/Name Improvements
- Tambahkan alias ROI-only/review:
  `Krollk→Krolik`, `Nenesls/Nemesls→Nemesis`, `Zyevnadya/Yyevnadya→Dushevnaya?` dengan review visual, `Kallna/Kalin→Kalina`, `Cllent→Client`, `Chlef→Chief`.
- Jangan apply alias ke body dialog secara bebas.

### P1 — Telemetry & Debug Bundle
Tambahkan field gate/fallback ke:
- `IDN_EVALUATION`;
- `FINAL_OVERLAY`;
- session event;
- debug bundle;
- test ledger.

## 9. Nama/Term Tambahan yang Muncul pada v8.7.7

### Perlu review/metadata
```text
Sharkry
Makiatto
Springfield
Centaureissi
Farkas
Sextans
Chief Odesa
Municipal Broadcast
Kalina
Dandelion
```

### Alias OCR kandidat
```text
Krollk → Krolik
Nenesls / Nemesls → Nemesis
Kallna / Kalin → Kalina
Cllent → Client
Chlef → Chief
QDE-01 → ODE-01
GrOZy / Grozy → Groza
Zyevnadya / Yyevnadya → review untuk Dushevnaya atau nama lain sesuai visual
```

## 10. Keputusan Profesional

v8.7.7 tidak gagal total. Update ini berhasil mengaktifkan CT2 dan menambahkan fondasi semantic/stable gate. Namun, untuk kualitas yang aman bagi user non-English, v8.7.7 masih perlu patch lanjutan karena:
- hallucination masih bisa lolos;
- Argos masih muncul di job tertentu;
- IDN/Normal belum memakai CT2 sebagai backend utama;
- OCR 40% tetap menghasilkan noise berat;
- telemetry gate belum cukup rinci.

Prioritas patch berikutnya adalah **v8.7.8 Faithfulness v2 + Strict CT2 Story + IDN-over-CT2**.
