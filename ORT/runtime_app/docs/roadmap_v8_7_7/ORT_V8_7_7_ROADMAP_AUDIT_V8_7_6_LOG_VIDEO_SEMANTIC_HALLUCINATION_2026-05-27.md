# ORT Translation v8.7.6 — Audit Log, POV Gameplay, Semantic Hallucination, dan Roadmap v8.7.7
**Tanggal audit:** 27 Mei 2026  
**Basis analisis:** 10 sesi log/event v8.7.6, 7 rekaman POV gameplay, dan ZIP runtime `ORT_Translation_v8_7_6.zip`.  
**Status:** Analisis profesional dan roadmap kumulatif; belum merupakan patch runtime v8.7.7.

## 1. Kesimpulan Eksekutif

v8.7.6 berhasil memperbaiki beberapa masalah penting:
- tidak ditemukan lagi marker internal `ORT_ENTITY`, `ORT_BKEND`, `ORT_BKED`, `ORT_BEND`, atau `_ _ ORT` pada event/cache namespace aktif yang diperiksa;
- `exact-only fallback speaker gate` bekerja: 175 calon false speaker diblok, dan label final yang muncul pada sesi audit seluruhnya berada dalam daftar official/approved speaker;
- `Adaptive OCR Readability Guard` bekerja nyata pada model rendah.

Namun, v8.7.6 masih mempunyai masalah P0 baru/yang kini terbukti kuat:
1. **Semantic hallucination terjemahan lolos ke overlay dan cache**: dialog game biasa berubah menjadi teks religius/tafsir yang sama sekali tidak ada pada source.
2. **45% terlihat lebih baik karena sering diselamatkan ke 55%, bukan karena native 45% telah optimal.**
3. **40% tetap tidak layak untuk story normal**, walaupun sering di-rescue ke 50%.
4. **Preview progressive masih mengganti overlay dengan fragmen/tulisan buruk**, sehingga user dapat melihat hasil tidak lengkap sebelum terjemahan yang lebih benar muncul.
5. **IDN accuracy-first tetap dapat turun dari 68% ke 55% karena throttle CPU/RAM sementara**, sehingga kualitas tidak konsisten.
6. **CT2/SPM masih tidak aktif untuk Lite/Fast; backend tetap Argos fallback.**

## 2. Sesi v8.7.6 yang Diaudit

| Waktu sesi | Model | OCR awal | Adaptive Rescue | Backend penting |
|---|---|---:|---:|---|
| 11:37:15 | IDN V3 | 68% applied dari request 75% | OFF | Argos Offline |
| 11:44:53 | IDN V5 | 68% applied dari request 75% | OFF | Argos Offline |
| 11:55:46 | Lite IDN V2 | 45% | ON | CT2 unavailable → Argos |
| 12:06:14 | Lite IDN V5 | 60% | ON | CT2 unavailable → Argos |
| 12:18:08 | Lite V4 | 55% | ON | CT2 unavailable → Argos |
| 12:23:46 | Lite V1 | 40% | ON | CT2 unavailable → Argos |
| 12:31:05 | Lite V1 | 40% | ON | CT2 unavailable → Argos |
| 13:02:55 | Fast V1 | 40% | ON | CT2 unavailable → Argos |
| 13:13:47 | Fast IDN | 50% | ON | CT2 unavailable → Argos |
| 13:22:18 | Normal V1 | 65% | OFF | Argos Offline |

Seluruh sesi masih memakai:
```text
responsive_story=0
latest_frame_wins=0
diagnostic=baseline
```
Dengan demikian, Mode Responsif belum dapat dinilai dari uji ini.

## 3. Adaptive OCR Rescue: 45% Membaik, tetapi karena Sering Naik ke 55%

### 3.1 Lite IDN V2 — OCR 45%

Pada sesi `11:55:46`, event mencatat:

