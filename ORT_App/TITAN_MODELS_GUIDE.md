# TITAN MODELS GUIDE (V1–V4 + V3Lite + IDN)

Terakhir update: **2026-01-06**  
File ini menjelaskan perbedaan tiap model Titan, kapan dipakai, dan cara menjalankan via terminal launcher.

---

## Cara menjalankan (paling mudah)

1) Jalankan launcher:
- `Run_TITAN_LAUNCHER.cmd` (Windows)
- atau `python TITAN_LAUNCHER.py`

2) Pilih model dari menu (nomor/alias).  
Bisa jalankan **berurutan** dengan input: `6,7,8`.

---

## Model Overview

### Titan V1 (FAST)
**Tujuan:** latensi serendah mungkin.  
**Kelebihan:** cepat.  
**Kekurangan:** akurasi/ketahanan konteks biasanya lebih rendah dibanding V2/V3.  
**Cocok untuk:** UI cepat, teks pendek, FPS/aksi yang butuh respons instan.

**File:**
- `TitanMainV1.py`
- `TitanMainV1_IDN.py` (hasil dibuat lebih natural untuk Indonesia)

---

### Titan V2 (STABLE)
**Tujuan:** stabil dan lengkap (middle ground).  
**Kelebihan:** lebih konsisten dari V1.  
**Kekurangan:** biasanya sedikit lebih berat/lebih lambat daripada V1.  
**Cocok untuk:** penggunaan umum, game dengan teks banyak.

**File:**
- `TitanMainV2.py`
- `TitanMainV2_IDN.py`

---

### Titan V3 (HYBRID)
**Tujuan:** hybrid routing (online/offline/cache) dengan indikator latency.  
**Cocok untuk:** game dialog panjang (VN/gacha), butuh akurasi tapi tetap responsif.

#### Option A (MS+PING framed)
- Indikator lengkap (MS + PING)
- Biasanya lebih informatif tapi sedikit lebih berat UI.

**File:** `TitanMainV3_OptionA_FRAMED.py`

#### Option B (MS only)
- Lebih ringan, tanpa ping monitor.

**File:** `TitanMainV3_OptionB_FRAMED.py`

#### Option C (gabungan A+B)
- Seimbang: fitur A + fallback B.

**File:** `TitanMainV3_OptionC_FRAMED.py`

#### V3_IDN
- Output hasil terjemahan diproses agar lebih natural untuk pembaca Indonesia.

**File:** `TitanMainV3_IDN.py`

---

### Titan V3Lite (HYBRID LITE)
**Tujuan:** versi ringan dari V3 (lebih hemat resource).  
**Cocok untuk:** PC spek menengah/rendah atau saat multitasking.

**File:**
- `TitanMainV3Lite.py`
- `TitanMainV3Lite_OptionA_FRAMED.py`
- `TitanMainV3Lite_OptionB_FRAMED.py`
- `TitanMainV3Lite_OptionC_FRAMED.py`
- `TitanMainV3Lite_IDN.py`

---

### Titan V4 (NEW / EXPERIMENTAL)
**Tujuan:** generasi baru/eksperimen (kombinasi cepat + akurat + natural).  
**Catatan:** bisa berubah sesuai iterasi update.

**File:**
- `TitanMainV4.py`
- `TitanMainV4_IDN.py`

---

## Catatan tentang *_IDN (Naturalisasi Bahasa Indonesia)
Varian `*_IDN` menambahkan tahap post-processing agar hasil:
- lebih natural untuk pembaca Indonesia
- tidak kaku/literal
- (opsional) style: `TITAN_IDN_STYLE=neutral|formal|casual`

Core naturalisasi biasanya ada pada `TitanIndonesianLocalizer.py` (jika tersedia).

---

## Troubleshooting singkat
- Jika menu menunjukkan `[MISSING]`, berarti file belum ada/berbeda nama.
- Pastikan Python sudah terinstall dan bisa dipanggil lewat `python` atau `py -3`.


## ORT Translation v7 Model Groups

- Normal V1-V5: V1 ringan, V2 balance, V3 akurasi berat, V4 hybrid online/offline, V5 naturalisasi presisi.
- Lite V1-V5: basis Normal yang dibuat lebih hemat untuk game berat.
- IDN V1-V5: basis Normal dengan naturalisasi Bahasa Indonesia aktif.
- Lite IDN V1-V5: Lite + naturalisasi Indonesia.
- Fast: mode latensi rendah untuk game dengan dialog cepat.

Jalur utama v7 menggunakan `model_registry.py`, bukan daftar model manual yang tersebar.
