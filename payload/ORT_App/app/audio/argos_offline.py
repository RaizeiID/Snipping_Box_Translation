from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


ARGOS_CHUNK_TYPE = "MINISBD"
ARGOS_DEVICE_TYPE = "cpu"


class ArgosOfflineError(RuntimeError):
    """Raised when an installed Argos bridge cannot be used fully offline."""


@dataclass(frozen=True)
class ArgosOfflineInfo:
    source_code: str
    target_code: str
    chunk_type: str
    device_type: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_code": self.source_code,
            "target_code": self.target_code,
            "chunk_type": self.chunk_type,
            "device_type": self.device_type,
        }


def configure_argos_offline_environment() -> dict[str, str]:
    """Force Argos to use MiniSBD instead of Stanza.

    ORT translates short ASR clauses. MiniSBD is sufficient for this input and,
    unlike the Stanza path, does not try to download a resources manifest during
    the first translation. Argos is kept on CPU so its bridge does not compete
    with the ASR CUDA process for VRAM.
    """

    os.environ["ARGOS_CHUNK_TYPE"] = ARGOS_CHUNK_TYPE
    os.environ["ARGOS_DEVICE_TYPE"] = ARGOS_DEVICE_TYPE
    os.environ.setdefault("ARGOS_DEBUG", "0")

    # If Argos settings were imported earlier in the same process, update the
    # already-materialized enum as well. This keeps the rule deterministic.
    try:
        import argostranslate.settings as settings

        chunk_enum = getattr(settings, "ChunkType", None)
        minisbd = getattr(chunk_enum, "MINISBD", None) if chunk_enum is not None else None
        if minisbd is not None:
            settings.chunk_type = minisbd
    except Exception:
        # Import errors are reported later by get_translation_pair with context.
        pass

    return {
        "chunk_type": os.environ["ARGOS_CHUNK_TYPE"],
        "device_type": os.environ.get("ARGOS_DEVICE_TYPE", ARGOS_DEVICE_TYPE),
    }


def get_translation_pair(source_code: str, target_code: str) -> tuple[Any, ArgosOfflineInfo]:
    source = str(source_code or "").strip().lower()
    target = str(target_code or "").strip().lower()
    if not source or not target:
        raise ArgosOfflineError("Kode bahasa Argos tidak lengkap")

    config = configure_argos_offline_environment()
    try:
        import argostranslate.translate
    except Exception as exc:
        raise ArgosOfflineError(
            f"Argos Translate tidak dapat diimpor: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        installed = argostranslate.translate.get_installed_languages()
        source_language = next(
            (lang for lang in installed if str(getattr(lang, "code", "")).lower() == source),
            None,
        )
        target_language = next(
            (lang for lang in installed if str(getattr(lang, "code", "")).lower() == target),
            None,
        )
        translator = (
            source_language.get_translation(target_language)
            if source_language is not None and target_language is not None
            else None
        )
    except Exception as exc:
        raise ArgosOfflineError(
            f"Gagal membuka pasangan Argos {source}->{target}: {type(exc).__name__}: {exc}"
        ) from exc

    if translator is None:
        raise ArgosOfflineError(
            f"Paket bahasa Argos {source}->{target} belum terpasang"
        )

    return translator, ArgosOfflineInfo(
        source_code=source,
        target_code=target,
        chunk_type=config["chunk_type"],
        device_type=config["device_type"],
    )


def translate_offline(text: str, source_code: str, target_code: str) -> tuple[str, ArgosOfflineInfo]:
    translator, info = get_translation_pair(source_code, target_code)
    try:
        result = str(translator.translate(str(text or "")) or "").strip()
    except Exception as exc:
        raise ArgosOfflineError(
            f"Terjemahan Argos {source_code}->{target_code} gagal: {type(exc).__name__}: {exc}"
        ) from exc
    return result, info
