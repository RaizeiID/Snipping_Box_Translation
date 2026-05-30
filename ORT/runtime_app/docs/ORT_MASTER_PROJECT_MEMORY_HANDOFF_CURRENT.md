# ORT TRANSLATION / ORTCORE — MASTER PROJECT MEMORY & CONTINUITY HANDOFF
## Current Continuity Document: v8.7.9 and Forward
**Tanggal pembaruan dokumen:** 29 Mei 2026  
**Pemilik proyek:** Diska Kurnia  
**Status:** Dokumen induk pemulihan konteks setelah Memory ChatGPT dihapus/dikosongkan  
**Peran dokumen:** Menjadi sumber kontinuitas proyek yang ikut disertakan pada paket update berikutnya

---

# 0. INSTRUKSI PALING PENTING UNTUK CHATGPT PADA OBROLAN BARU

Apabila pengguna mengunggah dokumen ini setelah Memory ChatGPT dibersihkan, lakukan hal berikut:

1. Baca dokumen ini terlebih dahulu sebelum mengusulkan update ORT.
2. Minta atau baca ZIP runtime/patch/log/video terbaru yang pengguna masih miliki bila pekerjaan membutuhkan modifikasi atau evaluasi aktual.
3. Perlakukan dokumen ini sebagai **riwayat keputusan, diagnosis, dan kontrak pengembangan**, bukan bukti bahwa semua fitur masih aktif pada runtime terbaru.
4. Jangan mengklaim log/video mentah lama masih tersedia hanya karena hasil analisisnya tercatat di dokumen ini.
5. Untuk perbaikan baru, selalu bandingkan kebutuhan akurasi dengan latency, queue, VRAM, dan kelancaran overlay—terutama pada Model Lite dalam Auto Story.
6. Jangan membuat update dengan menambah lapisan safety berat di jalur preview real-time tanpa pengukuran performa.
7. Bila sistem mulai makin kompleks, makin sulit diuji, atau hasil update menjauh dari ekspektasi pengguna, prioritaskan **refactoring terkontrol** sebelum menambah patch baru.
8. Setiap update berikutnya wajib membawa dokumen master ini yang telah diperbarui di folder dokumentasi/handoff, beserta changelog, manifest, known issues, test report, dan checksum.

## Cara pengguna memulihkan konteks setelah memory reset

Unggah minimal:
- file master handoff ini;
- ZIP runtime/patch terbaru yang masih dimiliki;
- log/live log/video POV terbaru bila meminta diagnosis hasil pengujian.

Tanpa ZIP atau log/video asli, ChatGPT masih dapat memahami arsitektur dan keputusan proyek dari dokumen ini, tetapi tidak boleh mengaku dapat memulihkan byte ZIP lama, log mentah, atau rekaman asli yang sudah terhapus.

---

# 1. IDENTITAS, TUJUAN, DAN KONTEKS PENGGUNA

## 1.1 Nama dan fungsi proyek

Nama proyek: **ORT Translation / ORTCore / TitanCORE Translator**

Fungsi utama:
- penerjemah dialog game real-time berbasis OCR;
- menampilkan hasil terjemahan Bahasa Indonesia melalui overlay;
- menyediakan WebUI untuk memilih game, model, mode, engine, OCR profile, diagnostic, data identity/terminology, dan tools pemeliharaan;
- menjaga agar story dapat dibaca mengikuti dialog game tanpa stutter yang mengganggu.

Game yang menjadi fokus uji terbaru:
- **Girls' Frontline 2: Exilium / GFL2_EXILIUM** untuk pengujian story terbaru;
- **Girls' Frontline / GFL** telah memiliki profile tersendiri sejak v8.7.

## 1.2 Hardware utama pengguna

Perangkat kerja utama yang telah digunakan sebagai konteks tuning:
- Acer Predator Helios Neo PHN16-71;
- Intel Core i7-13700HX;
- NVIDIA RTX 4050 Laptop GPU, 6 GB VRAM;
- RAM 64 GB;
- Windows.

Konsekuensi desain:
- Game berat dapat menyisakan VRAM sangat kecil bagi OCR/translation.
- Model Lite/Lite IDN bukan sekadar mode “murah”, tetapi jalur penting agar overlay tetap lancar ketika game menggunakan resource besar.
- Optimasi tidak boleh hanya berorientasi kualitas final; pengalaman Auto Story real-time menjadi syarat utama.

## 1.3 Preferensi kerja pengguna yang wajib dipertahankan

- Pengguna biasanya menguji langsung di game lalu mengirim log, ZIP runtime, screenshot, dan/atau video POV.
- Pengguna menginginkan analisis profesional sebelum update.
- Update minor umumnya dikirim sebagai **changed-files ZIP** di atas baseline runtime sebelumnya.
- Update besar, khususnya v9.0, harus berupa **full project ZIP dalam folder baru** yang rapi dan GitHub-ready.
- UI/fitur yang sudah berfungsi tidak boleh dirombak sembarangan tanpa alasan dan validasi.
- Semua perubahan penting harus mempunyai catatan, test result, known issues, rekomendasi berikutnya, serta master handoff terkini.

---

# 2. KONTRAK PRODUK YANG TIDAK BOLEH DILANGGAR

Bagian ini adalah keputusan pengguna yang harus menjadi aturan tetap untuk update setelah 29 Mei 2026.

## 2.1 Kontrak kelancaran Auto Story

