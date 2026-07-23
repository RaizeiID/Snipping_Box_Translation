# ORT Master Project Memory Handoff — Current through v8.9.5

## Current version
v8.9.5 — Real-Time Video Translation Update

## Latest project direction
v8.9.2 stabilizes OCR change detection, turn/generation identity, atomic overlay commits, stale-result rejection, and JSONL integrity. R2–R6 add Guided/Expert UI, Audio CPU, model recovery/compatibility, and native translation crash isolation. v8.9.3 turns Audio into explicit CPU/GPU/Hybrid execution paths, separates capture from ASR, introduces replay-safe GPU failover, and improves Japanese dialogue filtering while retaining the R6 translation-process boundary. v8.9.4 adds Azure Live Media streaming and local replay fallback. v8.9.5 changes that path into phone-style real-time video translation with 20 ms frames, endpoint profiles, Japanese Specialist phrase biasing, callback coalescing, final drain, state ordering, and latency telemetry.

## v8.9.5 Addendum — Real-Time Video Translation

- The goal is one-way video/game subtitle translation, not a turn-based two-person conversation workflow.
- Azure audio is written in 20 ms frames. The UI may only report `STREAMING` after `session_started` confirms `CLOUD_CONNECTED`.
- `speed`/Instant, `normal`/Balanced, and `accurate` select endpoint and overlay behavior as well as local fallback quality. For ja-JP Live Media the current silence targets are approximately 280/350/480 ms.
- `Speech_SegmentationMaximumTimeMs` limits phrases that otherwise keep absorbing multiple speakers.
- Interim callbacks revise one live subtitle line. Callback bursts are throttled, finals lock the line, stale interim is rejected, and repeated text from a different result ID remains valid.
- Closing a file or stopping capture closes the push stream first and drains callbacks before stopping the recognizer. This protects the last sentence.
- The six-second PCM replay buffer preserves the newest tail even if a single input payload exceeds its total capacity.
- Japanese Specialist sends Japanese and canonical GFL2 names/terms through Azure PhraseListGrammar. Keep the source locale fixed to `ja-JP`; do not use auto language for GFL2 testing.
- Credential deletion must be verified. An environment-provided key cannot be removed by the app and must be reported as still active.
- This release emulates the interaction pattern of phone live-video translation but does not claim to reproduce any proprietary smartphone model or private endpoint.

## v8.9.4 Addendum — Cloud Live Media Streaming

- Audio usage and delivery engine are independent controls. `live_media`/`conversation` does not replace local `cpu`/`gpu`/`hybrid`; it selects the capture/finalization behavior, while `local`/`azure`/`azure_fallback` selects the delivery path.
- Azure Live Media captures Windows system audio through WASAPI loopback, converts it to signed little-endian PCM 16-bit mono 16 kHz, and writes short frames to one persistent `TranslationRecognizer` connection.
- `recognizing` events are treated as interim subtitles and appear in light blue while a character is still speaking. `recognized` events replace the same subtitle with a stable white final result.
- GFL2 uses the fixed source locale `ja-JP` and direct Indonesian target `id`. A fixed locale is required because Azure interim translation is not routed through automatic source-language detection.
- `NO_MATCH`, silence, and noise never replace the visible subtitle. Local `quality_reject` events are also log/status only; the last usable translation stays on screen.
- Azure dependencies are installed in the separate `_runtime/audio_cloud/.venv`. The existing OCR, `audio_cpu`, `audio_gpu`, models, and user cache remain isolated.
- The Azure subscription key is sent from the local WebUI to the credential sidecar through stdin and stored through Windows Credential Manager. It must never be written to command arguments, preferences, source, status, log, manifest, or patch.
- `azure` is strict and stops visibly if the cloud path fails. `azure_fallback` is allowed to switch only when the selected local runtime and model have already passed their existing readiness checks.
- The cloud sidecar keeps a six-second in-memory PCM rolling buffer. A fatal cancellation writes a temporary `.npy` replay segment inside the session spool; after the cloud process exits, the parent starts the local pipeline and submits that segment before resuming capture.
- Cloud-to-local failover is one-way for the session. A new session is required to retry Azure, preventing repeated connection flapping.
- A file-based Azure test accepts only PCM 16-bit WAV. Other media formats remain supported through the Local engine.
- Automated validation uses a deterministic fake Azure SDK to exercise streaming callbacks and PCM delivery without a subscription. Real effectiveness, cost, network latency, Japanese-to-Indonesian accuracy, WASAPI behavior, and GFL2 session stability require testing on the user's Windows laptop with an active Azure resource.

