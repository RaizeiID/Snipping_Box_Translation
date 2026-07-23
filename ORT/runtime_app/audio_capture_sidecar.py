from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from app.audio.profiles import get_audio_profile
from app.audio.streaming import LiveAudioSegmenter, audio_rms, pcm16_to_mono_float, resample_linear


EVENT_PREFIX = "ORT_AUDIO_CAPTURE_EVENT "
TARGET_SAMPLE_RATE = 16000
STOP_REQUESTED = False


def emit_event(event_type: str, **payload: Any) -> None:
    event = {"type": str(event_type), "ts": time.time(), **payload}
    print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def _signal_stop(*_args: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def _install_signal_handlers() -> None:
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _signal_stop)
            except Exception:
                pass


def _resolve_loopback_device(manager: Any, requested_index: int) -> dict:
    loopbacks = [dict(item) for item in manager.get_loopback_device_info_generator()]
    if requested_index >= 0:
        for item in loopbacks:
            if int(item.get("index", -1)) == requested_index:
                return item
        raise RuntimeError(f"Perangkat loopback index {requested_index} tidak ditemukan.")
    try:
        return dict(manager.get_default_wasapi_loopback())
    except Exception:
        pass
    if loopbacks:
        return loopbacks[0]
    raise RuntimeError("WASAPI loopback tidak ditemukan. Pastikan perangkat output aktif.")


def _write_segment(spool_dir: Path, sequence: int, audio: np.ndarray) -> dict:
    segment_id = f"seg-{int(time.time() * 1000)}-{sequence:06d}"
    final_path = spool_dir / f"{segment_id}.npy"
    temporary_path = spool_dir / f".{segment_id}.tmp.npy"
    np.save(temporary_path, np.asarray(audio, dtype=np.float32), allow_pickle=False)
    os.replace(temporary_path, final_path)
    return {
        "segment_id": segment_id,
        "path": str(final_path),
        "kind": "npy",
        "audio_seconds": round(float(audio.size) / TARGET_SAMPLE_RATE, 3),
        "rms": round(audio_rms(audio), 6),
        "created_at": time.time(),
    }


def capture_live(profile_key: str, processing: str, device_index: int, spool_dir: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Audio internal langsung memerlukan Windows WASAPI. Gunakan File audio uji pada sistem lain.")
    import pyaudiowpatch as pyaudio

    profile = get_audio_profile(profile_key)
    segmenter = LiveAudioSegmenter(profile, processing=processing, sample_rate=TARGET_SAMPLE_RATE)
    spool_dir.mkdir(parents=True, exist_ok=True)
    last_meter = 0.0
    sequence = 0
    with pyaudio.PyAudio() as manager:
        device = _resolve_loopback_device(manager, int(device_index))
        channels = max(1, int(device.get("maxInputChannels", 1)))
        source_rate = int(float(device.get("defaultSampleRate", 48000)))
        source_name = str(device.get("name", "WASAPI Loopback"))
        source_index = int(device.get("index", -1))
        frames_per_buffer = max(512, min(2048, int(source_rate * 0.025)))
        emit_event(
            "state",
            state="LISTENING",
            device=source_name,
            device_index=source_index,
            channels=channels,
            sample_rate=source_rate,
            processing=processing,
        )
        with manager.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=source_rate,
            frames_per_buffer=frames_per_buffer,
            input=True,
            input_device_index=source_index,
        ) as stream:
            while not STOP_REQUESTED:
                payload = stream.read(frames_per_buffer, exception_on_overflow=False)
                mono = pcm16_to_mono_float(payload, channels)
                audio_16k = resample_linear(mono, source_rate, TARGET_SAMPLE_RATE)
                now = time.monotonic()
                if now - last_meter >= 0.5:
                    emit_event(
                        "meter",
                        rms=round(audio_rms(audio_16k), 6),
                        speech_active=segmenter.speech_active,
                        threshold=round(segmenter.threshold, 6),
                    )
                    last_meter = now
                segment = segmenter.feed(audio_16k)
                if segment is not None:
                    sequence += 1
                    emit_event("segment", **_write_segment(spool_dir, sequence, segment))
    remainder = segmenter.flush()
    if remainder is not None:
        sequence += 1
        emit_event("segment", **_write_segment(spool_dir, sequence, remainder))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORT Audio capture and VAD sidecar")
    parser.add_argument("--profile", default="normal", choices=["speed", "normal", "accurate"])
    parser.add_argument("--processing", default="vad", choices=["normal", "vad"])
    parser.add_argument("--device-index", type=int, default=-1)
    parser.add_argument("--spool-dir", required=True)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    _install_signal_handlers()
    try:
        capture_live(args.profile, args.processing, int(args.device_index), Path(args.spool_dir).expanduser().resolve())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        emit_event("error", stage="capture", message=str(exc))
        return 1
    finally:
        emit_event("state", state="CAPTURE_STOPPED")


if __name__ == "__main__":
    raise SystemExit(main())