Tujuan utama ORT bukan hanya menerjemahkan dengan benar, tetapi **mengikuti alur dialog story secara halus**. Pada GFL2 Auto Story, teks terjemahan harus bergerak mengikuti dialog/baris yang muncul, tanpa terasa tertahan atau tersendat.

Aturan wajib:
- Akurasi/anti-hallucination tidak boleh dicapai dengan membuat overlay lambat atau beku.
- Penambahan gate/lapisan safety tidak boleh otomatis ditempatkan sebelum preview tampil.
- Preview harus ringan dan cepat.
- Pemeriksaan berat hanya boleh berjalan pada stable final atau jalur non-real-time.
- Update yang lebih akurat tetapi membuat story lebih tersendat harus dianggap **gagal** atau harus dinonaktifkan pada mode cepat/Lite.

## 2.2 Kontrak Model Lite

Model Lite dipakai untuk:
- game berat dengan sisa VRAM kecil;
- pengguna yang mengutamakan respons cepat;
- GFL2 sekalipun ketika pengguna menginginkan pengalaman story lebih lancar.

Karena itu:
- Lite preview tidak boleh memanggil pemeriksaan berat atau model tambahan secara default.
- Lite harus menjadi **performance gate** setiap update: bila fitur baru membuat Lite stutter, fitur tersebut harus ditolak, dipindah ke final-only, atau diberi toggle terpisah.
- Argos story tidak boleh digunakan sebagai fallback default bila CT2 tersedia.
- Logging berat, candidate mining, migration, cache scan, dan debug export tidak boleh berjalan pada jalur utama overlay.

## 2.3 Kontrak anti-hallucination yang seimbang

- Output tidak faithful harus ditolak atau diganti dengan jalur aman.
- Namun jalur aman harus dirancang bertingkat: CT2 preview cepat → CT2 literal/final safe → source-safe bila perlu, bukan hold berlebihan.
- Jangan menyelesaikan semantic drift umum hanya dengan memperbesar blacklist kata.
- Faithfulness perlu menangani entity, negasi, angka, aksi, coverage, scene, dan turn synchronization.

## 2.4 Kontrak refactoring

Jika patch mulai membuat program makin kacau, semakin kompleks, sulit diuji, atau menjauh dari ekspektasi:
- hentikan penambahan fitur besar;
- pilih baseline paling sehat;
- bangun replay cases;
- mulai refactoring terkontrol untuk dialogue pipeline, policy engine, OCR/scene classification, cache/data, dan UI;
- jangan melakukan rewrite total tanpa compatibility bridge dan rollback.

---

# 3. ARSITEKTUR KONSEPTUAL ORT YANG PERLU DIPAHAMI

Pipeline umum:
```text
Screen Capture / ROI
→ OCR
→ OCR Normalization / Noise & Layout Guard
→ Speaker / Dialogue Classification
→ Scheduler / Progressive Text Handling
→ Translation Backend Policy (CT2 / fallback rules)
→ Preview or Final Commit Lane
→ Faithfulness / Fidelity Checks
→ Overlay Rendering
→ Cache / Learning / Telemetry / Diagnostics
```

File/modul historis penting:
- `TITANMAIN.py`: runtime OCR/overlay/translation utama; masih besar dan menjadi kandidat refactor.
- `webui.py`: WebUI/Dashboard/Runtime & Tools.
- `launcher_backend.py`: menerjemahkan setting UI menjadi runtime/environment/status.
- `model_strategy.py`: strategi model/profile/engine dan tuning.
- `translation_engine.py`: terjemahan, cache, backend path, IDN/policy.
- `runtime_bridge.py`: bridge preprocessing/postprocessing dan quality control.
- `app/translation/faithfulness_gate.py`: gate semantic/injection pada versi akhir v8.7.x.
- `app/translation/dialogue_completeness_gate.py`: stabilitas/coverage/hold.
- `app/identity/speaker_registry.py`: speaker/identity trusted dan alias.
- `app/runtime/turn_safe_overlay.py`: baru pada rekonstruksi v8.7.9.
- `app/translation/semantic_fidelity_guard.py`: baru pada rekonstruksi v8.7.9.

Semantik mode yang tidak boleh diubah tanpa keputusan pengguna:
- **Freeze:** snapshot/manual untuk membaca scene dengan stabil.
- **Interval:** capture stabil secara berkala.
- **Auto / Auto Story:** story berjalan otomatis dan harus merespons teks bertahap tanpa menahan overlay terlalu lama.

---

# 4. RIWAYAT VERSI BESAR DAN KEPUTUSAN TERKUNCI

## 4.1 v8.0 — Foundation build
Arah:
- fondasi modular `app/`;
- Mode Pengaturan / rekomendasi sistem;
- Reset Live Log, Analyze Last Session, Reset Settings;
- profile resolver, safe mode guard, conflict detector;
- diagnostic GPU/Torch/CUDA;
- OCR noise normalizer, speaker candidate gate;
- prototype cache.

Keterbatasan:
- runtime utama masih besar;
- state dan stable commit belum sepenuhnya terstruktur.

## 4.2 v8.1 — WebUI/runtime integration
Perbaikan:
- exit UI/runtime lebih bersih;
- penghubung tombol diagnostics;
- requested vs effective runtime status;
- integrasi awal OCR normalizer/stable text committer.