| Metrik | Nilai |
|---|---:|
| OCR awal | 45% |
| `OCR_READABILITY_RESCUE` | 1.133 event frame |
| Retry yang dipilih | 994 event |
| Retry terpilih | 55% |
| Median tambahan waktu rescue | ±119 ms |

Contoh event:
```text
Initial 45%:
Helen Bisodon the intel gatherod ... Lviy labor Ntory CpIOSIon ...

Selected retry 55%:
Helen Based on the intel gathered so far ... Lviv laboratory explosion ...
```

Interpretasi profesional:
```text
Lite IDN V2 45% kini dapat terasa cukup layak karena runtime sangat sering
memakai hasil 55%, bukan karena hasil native 45% sudah bersih.
```

Rekaman `2026-05-27 11-56-26.mkv` menunjukkan beberapa overlay jauh lebih terbaca daripada uji 40%, tetapi masih terlihat output sementara yang tidak lengkap atau tertinggal pada transisi tertentu.

### 3.2 Lite V1 — OCR 40%

Dua sesi Lite V1 menunjukkan:

| Sesi | Rescue event | Retry 50% dipilih | Penilaian visual |
|---|---:|---:|---|
| 12:23:46 | 689 | 541 | Masih banyak fragmen/gibberish |
| 12:31:05 | 2.474 | 1.987 | Masih ada OCR rusak dan hallucination |

Pada video `2026-05-27 12-24-03.mkv`, hasil seperti `Vilyz NOUVOIT TIOr Jonq`, potongan teks campur, dan dialog yang tidak utuh tetap terlihat. Jadi rescue 40→50 belum cukup untuk membuat Lite V1 aman bagi story biasa.

### 3.3 Fast V1 — OCR 40%

| Metrik | Nilai |
|---|---:|
| Rescue event | 709 |
| Retry 50% dipilih | 491 |
| Penilaian visual | Tetap kasar/gibberish pada beberapa scene |

Video `2026-05-27 13-03-10.mkv` menampilkan hasil overlay yang masih tidak mengikuti dialog secara cukup baik. `Fast V1 40%` tetap sebaiknya menjadi mode diagnostic/ultra-speed, bukan baseline story.

### 3.4 Fast IDN — OCR 50%

Fast IDN memakai 50%, tetapi 192 dari 376 rescue memilih 55%. Video `2026-05-27 13-14-08.mkv` masih menunjukkan output parsial/berantakan pada beberapa scene. Karena CT2 tetap gagal dan backend menjadi Argos, profile Fast IDN belum dapat diperlakukan sebagai mode cepat sekaligus akurat.

## 4. Hallucination Semantik: Bukti P0

### 4.1 Lite IDN V5: “and chose the latter” menjadi paragraf tentang nabi

Session:
```text
session_GFL2_EXILIUM_20260527_120614
Model: Lite IDN V5, OCR 60%, backend=argos_offline
```

Source:
```text
and chose the latter
```

`backend_output` dan `final_idn_output`:
```text
(Dan orang-orang yang paling dahulu) dalam kebaikan, mereka adalah para nabi;
ayat ini berkedudukan menjadi Mubtada ...
```

Ini bukan akibat nama character atau EntitySpan. Source pendek bahasa Inggris tidak memuat arti agama apa pun, tetapi backend langsung menghasilkan paragraf tafsir yang tidak relevan.

Lebih serius lagi, output tersebut:
- tampil sebagai `FINAL_OVERLAY`;
- tersimpan dalam `naturalized_idn_cache_v8_7_6_adaptive_ocr_exact_safe.json`;
- tersimpan dalam translation memory Lite IDN V5.

### 4.2 Normal V1: hallucination terlihat langsung di video

Video:
```text
2026-05-27 13-22-36.mkv, sekitar 63 detik
```

Dialog game yang terlihat:
```text
Vilyz:
Yeah, we're all getting on quite well. Groza and the others are in the
Green Zone near Odesa. They'll come swooping in if something goes wrong on our end.
```

