
## R5 — Resumable Provider Download & Network Recovery

- Hugging Face metadata and model files are downloaded sequentially (`max_workers=1`) to avoid parallel HEAD request disconnects.
- Transient network failures use bounded exponential retry with visible attempt, delay, and error details.
- Download and ETag timeouts are increased for large ONNX files.
- Completed cache files are reused; setup can be repeated with the same target to continue without deleting the cache.
- Partial download manifests are persisted after each completed file so Check Model Status reports incomplete CPU/GPU accurately.
- Reazon runtime dependencies are probed and reused instead of repeating Git/PIP installation after a download-only failure.
- Setup log reports Hugging Face authentication, cache reuse, retry state, and recovery instructions.
