"""v8.7.6 backend-safe immutable entity spans.

v8.7.4 protected post-processing spans correctly, but still passed backend
placeholder strings (``__ORT_BKEND_###__``) through Argos.  Some backends
mutated those strings into visible ``ORT_BEND/BKED`` fragments.  v8.7.6 keeps
canonical entities outside *both* backend translation and IDN/QA rewriting:
only TextSpan payloads are translated or naturalized, and EntitySpan values
are composed back unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from app.identity.speaker_registry import find_protected_entities, has_internal_entity_token


@dataclass(frozen=True)
class TextSpan:
    text: str


@dataclass(frozen=True)
class EntitySpan:
    canonical_id: str
    display_name: str


Span = TextSpan | EntitySpan


def _canonical_id(name: str) -> str:
    return "".join(ch.lower() for ch in str(name) if ch.isalnum())


def split_entity_spans(text: str, game: str) -> list[Span]:
    """Split text using longest-match-first protected terms from the registry."""
    source = str(text or "")
    matches = find_protected_entities(source, game)
    if not matches:
        return [TextSpan(source)]
    spans: list[Span] = []
    cursor = 0
    for start, end, name in matches:
        if start > cursor:
            spans.append(TextSpan(source[cursor:start]))
        spans.append(EntitySpan(_canonical_id(name), name))
        cursor = end
    if cursor < len(source):
        spans.append(TextSpan(source[cursor:]))
    return spans


def _process_text_preserving_spacing(text: str, processor: Callable[[str], str]) -> str:
    if not text:
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()):]
    core = text.strip()
    if not core:
        return text
    return leading + str(processor(core) or core) + trailing


def translate_spans(spans: list[Span], translator: Callable[[str], str]) -> tuple[str, int]:
    """Translate pre-split spans, preserving EntitySpan values exactly."""
    if not any(isinstance(span, EntitySpan) for span in spans):
        source = "".join(span.text for span in spans if isinstance(span, TextSpan))
        return str(translator(source) or source), 1
    rendered: list[str] = []
    calls = 0
    for span in spans:
        if isinstance(span, EntitySpan):
            rendered.append(span.display_name)
        else:
            core = span.text.strip()
            if core and any(ch.isalpha() for ch in core):
                rendered.append(_process_text_preserving_spacing(span.text, translator))
                calls += 1
            else:
                rendered.append(span.text)
    return "".join(rendered).strip(), calls


def translate_entity_safe_source(text: str, game: str, translator: Callable[[str], str]) -> tuple[str, list[Span], int]:
    """Translate only TextSpan payloads and compose canonical entities untouched.

    Returns ``(rendered_text, spans, backend_call_count)``. Ordinary lines
    without protected entities still make exactly one backend request.
    Name-heavy lines may make multiple small text-span requests; this is an
    intentional correctness tradeoff that prevents any internal marker from
    ever entering the backend.
    """
    spans = split_entity_spans(text, game)
    rendered, calls = translate_spans(spans, translator)
    return rendered, spans, calls


def process_entity_safe(text: str, game: str, processor: Callable[[str], str]) -> tuple[str, list[Span]]:
    """Post-process only non-entity spans after backend translation."""
    spans = split_entity_spans(text, game)
    rendered: list[str] = []
    for span in spans:
        if isinstance(span, EntitySpan):
            rendered.append(span.display_name)
        else:
            rendered.append(_process_text_preserving_spacing(span.text, processor))
    return "".join(rendered).strip(), spans


def spans_metadata(spans: Iterable[Span]) -> list[dict]:
    return [
        {"type": "entity", "canonical_id": s.canonical_id, "display_name": s.display_name}
        for s in spans if isinstance(s, EntitySpan)
    ]


def residual_internal_marker(text: str) -> bool:
    return has_internal_entity_token(text)