## v8.9.3 Addendum — Audio Tri-Mode & Japanese Quality

- CPU never probes or allocates CUDA and uses `base`/`small` with CPU INT8.
- GPU is strict: faster-whisper ASR uses CUDA `int8_float16`; VAD and translation stay on CPU; missing CUDA, VRAM, or models must be reported instead of hidden behind CPU fallback.
- Hybrid starts GPU when both workers and the VRAM reserve are ready. Otherwise it starts as CPU Guard. A GPU worker failure requeues the same segment identity on CPU, then retries GPU after the replay ACK. A second GPU failure opens the circuit and keeps the session on CPU.
- WASAPI capture/adaptive-energy VAD is a separate process. Audio segments are atomically spooled until acknowledged by ASR; the bounded ledger deletes only dropped or completed temporary segments.
- GFL2 defaults to Japanese input (`ja`) and Whisper `task=translate`, preserving the established English→Indonesian ORTCore bridge.
- Speed/Normal GPU use `small`; Accurate GPU uses `medium`. CPU Speed uses `base`; CPU Normal/Accurate use `small`. Hybrid fallbacks are `base`, `base`, and `small` respectively.
- Quality gates reject no-speech, low-confidence, high-compression, repeated, token-dense, language-mismatched, and known promotional hallucinations. Retryable cases receive one higher-beam pass.
- Audio translation splits sentence clauses, translates each through the isolated R6 worker, and rejoins every clause. The OCR policy remains unchanged.
- `requested_mode` and `effective_mode` must always be visible. `gpu` may never claim success when the active ASR worker is CPU.
- The shared model root remains `audio_cpu/models`; runtime/model/cache/user data are never bundled in the patch.

## Important principle
Low-OCR models such as Lite V1, Lite IDN V1, and other 40–45% OCR profiles must continue to be tested and optimized. They are entry-level/stress targets, not disposable modes. The system should improve their output using software-side cleaning, churn detection, cache shielding, and per-turn source handling without simply raising global OCR.

## v8.8.5 additions
- Turn Finalizer.
- OCR Churn Rescue.
- Bad Cache Shield.
- Source Longer Must Win.
- Hard repaint last-good overlay.
- Extra telemetry for final completeness and low-OCR analysis.

## Next likely focus
Use v8.8.5 logs to decide v8.8.6. If issues remain, prioritize mode policy separation for Interval/Freeze and deeper turn lifecycle refactoring, not heavy semantic preview gates.


## v8.8.6 Strategy Update

- Main Commander is `Raizei`; ARVITA/ATVITA/AFVITA cluster is alternate/example profile, not main.
- Mode Buffer is experimental checkbox under `Pilih Model`, default OFF, with hover/help tooltip.
- Temporal OCR Consensus must not block preview; it works in final lane only.
- Prediction/Repair Text will be guarded by confidence labels and replay-derived patterns, not blind auto-correct.
- Offline Replay Benchmark should learn general failure patterns, not memorize old story lines.


## v8.8.7 Strategy Addendum — Name/Term Prediction Guard & Dialogue Safety

- Feature scope uses general `Name/Term Ambiguity Guard`; Helen/Helena is only an example, not the whole feature.
- If user gives a small example, treat it as a test case, not as the entire feature name/scope.
- Main Commander is `Raizei`.
- `Mangi Security Team Leader` is an exact speaker/NPC display label in story context.
- `Tlazo` is a unique term/review Yellow, not NPC global unless later evidence confirms otherwise.
- Prediction/Repair Text must be guarded with Green/Yellow/Red labels and must not create hallucination.
- UI/loading/battle phrases must be filtered before translation/cache.
- Add Dialogue Timeout Safety so a new dialog cannot finish without any visible translation.
- Preserve v8.8.6 low-OCR 40% improvement; do not make OCR low profiles “rabun” again.


