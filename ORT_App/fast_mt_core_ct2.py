# fast_mt_core_ct2.py
# Offline tokenizer using local SentencePiece (NO HuggingFace/transformers download).
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from typing import Optional

import ctranslate2
import sentencepiece as spm

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# ORT v9.0.7 R22: CT2 gets its own thread budget instead of inheriting
# OMP_NUM_THREADS. The translator used to be built with no thread argument at
# all, so it followed OMP -- which the resource ladder scales by thread_frac
# (0.30-1.00) for the benefit of OCR and torch. On the Efisien end that landed
# CT2 on one or two threads, and the measured cost is severe. Median over 60
# real lines from the field logs, 24-core machine:
#
#     1 thread 163 ms | 2: 105 | 3: 81 | 4: 77 | 6: 58 | 8: 49 | 12: 57
#
# So one thread is 3.3x slower than eight, and past eight it regresses -- an
# en->id OPUS-MT model at beam 1 is too small to keep more cores busy, and the
# synchronisation cost starts to dominate. The band below is that curve: never
# below the floor where latency falls off a cliff, never above the point where
# more cores stop paying. The ladder still moves CT2 inside the band, it just
# can no longer push it off either end.
_CT2_THREAD_FLOOR = 4
_CT2_THREAD_CEILING = 8


def resolve_ct2_threads(requested: int = 0) -> int:
    """Clamp a requested CT2 thread count into the measured useful band."""
    floor = max(1, int(os.environ.get("ORT_CT2_THREAD_FLOOR", _CT2_THREAD_FLOOR)))
    ceiling = max(floor, int(os.environ.get("ORT_CT2_THREAD_CEILING", _CT2_THREAD_CEILING)))
    if requested <= 0:
        for key in ("ORT_CT2_THREADS", "ORT_CPU_THREADS", "OMP_NUM_THREADS"):
            try:
                requested = int(os.environ.get(key, "0") or 0)
            except ValueError:
                requested = 0
            if requested > 0:
                break
    if requested <= 0:
        requested = ceiling
    # Never promise more threads than the machine has; a 4-core box would
    # otherwise be handed the 8-thread ceiling and thrash.
    cores = os.cpu_count() or requested
    return max(1, min(ceiling, max(floor, requested), cores))


def looks_like_cjk(text: str) -> bool:
    return bool(text and _CJK_RE.search(text))


@dataclass
class CT2Config:
    # Required
    model_dir_en_id: str

    # Where source.spm & target.spm live (optional if env var is set)
    spm_dir_en_id: Optional[str] = None

    # Optional pivot later
    model_dir_zh_en: Optional[str] = None
    spm_dir_zh_en: Optional[str] = None

    # Speed/quality
    beam_size: int = 1
    max_decoding_length: int = 256

    # Device
    device: str = "auto"          # "cpu" / "cuda" / "auto"
    device_index: int = 0

    # Compute type (simple, stable defaults)
    # For GPU speed you can try "int8_float16" later.
    compute_type: str = "int8"

    # 0 = derive from the environment, then clamp to the measured band.
    intra_threads: int = 0


