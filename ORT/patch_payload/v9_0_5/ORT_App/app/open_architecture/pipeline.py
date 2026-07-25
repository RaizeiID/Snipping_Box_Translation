from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from build_info import APP_VERSION_TAG

from .paths import ensure_v9_roots, lab_data_root
from .registry import CATEGORIES, provider, selected_payload


@dataclass(frozen=True)
class PipelinePreset:
    preset_id: str
    label: str
    description: str
    source: str
    vad: str
    asr: str
    streaming: str
    translation: str
    overlay: str = "ort_overlay"
    experimental: bool = False

    def selections(self) -> dict[str, str]:
        return {category: getattr(self, category) for category in CATEGORIES}


_PRESETS: tuple[PipelinePreset, ...] = (
    PipelinePreset(
        "original_audio", "ORT Original · Audio", "Baseline produksi ORT tanpa provider eksperimental.",
        "ort_wasapi", "ort_rms_vad", "ort_faster_whisper", "ort_rolling_context", "ortcore_fast_v2",
    ),
    PipelinePreset(
        "original_ocr", "ORT Original · OCR", "Baseline OCR produksi ORT.",
        "ort_ocr", "ort_rms_vad", "ort_faster_whisper", "ort_rolling_context", "ortcore_fast_v2",
    ),
    PipelinePreset(
        "japanese_live_lab", "Japanese Live Lab · Recommended",
        "Executor Audio Lab: WASAPI, RMS/VAD, Japanese Specialist, Confirmed Prefix, dan bridge JA→EN→ID.",
        "ort_wasapi", "ort_rms_vad", "ort_japanese_specialist", "confirmed_prefix", "ja_en_id_bridge",
        experimental=True,
    ),
    PipelinePreset(
        "japanese_accuracy_lab", "Japanese Accuracy Lab",
        "Kotoba CUDA, Silero endpointing, confirmed prefix, dan rute direct JA→ID ketika provider tersedia.",
        "ort_wasapi", "silero_vad", "ort_japanese_specialist", "confirmed_prefix", "direct_ja_id",
        experimental=True,
    ),
    PipelinePreset(
        "japanese_safe_bridge", "Japanese Safe Bridge",
        "Japanese Specialist dengan confirmed prefix namun tetap memakai rute bridge yang sudah stabil.",
        "ort_wasapi", "hybrid_rms_silero", "ort_japanese_specialist", "confirmed_prefix", "ja_en_id_bridge",
        experimental=True,
    ),
    PipelinePreset(
        "long_dialogue_lab", "Long Dialogue Lab",
        "Worker persisten dan local agreement untuk diskusi panjang serta pergantian pembicara cepat.",
        "ort_wasapi", "hybrid_rms_silero", "whisperlive_worker", "local_agreement", "ortcore_fast_v2",
        experimental=True,
    ),
    PipelinePreset(
        "ocr_research_lab", "OCR Research Lab",
        "Multi-region OCR dengan consensus dan overlay ORT.",
        "multi_region_ocr", "ort_rms_vad", "ort_faster_whisper", "ort_rolling_context", "ortcore_fast_v2",
        experimental=True,
    ),
)

PRESET_BY_ID = {item.preset_id: item for item in _PRESETS}


def presets() -> tuple[PipelinePreset, ...]:
    return _PRESETS


def preset(preset_id: str) -> PipelinePreset:
    return PRESET_BY_ID.get(str(preset_id), PRESET_BY_ID["original_audio"])


def validate_selections(selections: dict[str, str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for category in CATEGORIES:
        value = str(selections.get(category, ""))
        try:
            spec = provider(value)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if spec.category != category:
            errors.append(f"{value} adalah provider {spec.category}, bukan {category}.")
    return not errors, errors


def pipeline_payload(selections: dict[str, str], *, preset_id: str = "custom", label: str = "Custom Lab") -> dict:
    valid, errors = validate_selections(selections)
    rows = selected_payload(selections[category] for category in CATEGORIES if selections.get(category)) if valid else []
    missing = [item for item in rows if not item["available"]]
    return {
        "schema": 1,
        "version": APP_VERSION_TAG,
        "preset_id": preset_id,
        "label": label,
        "experimental": preset_id not in {"original_audio", "original_ocr"},
        "production_pipeline_untouched": True,
        "valid": valid,
        "errors": errors,
        "selections": dict(selections),
        "providers": rows,
        "available": not missing and valid,
        "missing_or_setup_required": [item["provider_id"] for item in missing],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def diagram_html(payload: dict) -> str:
    cards: list[str] = []
    for category in CATEGORIES:
        provider_id = payload.get("selections", {}).get(category, "")
        if not provider_id:
            continue
        item = provider(provider_id)
        ready, reason = item.availability()
        cls = "oa-ready" if ready else "oa-warn"
        cards.append(
            f"<div class='oa-node {cls}'><span>{html.escape(category.upper())}</span>"
            f"<b>{html.escape(item.label)}</b><small>{html.escape(reason)}</small></div>"
        )
    arrow = "<div class='oa-arrow'>↓</div>"
    return (
        "<div class='oa-diagram'>" + arrow.join(cards) + "</div>"
        "<div class='oa-safety'>Pipeline ini hanya tersimpan di Open Architecture Lab. "
        "Pipeline Original OCR/Audio tidak diganti sampai aktivasi eksperimental dibuat secara eksplisit.</div>"
    )


def provider_table_html(payload: dict) -> str:
    rows: list[str] = []
    for item in payload.get("providers", []):
        state = "Ready" if item["available"] else "Setup required"
        badge = "oa-badge-ready" if item["available"] else "oa-badge-warn"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['category'])}</td>"
            f"<td><b>{html.escape(item['label'])}</b><br><small>{html.escape(item['description'])}</small></td>"
            f"<td>{html.escape(item['origin'])}</td>"
            f"<td>{html.escape(item['license_name'])}</td>"
            f"<td><span class='{badge}'>{state}</span><br><small>{html.escape(item['availability_reason'])}</small></td>"
            "</tr>"
        )
    return (
        "<div class='oa-table-wrap'><table class='oa-table'><thead><tr>"
        "<th>Layer</th><th>Provider</th><th>Origin</th><th>License</th><th>Status</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def status_text(payload: dict) -> str:
    if not payload.get("valid"):
        return "Konfigurasi tidak valid: " + " | ".join(payload.get("errors", []))
    missing = payload.get("missing_or_setup_required", [])
    if missing:
        return (
            "Rencana tersimpan sebagai eksperimen. Provider berikut belum siap: "
            + ", ".join(missing)
            + ". ORT Original tetap menjadi jalur aktif."
        )
    return "Seluruh provider pada rencana tersedia. Status ini belum mengaktifkan pipeline eksperimen secara otomatis."


def save_custom_plan(name: str, selections: dict[str, str]) -> tuple[Path, dict]:
    roots = ensure_v9_roots()
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (name.strip() or "custom_lab"))
    payload = pipeline_payload(selections, preset_id=f"custom:{safe_name}", label=name.strip() or "Custom Lab")
    path = roots["lab_data"] / "presets" / f"{safe_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, payload


def load_custom_plans() -> list[dict]:
    folder = lab_data_root() / "presets"
    if not folder.exists():
        return []
    result: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                result.append(data)
        except Exception:
            continue
    return result
