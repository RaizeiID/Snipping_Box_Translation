# Provider attribution and license policy

| Project / concept | Intended use | Integration boundary | License note |
|---|---|---|---|
| Silero VAD | Optional VAD provider | ONNX adapter; model in ORT_Runtime | MIT |
| WhisperStreaming | Confirmed-prefix/local-agreement reference | Clean ORT implementation | MIT |
| SimulStreaming | Streaming policy reference | Clean ORT implementation / optional adapter | MIT |
| WhisperLive | Persistent ASR worker reference | Optional local worker adapter | MIT |
| MORT | Multi-region OCR architecture reference | New ORT adapter; no direct application copy | MIT |
| Textractor | Optional game text hook | External process connector only | GPLv3 external boundary |
| LunaTranslator | Ecosystem/reference and optional connector | External process connector only | GPLv3 external boundary |

Provider licenses and upstream terms must be checked again before bundling any binary, model, or source-derived implementation.