Overlay pada frame audit menampilkan teks tidak relevan seperti:
```text
Groza (Dan yang lainnya) yakni orang-orang kafir dan orang-orang mukmin ...
```

Structured event pada source prefix yang sama juga memuat hasil:
```text
... kota kaum Nabi Luth dan kota kaum Nabi Syuaib ...
... kota Mekah.
```

Beberapa detik kemudian, ketika source dialog lebih lengkap, overlay berubah menjadi terjemahan yang lebih masuk akal. Jadi user tetap sempat melihat hallucination, walaupun output berikutnya membetulkannya.

### 4.3 Lite V1: “our reality” rusak menjadi `Qur reality` → `Quran`

Video:
```text
2026-05-27 12-31-22.mkv, sekitar 490 detik
```

Dialog asli DP-12 yang terlihat:
```text
But one day, I say, one day... we'll turn it into our reality.
```

Event OCR/translation:
```text
Source OCR: ... LUI into Qur reality
Translation: ... realitas Quran
```

Kasus ini berbeda dari “nabi”:
- di sini OCR lebih dahulu merusak `our` menjadi `Qur`;
- backend lalu menganggap token tersebut merujuk `Quran`.

Ini adalah **OCR-triggered semantic hallucination**, sedangkan kasus `and chose the latter → para nabi` adalah **backend hallucination murni**.

### 4.4 IDN V5: QA mendeteksi, tetapi hasil salah tetap muncul

Sesi IDN V5 pada 11:44:53 menemukan beberapa output tidak relevan, misalnya:
- dialog biasa berubah menjadi teks `Al-masyâriq / al-maghârib`;
- dialog Phaetusa berubah menjadi uraian `catatan amal ... tangan kiri ...`.

Log mencatat `QualityEstimation: REJECT - HALLUCINATION_DETECTED` sebanyak tiga kali, tetapi `FINAL_OVERLAY` tetap memuat hasil salah.

Akar source:
- profile IDN V5 mengaktifkan `QualityEstimation`;
- ketika QA menolak, `runtime_bridge.py` mengembalikan `out = original_out`;
- `original_out` sudah merupakan output backend Argos yang berhalusinasi;
- sehingga “fallback” tidak aman dan tetap tampil.

### 4.5 Lite IDN/Lite/Normal ringan tidak selalu memiliki QA aktif

Pada `core_profile_manager.py`, `QualityEstimation` aktif untuk profile `balanced`, `quality`, `hybrid`, dan `natural`, tetapi tidak aktif pada:
```text
lite_idn_efficient
lite_efficient
fast
light
```

Akibatnya, Lite IDN V5, Lite V1/Lite V4, Fast, dan Normal V1 ringan dapat menampilkan hallucination backend tanpa pemeriksaan QA panjang-rasio yang sama.

## 5. Cache v8.7.6 Sudah Tercemar Hallucination Semantik

Namespace v8.7.6 aman dari marker internal, tetapi belum aman dari output bermakna palsu.

Cache aktif yang ditemukan menyimpan output bermasalah:

| Cache | Output bermasalah |
|---|---|
| `naturalized_idn_cache_v8_7_6_adaptive_ocr_exact_safe.json` | `Al-masyâriq`, `para nabi` |
| Translation memory IDN V5 | output `Al-masyâriq/al-maghârib` |
| Translation memory Lite IDN V5 | `and chose the latter → para nabi` |
| Translation memory Lite V1 | `Quran`, `nabi-nabi` |

Artinya, bila source serupa muncul kembali, hasil salah dapat menjadi cache hit. Update berikutnya wajib memutar/menyaring cache ini setelah semantic gate diterapkan.

## 6. Yang Berhasil: EntitySpan dan False Speaker Gate

### 6.1 Marker internal
Tidak ditemukan:
```text
ORT_ENTITY
ORT_BKEND
ORT_BKED
ORT_BEND
_ _ ORT
```
pada session/cache aktif v8.7.6 yang diaudit.

