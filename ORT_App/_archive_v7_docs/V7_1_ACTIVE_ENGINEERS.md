# ORT Translation v7.1 - Status File Python / “Insinyur”

Dokumen ini menjelaskan fungsi file Python utama dan statusnya dalam v7.1.

## Jalur produksi utama

File berikut adalah jalur utama yang wajib dipertahankan:

```text
webui.py
launcher_backend.py
model_registry.py
v7_system_profile.py
TITANMAIN.py
v71_runtime_bridge.py
data_processing_backend.py
gpu_runtime.py
runtime_config.py
```

Jika salah satu file di atas dihapus, WebUI atau runtime utama kemungkinan error.

## Core yang diaktifkan melalui v71_runtime_bridge.py

Core berikut dipanggil secara aman oleh `v71_runtime_bridge.py`:

```text
ResourceSentinelCore.py          -> memantau CPU/RAM
AdaptiveThrottleCore.py          -> mengatur backoff OCR saat sistem berat
LatencyBudgetManagerCore.py      -> guard frame budget
PrioritySchedulerCore.py         -> helper prioritas tugas
PipelineOptimizerCore.py         -> rencana optimasi pipeline
TextStitcherCore.py              -> menyambung hasil OCR multi-line
SanitizerCore.py                 -> membersihkan noise OCR
SpellWeaverCore.py               -> memperbaiki glitch/typo OCR
EdgeCaseDetectorCore.py          -> memblokir loop/gibberish
DuplicateSubtitleSuppressorCore.py -> mengurangi subtitle duplikat
VisionAnalystCore.py             -> skip teks menu/loading untuk profil berat
ContextBufferCore.py             -> menyimpan konteks dialog pendek
TimelineTrackerCore.py           -> telemetry sesi
NarrativeCore.py                 -> hook analisis narasi
SociologistCore.py               -> profil gaya bicara karakter
CharacterArcCore.py              -> hook status karakter
EntityDiscoveryCore.py           -> hook kandidat entitas/nama
LearningEngineCore.py            -> pembelajaran noise/koreksi
FeedbackCollectorCore.py         -> kanal feedback koreksi
SmartCacheRouterCore.py          -> menentukan apakah teks layak cache
MemoryVaultCore.py               -> cache/memori sekunder
DynamicBatchingCore.py           -> helper batching untuk fast path mendatang
FailoverCore.py                  -> fallback darurat jika translator gagal
LoreKeeperCore.py                -> menjaga istilah lore/game
ProfessorSyntaxCore.py           -> koreksi sintaks
ProfessorToneCore.py             -> naturalisasi nada/IDN
ProfessorLogicCore.py            -> validasi logika output
StyleGuideCore.py                -> format gaya bahasa
TerminologyConstraintCore.py     -> enforcement istilah/blacklist
BilingualConsistencyCore.py      -> konsistensi bilingual
QualityEstimationCore.py         -> deteksi output buruk/hallucination
ValidationGateCore.py            -> gate akhir sebelum display
BlackBoxCore.py                  -> event/error recorder
LQAReportCore.py                 -> counter kualitas
OverseerCore.py                  -> health tracker
FallbackStrategyCore.py          -> fallback tampilan/log darurat
```

## Core yang sengaja diparkir

Core berikut tidak dihapus, tetapi tidak dijalankan langsung pada loop produksi v7.1:

```text
CaptureSpecialistCore.py         -> memakai Tesseract, berpotensi bentrok dengan EasyOCR dan butuh instalasi eksternal
HelsinkiCore.py                  -> translator Argos alternatif; TITANMAIN sudah punya translator Argos sendiri
AsyncOrchestratorCore.py         -> membuat worker thread sendiri; TITANMAIN sudah memakai QThread
FormatterCore.py                 -> renderer HTML alternatif; UI box terjemahan dikunci
UIConstraintCore.py              -> wrapper layout alternatif; UI box terjemahan dikunci
PromptDirectorCore.py            -> untuk jalur online/V4 mendatang
MultiCandidateGeneratorCore.py   -> butuh kontrak engine tambahan
BackTranslationVerifierCore.py   -> mahal untuk runtime, cocok untuk quality mode khusus
ConsistencyAuditorCore.py        -> audit manual, bukan tiap frame
RegressionTestCore.py            -> diagnostic/test manual
ConfigMasterCore.py              -> future central config
SynapseCore.py                   -> event bus untuk v7.2+
SemanticsCore.py                 -> butuh packet contract khusus
DeanCore.py                      -> council/review berat, belum dipakai tiap frame
```

Status runtime aktual akan ditulis ke `v71_core_status.json` setelah tombol Start dijalankan.

## Kesimpulan efisiensi

V7.1 tidak menghapus core-core lama secara permanen. File yang membingungkan dipindah ke `_archive_v6_legacy`, sementara core yang relevan diaktifkan lewat bridge. Ini lebih aman daripada menghapus file langsung karena proyek masih butuh pengujian nyata pada GFL2 Exilium dan Wuthering Waves.