## 4.3 v8.2 sampai v8.4.5 — Performance, Fast/Lite, dan UI maturity
Keputusan penting:
- Story Dialogue Scheduler dan Image Hash Gate dikembangkan.
- CT2 harus benar-benar aktif sebelum klaim speed Fast/Lite sah.
- Lite/Lite IDN dibuat untuk efisiensi GPU/VRAM.
- Preset historis Lite: V1 40%, V2 45%, V3 50%, V4 55%, V5 60%.
- Pada praktik berikutnya, OCR di bawah 50% terbukti terlalu berisiko untuk baseline story GFL2 tanpa rescue/benchmark.
- Number-Safe OCR mulai menangani noise angka, tetapi angka kecil/blur tetap memiliki batas OCR nyata.

## 4.4 v8.5 sampai v8.6 — Numeric OCR dan IDN Quality
v8.5/v8.5.2:
- numeric dual-pass/ROI-first;
- cache protection untuk garis yang kehilangan angka;
- Naturalized IDN Cache;
- GFL2 name alias normalizer;
- Lite telemetry requested vs applied;
- controlled online assist guard.

v8.6:
- Shared IDN Quality Layer untuk Fast IDN/Lite IDN/Normal IDN;
- mode Light/Balanced/Natural/Quality;
- terminology consistency;
- applied engine harus dibaca dari log, bukan disimpulkan dari policy requested.

## 4.5 v8.7 — Full project GFL profile
Tipe rilis:
- Full project/folder baru.

Tujuan:
- memisahkan profile `GFL` dari `GFL2_EXILIUM`;
- menangani panel dialog GFL yang memiliki footer/ikon `GFsystem`;
- mencegah OCR noise masuk cache dan speaker learning.

Implementasi penting:
- GFL layout resolver;
- footer mask/right-bottom artifact filter;
- dialogue/credit guard;
- speaker quarantine;
- seeded glossary;
- normalized/stable cache mitigation;
- diagnostic report GFL.

Pelajaran:
- profile game yang keliru adalah bug prioritas tinggi;
- false speaker dari narasi/credit/UI tidak boleh masuk data global.

## 4.6 v8.7.1 sampai v8.7.2 — Correctness, stable cache, observability
v8.7.1:
- Auto menjadi mode default keluarga model; Freeze/Interval tetap manual;
- GFL2 canonical seed `DP-12` dan `KSVK`;
- status applied backend lebih jujur;
- Legacy MemoryVault diisolasi;
- speaker gate/quarantine diperketat.

v8.7.2:
- Stable Final Cache v2 dan current-dialog memo;
- event cache seperti `CACHE_STORE_STABLE_FINAL`/`CACHE_HIT_STABLE_FINAL`;
- Speaker ROI/Name Pass v2 dan temporal speaker hold;
- text repair konservatif;
- IDN Evaluation Export;
- patch tidak menimpa data/prefs pengguna.

## 4.7 v8.7.3 sampai v8.7.5 — Official identity, EntitySpan, dan temuan OCR rendah
Perbaikan correctness yang tidak boleh di-rollback:
- `verified_character_speaker_exact`;
- backend-safe EntitySpan;
- residual internal-marker guard;
- cache namespace aman;
- pemisahan `Helen` dan `Helena`;
- compound speaker entity;
- stale-overlay guard;
- multi-game data/identity UI.

Audit v8.7.5 berdasarkan 11 live log dan 7 rekaman POV menyatakan:
- marker internal seperti `ORT_ENTITY`/`ORT_BKEND` tidak muncul kembali pada log yang diperiksa;
- label `Groza`, `Mayling`, `Colphne` terlihat bekerja saat OCR jelas;
- OCR di bawah 50% buruk sebagai baseline story GFL2 pada scene uji terbaru;
- Fast/Lite jatuh ke Argos karena CT2/SPM belum aktif, sehingga preset OCR rendah tidak menghasilkan manfaat backend cepat;
- belum ada bukti ilmiah bahwa algoritma Body OCR sengaja downgrade, karena scene/frame lintas versi belum diputar ulang identik.

Keputusan:
- perlu replay benchmark dari frame/video identik;
- UI harus jujur menampilkan preset/requested/applied/runtime rescue OCR dan applied backend.

## 4.8 v8.7.6 — Adaptive OCR, exact speaker gate, dan semantic hallucination terbukti
Audit berdasarkan 10 sesi log/event, 7 rekaman POV, dan ZIP runtime v8.7.6 mencatat:
- tidak ditemukan marker internal lama pada event/cache aktif yang diperiksa;
- exact-only fallback speaker gate bekerja dan memblok 175 calon false speaker;
- Adaptive OCR Readability Guard bekerja pada profile rendah;
- tetapi semantic hallucination serius lolos ke overlay/cache: dialog biasa berubah menjadi keluaran keagamaan/tafsir;
- CT2/SPM masih belum aktif untuk Lite/Fast; backend masih jatuh ke Argos.

Data speaker/term dari tahap ini:
- official observed tidak boleh diduplikasi;
- kandidat speaker/named NPC perlu klasifikasi exact-only/review;
- alias OCR hanya ROI-only;
- special terms perlu dipisahkan dari speaker;
- nama commander tidak boleh menjadi global roster.

## 4.9 v8.7.7 — CT2 recovery, stable commit, Faithfulness Gate awal
Implementasi/hasil audit:
- CT2 berhasil benar-benar aktif pada Lite/Lite IDN/Fast setelah masalah path/SPM ditangani;
- cache namespace `v8_7_7_faithful_complete_ct2_safe`;
- stable commit mulai menahan source progresif sangat pendek;
- beberapa hallucination semantic berhasil diblok.