## v8.8.8 Addendum — Offline Replay, Registry Expansion, Interval Safety

- Add Offline Replay Benchmark and Long Session Analyzer as tools to measure failure patterns, not memorize old story lines.
- Add Mode Policy Manager foundation for Auto/Interval/Freeze separation.
- Add Interval Fast-Skip Safety foundation.
- Registry expansion from v8.8.7 recording:
  - Main Commander: Raizei.
  - Distinct entities: Heli, Helen, Helena.
  - Additional characters/speakers: Darture, Mayling, Groza, Krolik, Vepley, Nemesis, Colphne, Carmen, Berryfield, Cocoon, Lentine, DP-12, Balthilde, Nikketa, Dushevnaya, KSVK, Suomi.
  - Speaker labels: Mangi Security Team Leader, Shadow Figure, Shadowy Figure.
  - Relation candidate: Anfiya Sharapova = older sister/person who named Colphne, Yellow review.
  - Unique terms: Tlazo, Chlovey, Odesa, Varjagers, Sangvis Ferri, Relics, Central Army Emergency First Response, Medical Chemical Equipment, Medical Team.
- Preserve OCR 40% readability improvements; do not make Lite/Fast low-OCR profiles rabun again.


## v8.8.8 R2 Hotfix Addendum

- v8.8.8 initial patch only added foundations; v8.8.8 R2 activates visible entity labeling and fixes Prediction Guard false positives.
- Fixed bug where `Hell -> Heli` Red block appeared on unrelated OCR lines.
- Entity labels now include exact prefixes like `Raizei`, `Darture`, `Poludnitsa`, `Anfiya Sharapova`, `Mangi Security Team Leader`, `Shadow Figure`, `Shadowy Figure`.
- `Poludnitsa` added as story entity/name candidate.
- Green/Yellow/Red should now appear as speaker confidence badge when entity prefix is detected.
- Mode policy telemetry must no longer stay at 0 for active sessions.
- Interval Fast-Skip Safety is connected to translation-hold emergency path.
- Keep low-OCR 40% improvements intact.


## v8.8.9 Addendum — Prediction Guard Activation, Full Output Guard, Anti-Stale New-Turn Commit

- User confirmed OCR readability at 40–50% has improved and must not be regressed.
- v8.8.9 focuses on post-OCR pipeline: Prediction/Repair Guard, full-output translation, new-dialog commit, stale overlay limit, UI filter, and cache safety.
- Added `Kenny` as exact Green story speaker.
- Added guarded alias family for `bathildel`/`Bathildel`/`balthildel`/`Balthildel` to map into the existing `Balthilde` canonical family while retaining `Bathilde` as review/exact evidence.
- PredictionGuard now supports registered alias prefix repair, not only exact prefix matching.
- Prediction metadata (`speaker_confidence_label`, kind, events) is propagated to overlay metadata so Green/Yellow/Red can be visible.
- New-turn source preview prevents stale last-good from covering a fresh dialogue while final translation is still pending.
- FullOutputGuard prevents low-coverage final output from causing a long hold; it uses anchor/source-safe no-cache preview instead.
- UI filter v3 catches fuzzy loading/challenge/supply/progress leaks.
- Auto/Interval manual burst detection handles fast manual story clicks.


## v8.9.2-R4 Addendum — Audio Model Recovery Hotfix

