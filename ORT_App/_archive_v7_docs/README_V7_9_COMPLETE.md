# ORT Translation v7.9 Complete Ready Package

Pre-v8 major stabilization build. Fokus utama:

- Structured telemetry lintas proses via `ORT_SESSION_JSONL_PATH`.
- Legacy `training_log.jsonl` OFF by default.
- OCR/capture/preprocess latency dicatat ke session JSONL.
- Benchmark session lebih kuat dengan dedupe event dan rekomendasi otomatis.
- UI WebUI dibersihkan: panel pro disembunyikan default dengan Accordion/Perluas.
- Package hygiene: cache/log/status runtime tidak ikut release.

## Untuk Wuthering Waves
Gunakan Lite IDN V2 atau Fast V1, CPU, OCR 50-58%, interval 450-700 ms, Online Assist OFF default.

## Setelah bermain
Jalankan:

```bash
python benchmark_session_report.py
```

Lihat hasil di `status/benchmark_session.txt` dan `status/benchmark_session_recommendation.txt`.