Namun masalah masih ada:
- variasi output seperti `al-Qur 'ân`, `ayat`, `zakat`, `neraka`, atau pola tafsir belum seluruhnya tertangkap;
- job-level fallback `legacy_argos` / `mixed_ct2_legacy_argos` masih masuk saat source pendek/noisy/identity output;
- Normal/IDN tertentu masih memakai Argos Offline;
- completeness/faithfulness metadata belum cukup untuk menjelaskan semua output buruk.

## 4.10 v8.7.8 — Faithfulness v2 memperbaiki kelas agama, tetapi menyebabkan/menyisakan usability regression
Tujuan v8.7.8:
- normalisasi istilah injection/agama;
- Qur OCR quarantine/controlled repair;
- Strict CT2 Story lebih kuat;
- IDN-over-CT2;
- final-only safe commit;
- telemetry/cache rotation/candidate ledger.

### Temuan agregat enam live log v8.7.8

| Metrik | Nilai |
|---|---:|
| Total PIPE selesai | 3.186 |
| `engine=ct2_fast` | 2.345 |
| `engine=legacy_argos` | 249 |
| `engine=mixed_ct2_legacy_argos` | 66 |
| `engine=argos_offline` | 7 |
| Cache/current-dialog memo | 519 |
| Hold total | 1.530 |
| `accuracy_final_only_wait_stable` | 1.348 |
| Median PIPE | 127 ms |
| P95 PIPE | 293 ms |
| Maksimum PIPE | 3.924 ms |
| PIPE ≥500 ms | 11 |
| Queue maksimum | 3.633 ms |

Diagnosis:
- CT2 menjadi backend mayoritas dan relatif cepat.
- Stutter dirasakan karena terlalu banyak hold overlay dan spike fallback Argos.
- `strict_ct2_story=1` belum benar-benar mengunci semua body story dari Argos.

### Bukti visual POV yang harus selalu diingat

1. **Stale overlay / dialog-turn mismatch:**  
   Dialog game menampilkan `??: Okay!`, tetapi overlay masih menunjukkan `Si gadis pemalu.` dari dialog/narasi sebelumnya. Ini bukan injection agama; ini kegagalan state/commit/turn synchronization.

2. **Scene exit leakage:**  
   Setelah story berakhir dan layar masuk reward/map, overlay masih menerjemahkan UI seperti `Collect more to claim rewards` / `Normal Hard`. Ini membuktikan kebutuhan Dialogue Presence / Scene Exit Guard.

3. **Omission semantic pada Lite V3:**  
   Dialog mengenai ketidakpercayaan terhadap berita kematian Commander dan narasi `(DP-12 bows slightly, ending the conversation.)` diterjemahkan rusak/terpotong. Ini adalah fidelity/coverage failure, bukan sekadar blacklist injection.

Keputusan roadmap:
- jangan menambah blacklist saja;
- bangun Responsive Faithfulness & Turn-Safe Overlay.

## 4.11 v8.7.9 — Responsive Faithfulness & Turn-Safe Overlay
Status pada tanggal dokumen ini:
- Patch v8.7.9 telah **direkonstruksi** di percakapan terbaru di atas runtime v8.7.8 yang diunggah pengguna.
- Rekonstruksi bukan klaim bahwa ZIP lama yang gagal diunduh berhasil dipulihkan byte-per-byte.
- Gameplay live baru untuk patch rekonstruksi **belum tersedia**; hasil performa aktual tetap perlu diuji pengguna.

Fokus perubahan:
1. **Trusted Preview**  
   Jalur CT2-only cepat untuk source progresif/held pada story GFL2. Preview tidak boleh masuk cache, training, atau final current-dialog memo.

2. **Stable Final**  
   Hasil final menunggu source stabil dan baru menjalankan pemeriksaan faithfulness/fidelity yang lebih lengkap sebelum cache commit.

3. **Hard Strict CT2 Story**  
   Saat CT2 tersedia pada story GFL2, Argos body fallback dinonaktifkan default untuk seluruh request/span story, bukan hanya source progresif/Qur.

4. **Turn-Safe Overlay**  
   Dialog turn tracking dan clear-on-new-turn agar overlay lama tidak bertahan saat dialog baru muncul.

5. **Scene Exit Guard**  
   Membersihkan overlay dan menghentikan story translation ketika OCR/scene menunjukkan reward/map/menu non-dialog.

6. **Semantic Fidelity Guard**  
   Membandingkan hasil IDN polished dengan CT2 literal anchor untuk menangkap kehilangan negasi/entity/angka/action/coverage; output dapat fallback ke literal yang lebih faithful.

7. **Cache namespace baru**  
   `v8_7_9_responsive_turn_safe_ct2`.

8. **Sinkronisasi versi/UI**  
   Mengatasi baseline v8.7.8 yang masih menampilkan identitas v8.7.7 pada beberapa file/UI.

---

# 5. INVENTARIS ARTEFAK TERKINI YANG TERBUKTI ADA

## 5.1 Runtime baseline v8.7.8 yang diunggah pengguna
Nama file:
```text
ORT_Translation_v8_7_8(1).zip
```

Hasil audit:
- runtime penuh, bukan changed-files patch;
- 1.006 entri;
- ukuran hasil ekstraksi sekitar 427.949.050 byte;
- SHA-256:
```text
7d489df88ab934eb941b5090747be85ae38c5078ded21601383ada0c6a6b8a15
```

