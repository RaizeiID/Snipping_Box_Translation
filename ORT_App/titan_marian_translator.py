#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optional Marian (Firefox/Bergamot-style Marian family) helper for TitanMainV3.

This uses HuggingFace transformers MarianMT models.
It is OPTIONAL: TitanMainV3 will run fine without it.

Install (in Titan environment, not venv-lt):
  pip install transformers sentencepiece

Env:
  TITAN_MARIAN_ZH_EN = Helsinki-NLP/opus-mt-zh-en
  TITAN_MARIAN_EN_ID = Helsinki-NLP/opus-mt-en-id
  TITAN_MARIAN_DEVICE = cpu / cuda

Notes:
- First run will download models (large).
- This helper is intended as a "race helper" for BOX translation, not CAS.
"""
from __future__ import annotations

import os
import re
import time
from typing import Callable, Optional

# Lazy imports
# transformers is heavy; we only import when creating the core.
from transformers import MarianMTModel, MarianTokenizer  # type: ignore


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in (text or ""))


class MarianTranslatorCore:
    def __init__(self, log_fn: Callable[[str], None]):
        self.log = log_fn
        self.device = (os.environ.get("TITAN_MARIAN_DEVICE") or "cpu").strip().lower()
        self.model_zh_en_name = (os.environ.get("TITAN_MARIAN_ZH_EN") or "Helsinki-NLP/opus-mt-zh-en").strip()
        self.model_en_id_name = (os.environ.get("TITAN_MARIAN_EN_ID") or "Helsinki-NLP/opus-mt-en-id").strip()

        self._tok_zh_en: Optional[MarianTokenizer] = None
        self._mod_zh_en: Optional[MarianMTModel] = None
        self._tok_en_id: Optional[MarianTokenizer] = None
        self._mod_en_id: Optional[MarianMTModel] = None

    def _load_zh_en(self):
        if self._mod_zh_en is not None:
            return
        self.log(f"[MARIAN] loading {self.model_zh_en_name} ...")
        self._tok_zh_en = MarianTokenizer.from_pretrained(self.model_zh_en_name)
        self._mod_zh_en = MarianMTModel.from_pretrained(self.model_zh_en_name)
        if self.device == "cuda":
            self._mod_zh_en = self._mod_zh_en.to("cuda")
        self._mod_zh_en.eval()
        self.log("[MARIAN] zh->en READY")

    def _load_en_id(self):
        if self._mod_en_id is not None:
            return
        self.log(f"[MARIAN] loading {self.model_en_id_name} ...")
        self._tok_en_id = MarianTokenizer.from_pretrained(self.model_en_id_name)
        self._mod_en_id = MarianMTModel.from_pretrained(self.model_en_id_name)
        if self.device == "cuda":
            self._mod_en_id = self._mod_en_id.to("cuda")
        self._mod_en_id.eval()
        self.log("[MARIAN] en->id READY")

    def _translate_one(self, model: MarianMTModel, tok: MarianTokenizer, text: str) -> str:
        import torch  # lazy
        with torch.no_grad():
            batch = tok([text], return_tensors="pt", truncation=True)
            if self.device == "cuda":
                batch = {k: v.to("cuda") for k, v in batch.items()}
            gen = model.generate(**batch, max_length=512)
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]
        return out

    def translate(self, text: str) -> str:
        src = (text or "").strip()
        if not src:
            return ""

        # Simple heuristic routing:
        # - If contains CJK => zh->en then en->id
        # - Else => en->id
        try:
            if _has_cjk(src):
                self._load_zh_en()
                self._load_en_id()
                assert self._mod_zh_en and self._tok_zh_en and self._mod_en_id and self._tok_en_id
                mid = self._translate_one(self._mod_zh_en, self._tok_zh_en, src)
                out = self._translate_one(self._mod_en_id, self._tok_en_id, mid)
                return out
            else:
                self._load_en_id()
                assert self._mod_en_id and self._tok_en_id
                return self._translate_one(self._mod_en_id, self._tok_en_id, src)
        except Exception as e:
            # fail-soft
            self.log(f"[MARIAN] fail: {e}")
            return ""