class FastCT2Translator:
    """
    Ultra low-latency translator using CTranslate2 + local SentencePiece files.
    Drop-in replacement for offline_translate_ram(text)->str.
    """

    def __init__(self, cfg: CT2Config):
        self.cfg = cfg
        self._lock = threading.RLock()

        if not os.path.isdir(cfg.model_dir_en_id):
            raise FileNotFoundError(
            f"CT2 model_dir_en_id not found: {cfg.model_dir_en_id}\n"
            f"Hint: set env TITAN_CT2_EN_ID_DIR ke folder model CT2 en->id, atau letakkan model di ./models/ct2_opus_mt_en_id\n"
        )

        # Determine spm directory
        spm_dir = (
            cfg.spm_dir_en_id
            or os.environ.get("TITAN_SPM_EN_ID_DIR")
            or (cfg.model_dir_en_id if os.path.exists(os.path.join(cfg.model_dir_en_id, "source.spm")) else None)
        )

        if not spm_dir:
            raise FileNotFoundError(
                "Cannot find SentencePiece files source.spm/target.spm.\n"
                "Fix: copy source.spm+target.spm into models/ct2_opus_mt_en_id OR set TITAN_SPM_EN_ID_DIR."
            )

        src_spm = os.path.join(spm_dir, "source.spm")
        tgt_spm = os.path.join(spm_dir, "target.spm")
        if not os.path.exists(src_spm) or not os.path.exists(tgt_spm):
            raise FileNotFoundError(f"Missing SPM files in: {spm_dir} (need source.spm & target.spm)")

        # Load sentencepiece
        self.src_sp = spm.SentencePieceProcessor()
        self.tgt_sp = spm.SentencePieceProcessor()
        self.src_sp.load(src_spm)
        self.tgt_sp.load(tgt_spm)

        # Load CT2 translator
        self.ct2_threads = resolve_ct2_threads(cfg.intra_threads)
        # Reported so the runtime log shows the real budget, not the OMP value.
        os.environ["ORT_CT2_THREADS_USED"] = str(self.ct2_threads)
        self.tr_en_id = ctranslate2.Translator(
            cfg.model_dir_en_id,
            device=cfg.device,
            device_index=cfg.device_index,
            compute_type=cfg.compute_type,
            inter_threads=1,
            intra_threads=self.ct2_threads,
        )

        # Optional pivot init (not required for EN->ID usage)
        self.tr_zh_en = None
        self.src_sp_zh = None
        self.tgt_sp_en = None
        if cfg.model_dir_zh_en:
            if not os.path.isdir(cfg.model_dir_zh_en):
                raise FileNotFoundError(
            f"CT2 model_dir_zh_en not found: {cfg.model_dir_zh_en}\n"
            f"Hint: set env TITAN_CT2_ZH_EN_DIR ke folder model CT2 zh->en, atau letakkan model di ./models/ct2_opus_mt_zh_en\n"
        )

            spm_dir_zh = cfg.spm_dir_zh_en or os.environ.get("TITAN_SPM_ZH_EN_DIR")
            if spm_dir_zh:
                src2 = os.path.join(spm_dir_zh, "source.spm")
                tgt2 = os.path.join(spm_dir_zh, "target.spm")
                if os.path.exists(src2) and os.path.exists(tgt2):
                    self.src_sp_zh = spm.SentencePieceProcessor()
                    self.tgt_sp_en = spm.SentencePieceProcessor()
                    self.src_sp_zh.load(src2)
                    self.tgt_sp_en.load(tgt2)

                    self.tr_zh_en = ctranslate2.Translator(
                        cfg.model_dir_zh_en,
                        device=cfg.device,
                        device_index=cfg.device_index,
                        compute_type=cfg.compute_type,
                        inter_threads=1,
                        intra_threads=self.ct2_threads,
                    )

    def warmup(self):
        try:
            _ = self.translate("warmup.")
        except Exception:
            pass

    def _translate_spm(self, translator: ctranslate2.Translator,
                       src_sp: spm.SentencePieceProcessor,
                       tgt_sp: spm.SentencePieceProcessor,
                       text: str) -> str:
        src_tokens = src_sp.encode(text, out_type=str)
        # Ensure Marian-style end token
        if not src_tokens or src_tokens[-1] != "</s>":
            src_tokens.append("</s>")

        results = translator.translate_batch(
            [src_tokens],
            beam_size=self.cfg.beam_size,
            max_decoding_length=self.cfg.max_decoding_length,
        )

        hyp = results[0].hypotheses[0]
        hyp = [t for t in hyp if t not in ("</s>", "<pad>")]
        out = tgt_sp.decode(hyp)
        return (out or "").strip()

    def translate(self, text: str) -> str:
        if not text:
            return ""
        with self._lock:
            # Pivot if configured and CJK detected
            if self.tr_zh_en and self.src_sp_zh and self.tgt_sp_en and looks_like_cjk(text):
                mid = self._translate_spm(self.tr_zh_en, self.src_sp_zh, self.tgt_sp_en, text)
                return self._translate_spm(self.tr_en_id, self.src_sp, self.tgt_sp, mid)

            return self._translate_spm(self.tr_en_id, self.src_sp, self.tgt_sp, text)