### 6.2 False speaker gate
Aggregate structured events:
```text
FALSE_SPEAKER_BLOCKED         = 175
GFL2_FALLBACK_SPEAKER_REJECTED = 175
```

Audit seluruh `FINAL_OVERLAY` dalam sepuluh sesi tidak menemukan speaker final di luar official/approved exact-speaker. Jadi masalah false label `DP`, `Name`, `TC`, atau `Hybrid` dari v8.7.5 sudah jauh lebih baik.

## 7. Masalah Terjemahan Tidak Lengkap / Pemangkasan

Keluhan user bahwa dialog 100% dapat menghasilkan terjemahan yang tampak hanya 80% atau kurang valid secara pengalaman visual.

Bukti:
- video IDN V3 (`11:38:02`) menampilkan overlay pendek/fragmen seperti `Asharp voi...` ketika dialog bawah sudah berbunyi `A sharp voice explodes in her ear...`;
- video Lite IDN V2 (`11:56:26`) menunjukkan terjemahan cukup membaik tetapi beberapa turn tetap parsial atau terlambat;
- Lite V1, Fast V1, dan Fast IDN menunjukkan fragmen buruk lebih sering;
- Normal V1 memperlihatkan hallucination transient sebelum output lebih benar muncul.

Structured logs aggregate:
| Event | Jumlah record |
|---|---:|
| `TRANSLATION_RESULT` | 17.190 |
| `FINAL_OVERLAY` | 8.969 |
| `CACHE_SKIP_PROGRESSIVE` | 8.272 |
| `OVERLAY_STALE_SPEAKER_DROPPED` | 34 |

Interpretasi:
- progressive translation masih sangat aktif;
- output interim tetap dapat sampai ke overlay;
- saat source baru belum stabil, backend dapat menerjemahkan frasa pendek/terpotong secara salah;
- untuk user yang tidak paham bahasa Inggris, menampilkan terjemahan parsial atau mengada-ngada lebih berbahaya daripada menunggu sedikit lebih lama.

## 8. OCR Accuracy-First Masih Tidak Stabil

IDN V3 dan IDN V5 meminta OCR 75% tetapi runtime menerapkan 68%. Selain itu, selama sesi:
- IDN V3 beberapa kali turun `68% → 55%` karena `CPU/RAM warning`;
- IDN V5 memiliki 44 perubahan OCR `68% ↔ 55%`;
- Lite IDN V5 sempat turun `60% → 55%`.

Untuk model IDN yang dipilih demi akurasi, penurunan temporer ini dapat membuat kualitas antardialog tidak konsisten. Update berikutnya perlu hysteresis/quality lock: jangan turun agresif hanya karena warning sesaat kecuali ada tekanan resource yang bertahan.

## 9. Roadmap P0 v8.7.7

### P0-A — Universal Faithfulness / Semantic Hallucination Gate
Gate ini harus selalu aktif untuk semua model dan tidak bergantung pada core profile berat.

Wajib dijalankan:
```text
setelah backend translation
setelah IDN post-processing
sebelum overlay
sebelum cache store
sebelum training/learning sample
```

Deteksi minimal:
- expansion ratio ekstrem, misalnya `and chose the latter` menjadi paragraf panjang;
- istilah/domain baru yang tidak didukung source, misalnya `nabi`, `Alquran/Quran`, `Mekah`, `Syuaib`, `Luth`, `malaikat`, `kafir`, `mukmin`, `Al-masyâriq`, kecuali source memang memuat konsep terkait;
- source-output keyword/NER mismatch;
- output tafsir/narasi panjang dari source pendek atau incomplete prefix;
- hasil cache lama yang memenuhi pola hallucination.

Event baru:
```text
SEMANTIC_HALLUCINATION_BLOCKED
SEMANTIC_CACHE_REJECTED
SAFE_LITERAL_RETRY_USED
UNTRUSTED_TRANSLATION_HELD
```

