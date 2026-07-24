# ORT v8.7.9 Project Memory Handoff

Patch ini adalah rekonstruksi v8.7.9 berdasarkan baseline v8.7.8 unggahan pengguna dan memo analisis lama. Rilis menargetkan regression v8.7.8: safety meningkat tetapi overlay tersendat, fallback Argos masih muncul, stale overlay terjadi pada turn baru, dan layar reward/map dapat ikut diterjemahkan.

Target live berikutnya: temukan event `TRUSTED_PREVIEW_OVERLAY`, `FINAL_OVERLAY`, `STALE_OVERLAY_CLEARED_ON_NEW_TURN`, `SCENE_EXIT_OVERLAY_CLEARED`, `IDN_POLISH_DRIFT_FALLBACK_TO_CT2_LITERAL`, serta `STRICT_CT2_STORY_FALLBACK_SUPPRESSED`; pada dialog GFL2 target `legacy_argos`, `mixed_ct2_legacy_argos`, dan `argos_offline` menuju nol saat CT2 tersedia.