Catatan keamanan packaging:
- runtime penuh memuat code, docs, logs, cache, backups, status, dan konfigurasi aktif;
- tepat sebagai baseline audit/recovery;
- tidak boleh dianggap paket patch publik/GitHub-ready tanpa pemisahan data aktif.

## 5.2 Patch v8.7.9 rebuilt yang telah dibuat sebelum dokumen ini
Nama file:
```text
ORT_Translation_v8_7_9_CHANGED_FILES_PATCH_WITH_PROJECT_MEMORY_REBUILT.zip
```

SHA-256 terverifikasi dari file yang tersedia pada sesi pembuatan memo:
```text
0293b06791faa4e2fdea80c401e86ed059df4a3cc0a0f2cfb582eef32f0b5be6
```

Isi patch rebuilt sebelumnya:
- 27 file baru/berubah;
- modul utama, tools, config/ledger, dan docs v8.7.9;
- tidak membawa data aktif seperti logs/cache/status/backups/user prefs aktif.

## 5.3 Paket dokumentasi-inclusive
Mulai dokumen ini dibuat, paket v8.7.9 dapat diterbitkan ulang sebagai R2 yang menambahkan:
```text
docs/ORT_MASTER_PROJECT_MEMORY_HANDOFF_CURRENT.md
```
Kode runtime tidak berubah karena penambahan dokumen master; checksum R2 harus dibaca dari file checksum pendampingnya.

---

# 6. DATA IDENTITY, NPC, ALIAS, DAN SPECIAL TERMS YANG HARUS DIWARISI

## 6.1 Prinsip data

- Official roster tidak boleh diduplikasi; hanya metadata `observed_recent_story_*` yang diperbarui.
- Nama baru hanya dapat aktif bila exact-only dan telah memiliki dasar cukup/validasi yang aman.
- Alias OCR hanya berlaku pada Name ROI atau jalur terkendali, tidak fuzzy body global.
- Candidate Miner hanya menghasilkan antrean review; tidak boleh auto-promote.
- Special term bukan speaker.
- Commander name yang berganti antar akun tidak boleh menjadi speaker/NPC global.

## 6.2 Official observed penting dari sesi v8.7.6/v8.7.7
Nama official yang pernah teramati dan tidak boleh diduplikasi antara lain:
- `Phaetusa`, `DP-12`, `KSVK`, `Lentine`, `Helen`, `Lenna`, `Mayling`, `Helena`, `Groza`, `Colphne`, `Krolik`, `Ullrid`, `Nemesis`, `Dushevnaya`;
- penguatan berikutnya meliputi `Sharkry`, `Sextans`, `Springfield`, `Centaureissi`, `Leva`, `Makiatto`, `Dandelion`.

## 6.3 Exact/role safe retained/available pada rancangan v8.7.9
- `Berryfield`
- `Cocoon`
- `Carmen`
- `Another Unfamiliar Worker`
- `Kalina`
- `Farkas`
- `Client`

## 6.4 Review-only / belum auto-live
- `Chief of Odesa`
- `Municipal Broadcast`
- `Zyevnadya` / `Yyevnadya`
- `Blondie`
- `DKRIN`
- `NOMFA`
- `Perslcarla` / kemungkinan `Persicaria?`
- `Beepy`
- `Warrant Officer`

## 6.5 Commander exclusions global
Nama berikut hanya boleh sebagai `user_configured_commander` per akun/profile:
- `Vilyz`
- `ARVITA ID`
- `ATVITA ID`

## 6.6 Alias ROI-only/review yang perlu dipertahankan
Contoh alias yang telah dicatat:
- `Duyhevnaya → Dushevnaya`
- `Krollk → Krolik`
- `Nenesls` / `Nemesls → Nemesis`
- `Kallna` / `Kalin` / `Kalna` / `Kalllna → Kalina`
- `Cllent → Client`
- `QDE-01 → ODE-01`
- `GrOZy` / `Grozy → Groza`
- `aklatto` / `akiatto` / `Maklatto → Makiatto`
- `Dandelon → Dandelion`
- `Centaurelssl` / `Centawrelssl → Centaureissi`
- `Shafkry → Sharkry`
- `Sprlngfield → Springfield`

Khusus:
- `Helene` tidak boleh auto-map karena `Helen` dan `Helena` merupakan entitas berbeda.
- Alias `Chief of Odesa` tetap menunggu validasi visual sebelum aktivasi.

## 6.7 Special terms/lore terms yang perlu dipertahankan atau direview
Retained/direncanakan sebagai terminology, bukan speaker:
- `URNC`
- `Conglomerate`
- `Green Zone`
- `Yellow Zone`
- `Odesa`
- `ELID` / `ELIDs`
- `ODE-01`
- `ODE-01 Municipal Center`
- `Griffin`
- `Griffin & Kryuger`
- `Satellite City`
- `Blusphere`
- `Lviv`
- `Mangi Security`
- `Neural Cloud`
- `T-Doll`
- `Nyto`
- `Project Eden`
- `Port Vest`
- `Collapse Epiphyllum`
- `Collapse Epiphyllums`
- `Boojum` / `Boajum`
- `Varjager` / `Varjagers`
- `NOMFA`