### P0-B — Fallback yang Aman
Saat hallucination terdeteksi:
- jangan kembali ke `backend_output` yang sama-sama salah;
- jangan tampilkan dan jangan cache;
- untuk source progressive/pendek, tahan overlay terakhir yang aman dan tunggu subtitle stabil;
- untuk source final, retry menggunakan `literal-safe` / segmented translation;
- bila retry tetap gagal, tampilkan source Inggris dengan status kecil `Terjemahan ditahan: hasil tidak terpercaya`, bukan makna palsu.

### P0-C — Cache Rotation Semantik
Gunakan namespace baru sesudah gate diterapkan dan pindahkan cache v8.7.6 yang sudah memuat hallucination. Tool rotasi harus mencari bukan hanya marker internal, tetapi juga output semantic anomaly yang telah terbukti.

### P0-D — Dialogue Completeness Gate
Untuk mencegah “dialog penuh tetapi overlay hanya sebagian”:
- pisahkan `preview` dan `committed final` secara visual;
- jangan mengganti terjemahan final aman dengan prefix singkat/fragmen buruk;
- hold frasa konektor atau source terlalu pendek: `and chose the latter`, `and recel`, `Then We`, dll.;
- committed final hanya setelah dialog stabil atau coverage cukup;
- catat `SOURCE_STABLE_LENGTH`, `OUTPUT_COMMITTED_COVERAGE`, `OMISSION_SUSPECTED`, dan `PREVIEW_HELD_INCOMPLETE`.

### P0-E — IDN Accuracy Quality Lock
Untuk keluarga IDN kualitas:
- tambah hysteresis terhadap dynamic downscale;
- jangan turun 68→55 hanya karena warning transient;
- status UI harus menampilkan kapan kualitas turun, berapa lama, dan dampak pada scene.

## 10. Roadmap P1

- Perbaiki CT2/SPM agar Lite/Fast tidak terus menggunakan Argos fallback.
- Setelah semantic/completeness gate stabil, uji Mode Responsif ON vs OFF pada scene video yang sama.
- Perluas Replay Benchmark agar mengukur:
  - CER/WER OCR,
  - semantic hallucination count,
  - cache contamination count,
  - committed translation coverage/omission,
  - label speaker accuracy,
  - stale overlay rate,
  - latency final.
- Tambahkan panel UI `Translation Reliability`:
  ```text
  Faithfulness: Aman / Ditahan / Retry Literal
  OCR Rescue: 45 → 55
  Source Status: Preview / Stable Final
  Backend: Argos Fallback / CT2
  ```

## 11. Penilaian Akhir v8.7.6

| Area | Status |
|---|---|
| EntitySpan / marker internal | Berhasil membaik kuat |
| Official speaker / false speaker | Berhasil membaik kuat |
| Adaptive OCR 45% | Membantu, tetapi umumnya melalui retry ke 55% |
| OCR 40% | Masih tidak layak untuk story normal |
| Translation faithfulness | P0 belum aman; hallucination nyata tampil dan tersimpan |
| Translation completeness | Belum aman; preview/fragmen masih tampil |
| Accuracy-first IDN OCR stability | Perlu quality lock/hysteresis |
| Responsive Mode | Belum diuji |
| CT2/Fast backend | Belum pulih; masih Argos fallback |

## 12. Keputusan Kumulatif untuk Update Berikutnya

Update selanjutnya sebaiknya bernama **v8.7.7** dengan fokus utama:

```text
Universal Semantic Faithfulness Gate
+ Safe Hallucination Fallback
+ Semantic Cache Rotation
+ Dialogue Completeness / Stable Commit Gate
+ IDN Quality Lock
+ CT2 fallback diagnostics
+ replay benchmark log-video yang menghitung fidelity dan omission
```

Jangan rollback EntitySpan, exact-speaker, atau adaptive OCR hanya karena muncul masalah terjemahan semantik; akar masalah terbaru berada pada backend output, pemilihan preview/final, dan kurangnya guard fidelity sebelum output tampil.