- OCR and Audio remain mutually exclusive; changing source stops the previous runtime.
- Guided/Expert UI from R2 and Audio CPU behavior from R3 are preserved.
- R3 live test reached faster-whisper model loading but the cached `Systran/faster-whisper-base` snapshot was incomplete: `config.json`, `tokenizer.json`, and `vocabulary.txt` were missing after a `WinError 10054` Hub interruption.
- Root cause inside ORT: readiness accepted a lone `model.bin` or prepared marker, so a partial snapshot could pass the launcher guard.
- R4 requires `config.json`, `model.bin`, `preprocessor_config.json`, `tokenizer.json`, and a valid `vocabulary.*` before Audio is ready.
- Model setup uses a canonical local folder, retries three times, reuses the existing cache, and switches to one transfer worker after the first failure. It must not delete a large completed blob merely because metadata/tokenizer files are missing.
- Normal Audio start loads the validated local folder with `local_files_only=True`; network is required only to complete the first setup for a selected model profile.
- UI distinguishes dependency readiness from model readiness and lists missing/invalid model files.
- Isolasi Suara remains unavailable. CPU INT8, Normal/VAD, Speed/Normal/Accurate, bounded queues, and generation guards remain unchanged.


## v8.9.2-R5 Addendum — Audio Model Compatibility Hotfix

- A live Speed-profile setup reached `MODEL_INCOMPLETE` with only `preprocessor_config.json` missing after three attempts.
- The official Systran CTranslate2 repositories for `tiny`, `base`, and `small` contain `config.json`, `model.bin`, `tokenizer.json`, and `vocabulary.txt`, but do not contain `preprocessor_config.json`.
- faster-whisper falls back to its default feature-extractor configuration when `preprocessor_config.json` is absent.
- R5 therefore requires the four core assets and tracks `preprocessor_config.json` as optional diagnostic metadata.
- A complete cached model must skip network download, then pass an actual local `WhisperModel` construction using CPU INT8 and `local_files_only=True` before setup reports success.
- Missing core assets must still produce `MODEL_INCOMPLETE`; R5 must not weaken protection against genuinely partial snapshots.
- UI, user configuration, OCR behavior, Audio profiles, WASAPI selection, and Isolation status remain unchanged.


## v8.9.2-R6 Addendum — Audio Native Crash Isolation Hotfix

- Live R5 testing reached `MODEL_READY`, `LISTENING`, and a valid transcript, then the WebUI-managed Audio process exited with decimal code `3221225477`, equivalent to Windows `0xC0000005` native access violation.
- Absence of `Audio sidecar berhenti` and absence of a `displayed` event place the failure in the parent process after transcript delivery, where ORTCore Fast V2/CTranslate2 was lazily initialized in a Python thread.
- R6 moves Audio translation into `audio_translation_sidecar.py`; the PyQt parent no longer imports or constructs the native TranslationEngine.
- Translation preload starts before ASR, uses CT2 CPU INT8 with packed GEMM disabled, and limits translation to 1–2 CPU threads while leaving the ASR profile budget unchanged.
- The coordinator retains one in-flight transcript and one latest pending transcript. A crashed in-flight request is replayed with its generation identity; stale results remain blocked.
- The first translation-process exit triggers exactly one isolated recovery process with `ORT_DISABLE_CT2=1`, routing through Argos. A second native failure cannot terminate ASR, overlay, or WebUI.
- New diagnostics record translation process state/mode, exit code, normalized access-violation flag, restart count, and safe-mode result identity.
- UI, OCR behavior, model selection, WASAPI choice, Audio profiles, cache/model folders, and Isolasi Suara status remain unchanged.

## v8.9.6 Addendum — Real-Time Cloud Enforcement

- Log pengguna membuktikan v8.9.5 tidak menjalankan Azure: requested_engine=azure_fallback tetapi effective_engine=local_guard, cloud_ready=0, effective_mode=cpu_guard, dan ASR base CPU memproses segmen 1.6–8 detik.
- Karena itu tidak ada cloud interim/final; perilaku pause/play tetap sama seperti local segmentation.
- Live Media Azure/Azure Fallback sekarang wajib lulus network test saat Start.
- Startup fallback ke local_guard diblokir. Local fallback hanya boleh terjadi setelah cloud session aktif lalu gagal.
- Mode Local tetap tersedia secara eksplisit dan harus diberi keterangan bahwa ia bukan phone-style streaming subtitle.