Istilah hallucination agama seperti `nabi`, `Quran/Alquran`, `Mekah`, `Luth`, `Syuaib`, `malaikat`, `kafir`, `mukmin`, `al-Qur 'ân`, `ayat`, `zakat`, `neraka` tidak boleh dimasukkan sebagai terminology game kecuali source nyata mendukung; istilah tersebut berfungsi sebagai indikator semantic corruption/injection pada gate.

---

# 7. AKAR MASALAH HALLUCINATION DAN STUTTER YANG SUDAH DIKETAHUI

## 7.1 Hallucination religius/tafsir
Bukti historis:
- source OCR progresif/noisy biasa dapat berubah menjadi keluaran bertema `al-Qur 'ân`, `ayat`, `zakat`, `neraka`, atau pola tafsir;
- backend yang paling terkait dengan output final buruk adalah Argos Offline/legacy fallback;
- token OCR seperti `Qur` kemungkinan berasal dari corruption terhadap `our/your`.

Interpretasi yang aman:
- pola ini menunjukkan failure mode memorized/domain-biased pada fallback terjemahan ketika input rusak/tidak lengkap;
- asal corpus model tidak dapat dipastikan hanya dari file proyek;
- solusi bukan memasukkan istilah tersebut ke lore game, melainkan mencegah fallback berisiko dan menjalankan faithfulness guard.

## 7.2 Hallucination umum / semantic drift
Jenis kegagalan yang tidak selesai hanya dengan blacklist:
- stale overlay dari turn lama;
- UI reward/map diterjemahkan sebagai dialog;
- omission tindakan/narasi;
- kehilangan negasi;
- hasil IDN naturalization terlalu berubah dari CT2 literal;
- entity/angka penting hilang.

## 7.3 Stutter
Sumber yang telah terbukti pada v8.7.8:
- hold output berlebihan pada `accuracy_final_only_wait_stable`;
- spike `legacy_argos`/`mixed_ct2_legacy_argos`;
- queue menumpuk;
- overlay lama bertahan karena final/turn synchronization lemah.

Keputusan:
- safety berat harus final-only;
- preview CT2 ringan tetap tampil;
- Argos story default OFF ketika CT2 tersedia;
- stale jobs harus dibuang ketika dialog berubah.

---

# 8. PERFORMANCE BUDGET DAN ACCEPTANCE CRITERIA UNTUK UPDATE SELANJUTNYA

Nilai berikut adalah target engineering untuk evaluasi, bukan klaim hasil aktual sampai diuji.

| Area | Target evaluasi |
|---|---|
| Preview pertama Lite Auto | terasa instan; ideal p95 sekitar ≤250 ms setelah OCR bermakna |
| Stable Final setelah source berhenti | idealnya ≤500–700 ms |
| Overlay lama setelah turn baru | dibersihkan hampir seketika; target <100 ms |
| `legacy_argos` / `mixed_ct2_legacy_argos` / `argos_offline` pada story GFL2 saat CT2 tersedia | 0 secara default |
| Preview masuk final cache/training | 0 |
| Reward/map UI tampil sebagai dialog | 0 kasus |
| Candidate auto-promote tanpa approval | 0 kasus |
| Loss negasi/entity/angka penting pada final | harus diflag/fallback |
| Data aktif pengguna terbawa changed-files patch | 0 file |

Setiap update wajib mengevaluasi minimal:
- Lite Responsive/Lite IDN;
- Fast atau Fast IDN bila diubah;
- Normal/IDN bila jalur final/fidelity diubah;
- scene dialog progresif;
- pergantian dialog sangat pendek (`Okay!`);
- scene exit ke reward/map;
- penggunaan VRAM/queue/latency;
- engine actual applied, bukan sekadar policy requested.

---

# 9. STRATEGI MODE YANG DIREKOMENDASIKAN

## 9.1 Responsive Story
Target: Lite / game berat / kecepatan maksimal.
```text
CT2 single-pass preview
+ micro safety
+ latest-frame-wins
+ no Argos story
+ final sederhana setelah stabil
```

## 9.2 Balanced Story
Target: GFL2 sehari-hari.
```text
CT2 preview cepat
+ stable final
+ IDN polish final
+ fidelity final check
+ turn-safe/scene guard
```

## 9.3 Accuracy Story
Target: kualitas final lebih ketat tanpa mengorbankan preview.
```text
Preview tetap cepat
+ final validation lebih kuat
+ cache commit lebih ketat
```

## 9.4 Freeze / Manual Review
Target: inspeksi dialog tertentu.
```text
OCR retry/fidelity penuh diperbolehkan
+ tidak terikat pengalaman typewriter real-time
```

Aturan: bahkan mode Accuracy tidak boleh menahan preview sampai overlay terasa beku pada Auto Story.

---

# 10. TRIGGER DAN ARAH REFACTORING

## 10.1 Refactoring menjadi perlu bila:
- v8.7.9 masih stutter meski Trusted Preview aktif;
- Argos masih lolos pada story saat CT2 aktif;
- stale overlay masih muncul;
- Scene Exit Guard false-positive/false-negative berulang;
- Semantic Fidelity Guard membebani Lite;
- satu fix melahirkan banyak regression baru;
- test terus rusak karena kontrak internal berubah;
- versi/status UI tidak sinkron dengan runtime;
- packaging masih membawa data aktif pengguna.

## 10.2 Refactor yang direkomendasikan
Bukan rewrite total. Buat branch/folder baru yang memindahkan subsistem bertahap:

