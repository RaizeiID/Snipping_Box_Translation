from __future__ import annotations

import html
import json
from datetime import datetime

from .paths import ensure_v9_roots
from .pipeline import (
    CATEGORIES,
    diagram_html,
    pipeline_payload,
    preset,
    presets,
    provider_table_html,
    save_custom_plan,
    status_text,
)
from .registry import choices, export_registry, provider
from .streaming.confirmed_prefix import demo_hypotheses


def architecture_preset_choices() -> list[tuple[str, str]]:
    return [(item.label, item.preset_id) for item in presets()]


def architecture_provider_choices(category: str) -> list[tuple[str, str]]:
    return choices(category)


def _render(selections: dict[str, str], *, preset_id: str, label: str) -> tuple[str, str, str, str]:
    payload = pipeline_payload(selections, preset_id=preset_id, label=label)
    registry_warning = ""
    try:
        export_registry()
    except Exception as exc:
        registry_warning = f" Provider registry runtime tidak dapat ditulis: {exc}"
    return (
        diagram_html(payload),
        provider_table_html(payload),
        json.dumps(payload, ensure_ascii=False, indent=2),
        status_text(payload) + registry_warning,
    )


def architecture_initial_payload() -> tuple:
    return architecture_apply_preset("original_audio")


def architecture_apply_preset(preset_id: str) -> tuple:
    item = preset(preset_id)
    selections = item.selections()
    rendered = _render(selections, preset_id=item.preset_id, label=item.label)
    return (
        selections["source"], selections["vad"], selections["asr"],
        selections["streaming"], selections["translation"], selections["overlay"],
        *rendered,
    )


def architecture_refresh(source: str, vad: str, asr: str, streaming: str, translation: str, overlay: str) -> tuple[str, str, str, str]:
    selections = {
        "source": source, "vad": vad, "asr": asr,
        "streaming": streaming, "translation": translation, "overlay": overlay,
    }
    return _render(selections, preset_id="custom:preview", label="Custom Preview")


def architecture_save_custom(name: str, source: str, vad: str, asr: str, streaming: str, translation: str, overlay: str) -> str:
    selections = {
        "source": source, "vad": vad, "asr": asr,
        "streaming": streaming, "translation": translation, "overlay": overlay,
    }
    path, payload = save_custom_plan(name, selections)
    return f"Preset tersimpan: {path} | available={payload['available']} | pipeline Original tidak berubah."


def architecture_export_plan(source: str, vad: str, asr: str, streaming: str, translation: str, overlay: str) -> str:
    roots = ensure_v9_roots()
    selections = {
        "source": source, "vad": vad, "asr": asr,
        "streaming": streaming, "translation": translation, "overlay": overlay,
    }
    payload = pipeline_payload(selections, preset_id="export", label="Open Architecture Export")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = roots["exports"] / f"open_architecture_plan_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Rencana arsitektur diekspor ke: {path}"


def architecture_compare_presets(left_id: str, right_id: str) -> str:
    left = preset(left_id)
    right = preset(right_id)
    lines = [
        f"### Perbandingan: {left.label} vs {right.label}",
        "| Layer | Pipeline A | Pipeline B | Perubahan |",
        "|---|---|---|---|",
    ]
    for category in CATEGORIES:
        left_spec = provider(getattr(left, category))
        right_spec = provider(getattr(right, category))
        changed = "Berbeda" if left_spec.provider_id != right_spec.provider_id else "Sama"
        lines.append(f"| {category.title()} | {left_spec.label} | {right_spec.label} | {changed} |")
    lines.append("")
    lines.append("Pipeline A/B pada halaman ini adalah rencana konfigurasi. Audio/OCR produksi tidak dijalankan dua kali secara diam-diam.")
    return "\n".join(lines)


def confirmed_prefix_demo(hypotheses: str, agreement_passes: int = 2) -> tuple[str, str]:
    rows = demo_hypotheses(hypotheses, agreement_passes)
    html_rows = []
    for row in rows:
        html_rows.append(
            "<tr>"
            f"<td>{row['step']}</td><td>{html.escape(row['hypothesis'])}</td>"
            f"<td>{html.escape(row['confirmed'])}</td><td>{html.escape(row['live_tail'])}</td>"
            f"<td>{html.escape(row['display'])}</td>"
            "</tr>"
        )
    table = (
        "<div class='oa-table-wrap'><table class='oa-table'><thead><tr>"
        "<th>Step</th><th>ASR hypothesis</th><th>Confirmed</th><th>Live tail</th><th>Display</th>"
        "</tr></thead><tbody>" + "".join(html_rows) + "</tbody></table></div>"
    )
    return table, json.dumps(rows, ensure_ascii=False, indent=2)
