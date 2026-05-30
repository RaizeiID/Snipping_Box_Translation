# V7.2 Integration Notes

## Jalur utama runtime

Start_ORT_Translation.bat -> webui.py -> launcher_backend.py -> model_strategy.py -> TITANMAIN.py -> translation_engine.py + v72_runtime_bridge.py + runtime_health_manager.py

## File utama baru

- model_strategy.py
- translation_engine.py
- runtime_health_manager.py
- v72_runtime_bridge.py

## Status kompatibilitas

`v71_runtime_bridge.py` tetap ada sebagai wrapper kompatibilitas agar import lama tidak putus.

## Rekomendasi uji awal

1. Jalankan GFL2 Exilium + Normal V2.
2. Jalankan Wuthering Waves + Lite V2 / Lite IDN V2.
3. Cek Dashboard -> Diagnostic v7.2.
4. Pastikan `v72_strategy_status.json`, `v72_runtime_health.json`, dan `v72_core_status.json` terbentuk setelah Start.
5. Uji Normal Override WUWA hanya jika game masih stabil.