```text
app/
├── ocr/
│   ├── capture_pipeline.py
│   ├── roi_manager.py
│   └── scene_classifier.py
├── dialogue/
│   ├── state_machine.py
│   ├── turn_tracker.py
│   └── scheduler.py
├── translation/
│   ├── policy_engine.py
│   ├── preview_lane.py
│   ├── final_lane.py
│   ├── fidelity_guard.py
│   └── terminology.py
├── overlay/
│   ├── renderer.py
│   └── status_model.py
├── data/
│   ├── identity_store.py
│   ├── review_queue.py
│   └── cache_store.py
└── diagnostics/
    ├── telemetry.py
    └── debug_export.py
```

## 10.3 Dialogue state machine yang harus menjadi pusat refactor
State minimum:
```text
NO_DIALOG
DIALOG_DETECTED
PROGRESSIVE_CAPTURE
TRUSTED_PREVIEW_VISIBLE
SOURCE_STABLE
FINAL_VALIDATING
FINAL_VISIBLE_AND_CACHEABLE
TURN_CHANGED
SCENE_EXITED
ERROR_SAFE_SOURCE
```

Peraturan:
- hasil job lama tidak boleh menimpa dialog baru;
- cache write hanya untuk final dengan turn ID masih valid;
- scene exit membersihkan overlay;
- failure aman menampilkan literal/source-safe, bukan fallback berisiko.

---

# 11. ROADMAP DIREKOMENDASIKAN SETELAH v8.7.9

## 11.1 Langkah pertama: Live test v8.7.9
Uji terutama:
- Lite V3 / Lite IDN;
- Fast IDN bila diperlukan;
- Normal V3;
- preview pada teks typewriter;
- final translation;
- turn pendek `Okay!`;
- reward/map exit;
- nilai latency, queue, applied engine, VRAM;
- event:
  - `TRUSTED_PREVIEW_OVERLAY`
  - `FINAL_OVERLAY`
  - `STALE_OVERLAY_CLEARED_ON_NEW_TURN`
  - `SCENE_EXIT_OVERLAY_CLEARED`
  - `IDN_POLISH_DRIFT_FALLBACK_TO_CT2_LITERAL`
  - `STRICT_CT2_STORY_FALLBACK_SUPPRESSED`

## 11.2 Bila v8.7.9 membaik
Buat hardening kecil (v8.7.10) untuk:
- bug spesifik hasil live;
- telemetry/UI status;
- cache metadata/invalidation;
- replay test dataset;
- persiapan refactor.

## 11.3 Bila v8.7.9 masih jauh dari harapan
- freeze fitur baru;
- jangan menambah gate berlapis;
- mulai branch refactor pipeline/policy/state machine;
- gunakan baseline terbaik yang terukur.

## 11.4 v9.0
Rilis besar berupa full ZIP folder baru:
- root minimal berisi launcher seperti `Start OCR` dan `Runtime`;
- source/config/docs/tools/tests/assets/runtime/user_data/cache/logs/backups dipisahkan;
- GitHub-ready;
- migration plan v8.x → v9.0;
- rollback;
- master handoff ini ikut diwariskan;
- fitur audio baru dipertimbangkan setelah text-overlay stabil.

---

# 12. PROSEDUR ANALISIS LOG/VIDEO BARU

Saat pengguna mengunggah hasil tes baru, lakukan urutan berikut:

1. Identifikasi versi runtime sebenarnya, model, game, mode, OCR requested/applied/runtime-rescue, applied engine, CT2 status, cache namespace, VRAM/CPU/GPU state.
2. Pastikan profile game benar (`GFL` tidak boleh salah menjadi `GFL2_EXILIUM`, dan sebaliknya).
3. Hitung event preview/final/hold/clear/fallback/fidelity/cache.
4. Hitung latency median/p95/max dan queue wait; pisahkan warmup dan fallback spike.
5. Periksa apakah Argos story muncul saat CT2 tersedia.
6. Korelasikan log dengan video/screenshot untuk menemukan stale overlay, scene exit leakage, flicker preview→final, atau subtitle tertunda.
7. Audit OCR speaker/name/body dan candidate occurrence; klasifikasikan official/approved/review/alias/term/commander-only.
8. Jangan membuat keputusan akurasi hanya dari satu screenshot atau hanya dari log bila masalah bersifat visual.
9. Buat ledger hasil uji dan masukkan ringkasannya ke versi terbaru dokumen master ini.
10. Sebelum patch baru, tetapkan apakah masalah perlu patch lokal atau sudah memerlukan refactoring.

---

# 13. ATURAN PACKAGING SETIAP UPDATE BERIKUTNYA

Setiap changed-files ZIP update minor harus menyertakan minimal:
```text
CHANGED_FILES_MANIFEST_<VERSION>.txt
APPLY_NOTES_<VERSION>.txt
docs/CHANGELOG_<VERSION>.md
docs/TEST_REPORT_<VERSION>.md
docs/KNOWN_ISSUES_AND_NEXT_RECOMMENDATIONS_<VERSION>.md
docs/ORT_MASTER_PROJECT_MEMORY_HANDOFF_CURRENT.md
checksum SHA-256 pendamping
```

Jangan masukkan ke patch source, kecuali pengguna secara eksplisit meminta backup runtime penuh:
```text
speaker_registry_v2.json aktif
data_processing_store/settings aktif
webui_prefs.json
configs/app_state.json aktif
cache/
logs/
status/
backups/
reports/
debug_bundles/
```

Untuk update besar/full project:
- pisahkan default config dan user data;
- sertakan migration dry-run dan apply;
- sertakan rollback instructions;
- sertakan checksum;
- sertakan master handoff terkini.

---

# 14. HAL YANG BELUM BOLEH DIKLAIM

- v8.7.9 rebuilt belum dapat disebut berhasil dalam gameplay sampai pengguna mengirim live log/POV pengujian baru.
- ZIP v8.7.9 historis yang dahulu gagal diunduh tidak dipulihkan secara byte-identik; yang tersedia adalah rekonstruksi berdasarkan baseline dan memo/riwayat.
- Log/video mentah yang sudah dihapus dari laptop pengguna tidak dapat dikembalikan sebagai file asli dari dokumen ini.
- Candidate OCR tidak boleh diklaim sebagai karakter resmi tanpa validasi.
- Tidak ada jaminan lapisan safety baru selalu gratis terhadap latency; setiap perubahan harus diuji.

---

# 15. SUMBER RIWAYAT YANG MENJADI DASAR DOKUMEN INI

Dokumen ini merangkum keputusan dari arsip/artefak berikut yang pernah tersedia:
- `ORTCORE_MASTER_PROJECT_MEMORY_HANDOFF_V8_7_EXPANDED_AFTER_MEMORY_RESET.txt`
- `ORTCORE_MASTER_PROJECT_MEMORY_HANDOFF_V8_7_2_AFTER_IDN_OPTIMIZATION.txt`
- `ORT_AUDIT_PROFESIONAL_V8_6_TO_V8_7_2026-05-25.md`
- `ORT_V8_7_6_SOURCE_AUDIT_V8_7_5_DOWNGRADE_CHARACTER_OCCURRENCE_AND_LEDGER_2026-05-27.md`
- `ORT_V8_7_6_ROADMAP_ANALISIS_UJI_V8_7_5_LOG_VIDEO_2026-05-26.md`
- `ORT_V8_7_7_ROADMAP_AUDIT_V8_7_6_LOG_VIDEO_SEMANTIC_HALLUCINATION_2026-05-27.md`
- `ORT_V8_7_7_ADDENDUM_CT2_RECOVERY_NAMES_TERMS_FROM_V8_7_6_2026-05-27.md`
- `ORT_V8_7_8_CANDIDATE_IDENTITY_TERMS_AND_HALLUCINATION_ROOT_CAUSE_LEDGER_2026-05-28.md`
- `ORT_V8_7_8_ROADMAP_AUDIT_V8_7_7_LOG_VIDEO_SEMANTIC_CT2_2026-05-28.md`
- `ORT_V8_7_9_ROADMAP_AUDIT_V8_7_8_STUTTER_GENERAL_HALLUCINATION_2026-05-28.md`
- `ORT_AUDIT_HANDOFF_BASELINE_V8_7_8_AND_V8_7_9_DIRECTION_2026-05-29.md`
- `Analisis Proyek ORT v8.7.html`
- runtime baseline `ORT_Translation_v8_7_8(1).zip`
- patch rekonstruksi `ORT_Translation_v8_7_9_CHANGED_FILES_PATCH_WITH_PROJECT_MEMORY_REBUILT.zip`

---

# 16. CHECKLIST UNTUK CHATGPT SAAT MELANJUTKAN PROYEK

Sebelum menjawab permintaan update:
- [ ] Baca dokumen ini dan file terbaru yang diberikan pengguna.
- [ ] Identifikasi baseline source dan jangan mencampur build lama/baru tanpa catatan.
- [ ] Tentukan apakah permintaan adalah audit, patch kecil, refactor, atau full release.
- [ ] Lindungi data aktif pengguna dari ZIP patch.
- [ ] Pertahankan official/exact/review/alias/special-term/commander policy.
- [ ] Ukur dampak fitur pada preview latency, final latency, queue, VRAM, dan Lite.
- [ ] Jangan menambahkan gate berat di preview tanpa pembuktian.
- [ ] Jalankan compile/regression/smoke/dry-run/migration validation pada clone.
- [ ] Buat checksum dan manifest.
- [ ] Perbarui dokumen master ini dalam setiap paket update.

---

# 17. RINGKASAN SATU PARAGRAF UNTUK PEMULIHAN CEPAT

ORT Translation adalah overlay OCR penerjemah dialog game real-time untuk Bahasa Indonesia dengan fokus terbaru GFL2. Setelah v8.7 mengembangkan profile GFL dan identity/cache safety, v8.7.5–v8.7.8 menemukan rangkaian masalah: OCR rendah dan fallback Argos, hallucination tafsir/agama dari source noisy, lalu stutter dan semantic drift umum karena hold/fallback/stale overlay. v8.7.9 direkonstruksi untuk mengubah desain menjadi Trusted Preview CT2-only yang cepat dan Stable Final yang aman, dengan Hard Strict CT2 Story, Turn-Safe Overlay, Scene Exit Guard, Semantic Fidelity Guard, serta cache namespace `v8_7_9_responsive_turn_safe_ct2`. Prinsip mutlak pengguna: akurasi tidak boleh membuat Auto Story/Lite tersendat; safety berat harus final-only; Argos story default OFF saat CT2 tersedia; setiap update diuji terhadap latency/queue/VRAM/overlay; bila patch makin kacau, lakukan refactoring terkontrol menuju v9.0 GitHub-ready.
