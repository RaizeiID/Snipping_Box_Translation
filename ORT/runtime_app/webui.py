from __future__ import annotations

import html
import json
import os
import threading
import time
import webbrowser
from pathlib import Path

import gradio as gr

from launcher_backend import load_prefs, runtime_summary_text, core_summary_text, diagnostic_text, read_full_session_log_for_recap, start_model, stop_model, refresh_state, recommendation_summary, fast_setup_text, fast_engine_status_text, online_status_text, online_test_text, save_online_config_from_ui, online_config_values, dependency_check_text, fast_engine_test_report, fast_engine_rebind_report, analyze_last_session_text, reset_settings_text, reset_live_log_text, profile_resolver_text, conflict_detector_text, gpu_cuda_text, runtime_effective_status_html, npc_cleanup_text, lite_gpu_guard_text, diagnose_repair_text, export_diagnostic_report_text
from data_processing_backend import (
    load_settings,
    save_settings,
    get_game_data,
    save_game_data,
    get_candidate_groups,
    add_items_with_feedback,
    remove_items,
    clear_candidates,
    upsert_original_name,
    remove_original_name,
    COLOR_CHOICES,
    COLOR_LABELS,
    COLOR_HEX,
    render_badge_preview,
    render_list_html,
    render_original_table,
    render_confirmed_log_html,
    get_identity_ui_payload,
    add_identity_name,
    delete_identity_choice,
    migrate_identity_choice,
    set_simple_view_enabled,
    identity_detail_categories,
    render_reference_catalog_html,
)
from gpu_runtime import gpu_summary_text, install_or_repair_gpu
from model_registry import (
    GROUP_LABELS,
    available_model_choices,
    get_model_by_title,
    group_choices,
    list_models,
)
from v7_system_profile import game_choices, profile_html, recommendation_text, recommend_settings, hardware_summary_text
from app.runtime.model_user_presets import (
    get_model_user_preset,
    save_model_user_preset,
    reset_model_user_preset,
    describe_model_user_preset,
    model_user_preset_is_modified,
    model_user_preset_badge_html,
)

PROJECT_ROOT = Path(__file__).resolve().parent
PREFS = load_prefs()
SETTINGS = load_settings()


def render_observed_review_html(game: str) -> str:
    """Render v8.8.5 observed speaker/term/alias review without auto-activating aliases."""
    if str(game or "").upper() != "GFL2_EXILIUM":
        return "<div class='smallnote'>Observed Story / Alias Review saat ini tersedia untuk profile GFL2 setelah audit v8.7.6 dan live CT2.</div>"
    path = PROJECT_ROOT / "configs" / "gfl2_observed_candidates_v8_7_8.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "<div class='smallnote'>Ledger observasi belum tersedia.</div>"
    official = data.get("observed_recent_story_v8_7_7", data.get("observed_official_priority", []))
    aliases = data.get("roi_only_alias_candidates", data.get("reviewed_alias_candidates", []))
    additions = data.get("approved_exact_additions_v8_7_9", data.get("approved_exact_additions", []))
    special_terms = data.get("special_terms_additions", data.get("ct2_live_special_terms", []))
    excluded = [{"display_name": x} if isinstance(x,str) else x for x in data.get("commander_profile_only_excluded_global", [])]
    official_chips = " ".join(f"<span style='display:inline-block;background:#14532d;color:#dcfce7;padding:4px 8px;border-radius:12px;margin:3px'>{html.escape(str(row.get('display_name','')))} · {int(row.get('prefix_hits', row.get('selected_events', 0)))}</span>" for row in official[:15])
    add_chips = " ".join(f"<span style='display:inline-block;background:#1d4ed8;color:#eff6ff;padding:4px 8px;border-radius:12px;margin:3px'>{html.escape(str(row.get('display_name','')))} · exact-only</span>" for row in additions)
    term_chips = " ".join(f"<span style='display:inline-block;background:#6d28d9;color:#f5f3ff;padding:4px 8px;border-radius:12px;margin:3px'>{html.escape(str(term))}</span>" for term in special_terms)
    excluded_text = ", ".join(html.escape(str(row.get('display_name',''))) for row in excluded)
    alias_rows = "".join(f"<tr><td>{html.escape(str(row.get('ocr_form','')))}</td><td>→ {html.escape(str(row.get('canonical', row.get('canonical_name',''))))}</td><td>{int(row.get('hits',0))}</td><td>{html.escape(str(row.get('status','ROI-only review')))}</td></tr>" for row in aliases[:16])
    return (
        "<div class='card'><b>Observed Recent Story — official exact speaker</b><p class='smallnote'>Nama hijau sudah berada pada katalog resmi; angka menunjukkan bukti selected audit terbaru.</p>" + official_chips +
        "<hr><b>v8.8.5 Safe Additions — exact-only setelah migrasi</b><p class='smallnote'>Nama biru berasal dari log CT2 terbaru dan tidak memakai fuzzy body matching.</p>" + add_chips +
        "<hr><b>Special Terms GFL2 v8.8.5 baru/retained</b><div>" + term_chips + "</div>" +
        "<hr><b>Alias Candidate (ROI-only, belum aktif otomatis)</b><table style='width:100%;margin-top:6px'><tr><th>OCR</th><th>Canonical</th><th>Hits</th><th>Status</th></tr>" + alias_rows +
        "</table><p class='smallnote'>Tidak auto-map Helene. Commander profile-only yang tidak dimasukkan global: " + excluded_text + ".</p></div>"
    )

CSS = """
.gradio-container {
  background: radial-gradient(circle at top, #0b1530 0%, #07101f 50%, #03060c 100%);
}
.hero {
  border: 1px solid rgba(96,165,250,.25);
  background: linear-gradient(145deg, rgba(10,20,46,.95), rgba(8,16,31,.88));
  border-radius: 24px;
  padding: 22px 24px;
  box-shadow: 0 18px 60px rgba(0,0,0,.35);
}
.hero h1 { margin: 0; font-size: 34px; }
.hero p { margin: 8px 0 0; color: #dbeafe; }
.card {
  border: 1px solid rgba(56,189,248,.18);
  border-radius: 18px;
  padding: 14px;
  background: rgba(15,23,42,.72);
}
.mono textarea, .logbox textarea, .jsonbox textarea {
  font-family: Consolas, monospace !important;
}
#exit_btn button {
  background: #991b1b !important;
  color: white !important;
  border: 1px solid rgba(255,255,255,.08) !important;
}
#reset_model_default_btn button {
  background: #dc2626 !important;
  color: white !important;
  border-radius: 999px !important;
  border: 1px solid rgba(255,255,255,.12) !important;
  padding: 9px 16px !important;
  font-weight: 800 !important;
}
.model-default-panel {
  margin-top: -4px;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 14px;
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(15,23,42,.48);
}
.model-default-panel small { display:block; color:#94a3b8; margin-top:4px; }
.model-modification-badge { color:#fb923c; font-weight:900; letter-spacing:.2px; }
.model-default-badge { color:#94a3b8; font-weight:800; }
#gpu_repair_btn button {
  background: #f97316 !important;
  color: white !important;
  border: 1px solid rgba(255,255,255,.08) !important;
}
#gpu_repair_btn button:active, #gpu_repair_btn button[aria-pressed='true'] {
  background: #6b7280 !important;
}
.status-pill { display:inline-block; padding:10px 14px; border-radius:12px; font-weight:700; }
.status-idle { background:#1f2937; color:white; }
.status-running { background:#166534; color:white; }
.status-stop { background:#b45309; color:white; }
.status-error { background:#991b1b; color:white; }
.notice {
  border: 1px solid rgba(234,179,8,.35);
  background: rgba(120,53,15,.2);
  color: #fde68a;
  border-radius: 16px;
  padding: 12px 14px;
}
.smallnote { color:#cbd5e1; font-size:13px; }
.color-legend { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
.color-chip { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; border:1px solid rgba(255,255,255,.08); background:rgba(15,23,42,.55); }
.color-dot { width:14px; height:14px; border-radius:999px; display:inline-block; }
.copylog-wrap button { background:#0f766e; color:white; border:none; border-radius:10px; padding:10px 14px; cursor:pointer; font-weight:700; margin-right:8px; }
.copylog-wrap span { margin-left:10px; color:#a7f3d0; font-size:13px; }
.ai-link, .ai-copy-btn {
  display:inline-flex; align-items:center; justify-content:center;
  padding:10px 14px; border-radius:12px; text-decoration:none; color:white;
  border:1px solid rgba(255,255,255,.08); font-weight:700; cursor:pointer; margin-right:8px;
}
.ai-chatgpt { background:#0f172a; }
.ai-gemini { background:#111827; }
.ai-copy-btn { background:#0f766e; }

/* v8.1 UI refresh */
.gradio-container { font-family: Inter, Segoe UI, system-ui, sans-serif; }
.hero { position: relative; overflow: hidden; }
.hero:after { content:""; position:absolute; inset:-80px -20px auto auto; width:220px; height:220px; background: radial-gradient(circle, rgba(56,189,248,.22), transparent 62%); pointer-events:none; }
.compact-card, .gr-accordion { border-radius: 18px !important; border:1px solid rgba(148,163,184,.16) !important; background:rgba(15,23,42,.55) !important; }
.dashboard-tip { border:1px solid rgba(34,197,94,.28); background:rgba(20,83,45,.18); color:#bbf7d0; border-radius:16px; padding:12px 14px; margin:10px 0; }
.pro-hint { color:#93c5fd; font-size:12px; margin-top:-4px; margin-bottom:8px; }
.clean-section { padding: 8px 0 2px; }


.status-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin:10px 0 14px; }
.status-card { border:1px solid rgba(148,163,184,.18); background:rgba(15,23,42,.72); border-radius:16px; padding:12px; min-height:78px; }
.status-card b { display:block; color:#bfdbfe; font-size:12px; margin-bottom:6px; }
.status-card span { display:block; color:white; font-weight:700; word-break:break-word; }
.status-card small { display:block; color:#94a3b8; margin-top:6px; font-size:11px; }
.mode-guide { border:1px solid rgba(56,189,248,.22); background:rgba(8,47,73,.22); border-radius:16px; padding:12px 14px; color:#dbeafe; }

"""

USER_NOTE = """**Catatan v8.7**

- Fokus update: profil khusus **GFL**, mask footer `GFsystem`/ikon kanan bawah, pemisahan Name/Body ROI, Scene Guard, serta normalized cache sebelum terjemahan.
- Untuk Girls' Frontline seri pertama, pilih game **GFL** agar footer UI tidak mencemari OCR/cache/NPC learning. **Freeze**, **Interval**, dan **Auto** tetap mempertahankan semantik lama.
- Jika Fast CT2 belum aktif, WebUI memberi warning karena model Fast akan fallback ke Argos dan belum valid untuk perbandingan performa Fast/Lite.
- Runtime cards dan Analyze Last Session menampilkan artifact GFL, frame non-dialog yang ditahan, cache, serta requested vs applied engine.
"""

GAME_CHOICES = game_choices()


def _status_html(status_text: str) -> str:
    t = (status_text or "STATUS: IDLE").upper()
    cls = "status-idle"
    if "RUNNING" in t:
        cls = "status-running"
    elif "STOP" in t:
        cls = "status-stop"
    elif "ERROR" in t:
        cls = "status-error"
    safe = html.escape(status_text or "STATUS: IDLE")
    return f"<div class='status-pill {cls}'>{safe}</div>"


def _model_desc(name: str) -> str:
    if not name:
        return "Deskripsi model belum tersedia."
    try:
        m = get_model_by_title(name)
        custom = describe_model_user_preset(m.title)
        return (
            f"**{m.title}** — {m.summary}\n\n{m.details}\n\n"
            f"Default bawaan: `{m.default_mode}` / `{m.default_engine}` / `{m.default_interval_ms} ms` / OCR `{m.ocr_resolution_percent}%`.\n\n"
            f"**Default kustom:** {custom}"
        )
    except Exception:
        return f"{name} siap dipakai. Deskripsi rinci belum ditulis."

def _render_catalog(group_key: str) -> str:
    items = list_models(group_key)
    chunks = []
    for item in items:
        chunks.append(
            "<div class='card'>"
            f"<b>{html.escape(item.title)}</b>"
            f"<div style='margin-top:8px;color:#dbeafe'>{html.escape(item.summary)}</div>"
            f"<div style='margin-top:6px;color:#cbd5e1;font-size:13px'>{html.escape(item.details)}</div>"
            f"<div style='margin-top:8px;color:#fde68a;font-size:13px'>Default: {item.default_engine} / {item.default_mode} / {item.default_interval_ms}ms / OCR {item.ocr_resolution_percent}%</div>"
            "</div>"
        )
    return "<div style='display:grid;gap:12px'>" + "".join(chunks) + "</div>"


def _render_color_legend(name_color: str, special_color: str) -> str:
    rows = []
    for label, color in [("Daftar Nama", name_color), ("Kata Khusus", special_color), ("Blacklist", "yellow")]:
        rows.append(
            f"<div class='color-chip'><span class='color-dot' style='background:{COLOR_HEX[color]}'></span>"
            f"<span>{label} → {COLOR_LABELS.get(color, color)}</span></div>"
        )
    return "<div class='color-legend'>" + "".join(rows) + "</div>"


def _candidate_map(game: str):
    name_choices, special_choices = get_candidate_groups(game)
    return {
        "name_labels": [x[0] for x in name_choices],
        "name_map": {label: item for label, item in name_choices},
        "special_labels": [x[0] for x in special_choices],
        "special_map": {label: item for label, item in special_choices},
    }


def _proc_payload(game: str, message: str = ""):
    data = get_game_data(game)
    cmap = _candidate_map(game)
    settings = load_settings()
    return (
        message,
        gr.update(choices=cmap["name_labels"], value=[]),
        gr.update(choices=cmap["special_labels"], value=[]),
        render_confirmed_log_html(game),
        render_list_html(data["names"], data["name_color"], "Belum ada daftar nama tersimpan."),
        render_list_html(data["special_words"], data["special_color"], "Belum ada daftar kata khusus tersimpan."),
        render_list_html(data["blacklist"], "yellow", "Belum ada blacklist kata."),
        render_original_table(game),
        data["name_color"],
        data["special_color"],
        settings.get("popup_on_stop", True),
        settings.get("auto_reset_candidates", False),
        render_badge_preview(game),
        _render_color_legend(data["name_color"], data["special_color"]),
        gr.update(choices=data["names"], value=[]),
        gr.update(choices=data["special_words"], value=[]),
        gr.update(choices=data["blacklist"], value=[]),
    )


def _on_group_change(group_key: str):
    choices = available_model_choices(group_key)
    value = choices[0] if choices else None
    _save_ui_pref(model_group=group_key, model=value)
    return (
        gr.update(choices=choices, value=value),
        _model_desc(value),
        _render_catalog(group_key),
        model_user_preset_badge_html(value),
        gr.update(visible=model_user_preset_is_modified(value)),
    )


def _on_model_change(name: str):
    try:
        m = get_model_by_title(name)
        return _model_desc(name), m.default_mode, m.default_engine, m.default_interval_ms, m.ocr_resolution_percent
    except Exception:
        return _model_desc(name), gr.update(), gr.update(), gr.update(), gr.update()


def _settings_mode_is_manual(settings_mode: str) -> bool:
    return str(settings_mode or "recommended").lower() in {"manual", "normal", "normal / manual"}


def _save_ui_pref(**updates):
    try:
        path = PROJECT_ROOT / "webui_prefs.json"
        data = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                data = {}
        data.update(updates)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ui_mode_visibility(mode: str):
    mode = str(mode or "recommended").lower()
    return {
        "recommendation": mode in {"recommended", "expert"},
        "diagnostic": mode == "expert",
        "model_controls": mode in {"recommended", "expert"},
        "runtime_summary": mode != "basic",
        "hardware": mode in {"recommended", "expert"},
        "policy": mode == "expert",
    }


def _ui_mode_updates(mode: str):
    _save_ui_pref(ui_mode=str(mode or "recommended"))
    v = _ui_mode_visibility(mode)
    return (
        gr.update(visible=v["recommendation"]),
        gr.update(visible=v["diagnostic"]),
        gr.update(visible=v["model_controls"]),
        gr.update(visible=v["runtime_summary"]),
        gr.update(visible=v["hardware"]),
        gr.update(visible=v["policy"]),
    )


def _apply_recommendation(game: str, settings_mode: str = "recommended"):
    manual = _settings_mode_is_manual(settings_mode)
    if manual:
        # v8.1: Manual mode must not overwrite model/engine/interval/OCR choices.
        return (
            profile_html(game, True),
            recommendation_text(game, True),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            "manual",
        )
    return _force_apply_recommendation(game)


def _force_apply_recommendation(game: str):
    rec = recommend_settings(game, allow_normal=False)
    group = rec.get("recommended_model_group", "normal")
    choices = available_model_choices(group)
    model = rec.get("recommended_model")
    if model not in choices:
        model = choices[0] if choices else None
    _save_ui_pref(settings_mode="recommended", model_group=group, model=model, game=game, mode=rec.get("recommended_mode", "auto"), engine=rec.get("recommended_engine", "hybrid"), interval_ms=max(90, int(rec.get("recommended_interval_ms", 220))), ocr_resolution=int(rec.get("recommended_ocr_resolution", 65)))
    return (
        profile_html(game, False),
        recommendation_text(game, False),
        gr.update(value=group),
        gr.update(choices=choices, value=model),
        _model_desc(model),
        rec.get("recommended_mode", "auto"),
        rec.get("recommended_engine", "hybrid"),
        max(90, int(rec.get("recommended_interval_ms", 220))),
        int(rec.get("recommended_ocr_resolution", 65)),
        "recommended",
    )

def _builtin_model_values(name: str, game: str = ""):
    m = get_model_by_title(name)
    heavy = str(game or "").upper() in {"WUWA", "WUTHERING_WAVES"}
    is_lite = "lite" in (m.tier or "").lower()
    engine = "cpu" if (heavy and is_lite) else (m.default_engine or "hybrid")
    return {
        "mode": str(m.default_mode or "auto").lower(),
        "engine": str(engine or "hybrid").lower(),
        "interval_ms": max(90, int(m.default_interval_ms or 90)),
        "ocr_resolution": int(m.ocr_resolution_percent or 65),
    }


def _settings_match_builtin(name: str, game: str, mode: str, engine: str, interval_ms: int, ocr_resolution: int) -> bool:
    try:
        base = _builtin_model_values(name, game)
        return (
            str(mode or "").lower() == base["mode"]
            and str(engine or "").lower() == base["engine"]
            and int(interval_ms) == int(base["interval_ms"])
            and int(ocr_resolution) == int(base["ocr_resolution"])
        )
    except Exception:
        return False


def _manual_model_defaults(name: str, game: str):
    try:
        m = get_model_by_title(name)
        base = _builtin_model_values(name, game)
        preset = get_model_user_preset(m.title)
        mode_v = str(preset.get("mode") or base["mode"])
        engine_v = str(preset.get("engine") or base["engine"])
        interval_v = max(90, int(preset.get("interval_ms") or base["interval_ms"]))
        ocr_v = int(preset.get("ocr_resolution") or base["ocr_resolution"])
        _save_ui_pref(model=name, model_group=m.tier, mode=mode_v, engine=engine_v, interval_ms=interval_v, ocr_resolution=ocr_v, settings_mode="manual")
        return (
            _model_desc(name), mode_v, engine_v, interval_v, ocr_v, "manual",
            model_user_preset_badge_html(m.title),
            gr.update(visible=model_user_preset_is_modified(m.title)),
        )
    except Exception:
        return _model_desc(name), gr.update(), gr.update(), gr.update(), gr.update(), "manual", "<div class='model-default-panel'>Gagal membaca default model.</div>", gr.update(visible=False)


def _auto_save_model_setting(name: str, game: str, mode: str, engine: str, interval_ms: int, ocr_resolution: int):
    """v8.6: automatically remember per-model modifications.

    If the user returns every value to the built-in defaults, the custom preset is removed
    and the orange Modification badge disappears.
    """
    try:
        m = get_model_by_title(name)
        if _settings_match_builtin(name, game, mode, engine, int(interval_ms), int(ocr_resolution)):
            reset_model_user_preset(m.title)
        else:
            item = save_model_user_preset(m.title, mode=mode, engine=engine, interval_ms=int(interval_ms), ocr_resolution=int(ocr_resolution))
            _save_ui_pref(model=name, model_group=m.tier, mode=item["mode"], engine=item["engine"], interval_ms=item["interval_ms"], ocr_resolution=item["ocr_resolution"], settings_mode="manual")
        return model_user_preset_badge_html(m.title), gr.update(visible=model_user_preset_is_modified(m.title)), "manual"
    except Exception as exc:
        return f"<div class='model-default-panel model-default-modified'><span class='model-modification-badge'>• Modification</span><small>Autosave gagal: {html.escape(str(exc))}</small></div>", gr.update(visible=True), "manual"


def _reset_model_default_click(name: str, game: str):
    try:
        m = get_model_by_title(name)
        reset_model_user_preset(m.title)
        base = _builtin_model_values(name, game)
        _save_ui_pref(model=name, model_group=m.tier, mode=base["mode"], engine=base["engine"], interval_ms=base["interval_ms"], ocr_resolution=base["ocr_resolution"], settings_mode="manual")
        return (
            _model_desc(name),
            model_user_preset_badge_html(m.title),
            base["mode"],
            base["engine"],
            base["interval_ms"],
            base["ocr_resolution"],
            "manual",
            gr.update(visible=False),
        )
    except Exception as exc:
        return _model_desc(name), f"<div class='model-default-panel model-default-modified'><span class='model-modification-badge'>• Modification</span><small>Gagal reset: {html.escape(str(exc))}</small></div>", gr.update(), gr.update(), gr.update(), gr.update(), "manual", gr.update(visible=True)


def _manual_mode_only(*_):
    return "manual"


def _refresh_all(game: str):
    status, log, err, notice = refresh_state()
    err_md = f"**Error terakhir:**\n\n```\n{err}\n```" if err else ""
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return _status_html(status), runtime_summary_text(), log, err_md, notice_md


def _start(model, game, mode, engine, interval_ms, ocr_resolution, settings_mode, responsive_story_mode, diagnostic_profile):
    manual = _settings_mode_is_manual(settings_mode)
    # v8.6: restore the previous safe interval floor for Interval mode.
    # 45ms remains technically possible only in custom experiments, but the normal WebUI path
    # should no longer silently make Interval more aggressive than the pre-v8.2.1 behavior.
    try:
        if str(mode or "").lower() == "interval" and int(interval_ms) < 90:
            interval_ms = 90
    except Exception:
        pass
    status, log, msg, notice = start_model(model, game, mode, engine, interval_ms, ocr_resolution, "normal" if manual else "auto", manual, settings_mode, bool(responsive_story_mode), str(diagnostic_profile or "baseline"))
    err_md = ""
    if "ERROR" in (status or ""):
        err_md = f"**Error:**\n\n```\n{msg}\n```"
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return _status_html(status), runtime_summary_text(), log, msg, err_md, notice_md


def _stop(game):
    status, log, msg, notice = stop_model()
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return (_status_html(status), runtime_summary_text(), log, msg, "", notice_md, *_proc_payload(game))


def _save_processing_settings(game, popup_on_stop, auto_reset_candidates, name_color, special_color):
    if name_color == special_color:
        return "Warna Daftar Nama dan Kata Khusus tidak boleh sama.", render_badge_preview(game), _render_color_legend(name_color, special_color)
    save_settings({"popup_on_stop": bool(popup_on_stop), "auto_reset_candidates": bool(auto_reset_candidates)})
    data = get_game_data(game)
    data["name_color"] = name_color
    data["special_color"] = special_color
    save_game_data(game, data)
    return "Pengaturan Pengolahan Data disimpan.", render_badge_preview(game), _render_color_legend(data["name_color"], data["special_color"])


def _feedback_message(label: str, added, dup):
    msg = []
    if added:
        msg.append(f"{label} ditambah: " + ", ".join(added[:12]))
    if dup:
        msg.append(f"Duplikat/sudah ada: " + ", ".join(dup[:12]))
    return " | ".join(msg) if msg else "Tidak ada item baru yang valid."


def _confirm_candidates(game, name_labels, special_labels, name_color, special_color):
    if name_color == special_color:
        return _proc_payload(game, "Warna Daftar Nama dan Kata Khusus tidak boleh sama.")
    data = get_game_data(game)
    data["name_color"] = name_color
    data["special_color"] = special_color
    save_game_data(game, data)
    cmap = _candidate_map(game)
    chosen_names = [cmap["name_map"][x] for x in (name_labels or []) if x in cmap["name_map"]]
    chosen_special = [cmap["special_map"][x] for x in (special_labels or []) if x in cmap["special_map"]]
    added_n, dup_n = add_items_with_feedback(game, "names", chosen_names)
    added_s, dup_s = add_items_with_feedback(game, "special_words", chosen_special)
    clear_candidates(game)
    msg = "Konfirmasi selesai. " + " ".join([
        _feedback_message("Nama", added_n, dup_n),
        _feedback_message("Kata khusus", added_s, dup_s),
    ])
    return _proc_payload(game, msg)


def _skip_candidates(game):
    clear_candidates(game)
    return _proc_payload(game, "Kandidat baru di-skip untuk sesi ini.")


def _reset_candidates(game):
    clear_candidates(game)
    return _proc_payload(game, "Daftar kandidat sesi ini dibersihkan.")


def _add_name(game, text):
    items = [x.strip() for x in str(text or "").split(",") if x.strip()]
    added, dup = add_items_with_feedback(game, "names", items)
    return (_feedback_message("Nama", added, dup), "", *_proc_payload(game)[1:])


def _add_special(game, text):
    items = [x.strip() for x in str(text or "").split(",") if x.strip()]
    added, dup = add_items_with_feedback(game, "special_words", items)
    return (_feedback_message("Kata khusus", added, dup), "", *_proc_payload(game)[1:])


def _add_blacklist(game, text):
    items = [x.strip() for x in str(text or "").split(",") if x.strip()]
    added, dup = add_items_with_feedback(game, "blacklist", items)
    return (_feedback_message("Blacklist", added, dup), "", *_proc_payload(game)[1:])


def _remove_name(game, items):
    remove_items(game, "names", items)
    return _proc_payload(game, "Item nama dihapus.")


def _remove_special(game, items):
    remove_items(game, "special_words", items)
    return _proc_payload(game, "Item kata khusus dihapus.")


def _remove_blacklist(game, items):
    remove_items(game, "blacklist", items)
    return _proc_payload(game, "Item blacklist dihapus.")


def _upsert_original(game, current_name, original_name):
    try:
        upsert_original_name(game, current_name, original_name)
        payload = _proc_payload(game, "Original Name diperbarui.")
        return (payload[0], "", "", *payload[1:])
    except Exception as e:
        payload = _proc_payload(game, f"Gagal menyimpan Original Name: {e}")
        return (payload[0], current_name, original_name, *payload[1:])


def _remove_original(game, current_name):
    remove_original_name(game, current_name)
    payload = _proc_payload(game, "Original Name dihapus.")
    return (payload[0], "", *payload[1:])


def _identity_payload_ui(game, simple_view):
    header, names, terms, blacklist, choices, notice = get_identity_ui_payload(game, bool(simple_view))
    cats = identity_detail_categories(game)
    cat_update = gr.update(choices=[(label, key) for key, label in cats], value=cats[0][0] if cats else 'protected_character')
    return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices, value=None), notice, gr.update(visible=bool(simple_view)), gr.update(visible=not bool(simple_view)), cat_update


def _identity_toggle(game, simple_view):
    set_simple_view_enabled(bool(simple_view))
    return _identity_payload_ui(game, simple_view)


def _identity_add(game, simple_view, name, category, faction):
    try:
        header, names, terms, blacklist, choices, notice = add_identity_name(game, name, bool(simple_view), category, faction)
        msg = f"Nama '{name.strip()}' ditambahkan. " + ("Nama akan tampil orange di Mode Normal sampai dimigrasikan." if simple_view else "Nama tersimpan pada kategori detail.")
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices, value=None), notice, "", msg
    except Exception as exc:
        header, names, terms, blacklist, choices, notice = get_identity_ui_payload(game, bool(simple_view))
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices), notice, name, f"Gagal menambah nama: {exc}"


def _identity_delete(game, simple_view, selected):
    try:
        header, names, terms, blacklist, choices, notice = delete_identity_choice(game, selected, bool(simple_view))
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices, value=None), notice, "Nama terpilih dihapus."
    except Exception as exc:
        header, names, terms, blacklist, choices, notice = get_identity_ui_payload(game, bool(simple_view))
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices), notice, f"Gagal menghapus: {exc}"


def _identity_migrate(game, selected, category, faction):
    try:
        header, names, terms, blacklist, choices, notice = migrate_identity_choice(game, selected, category, faction)
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices, value=None), notice, "Nama orange berhasil dimigrasikan ke kategori detail."
    except Exception as exc:
        header, names, terms, blacklist, choices, notice = get_identity_ui_payload(game, False)
        return header, names, terms, blacklist, names, terms, blacklist, gr.update(choices=choices), notice, f"Migrasi tidak dilakukan: {exc}"


def _build_story_prompt(log_text: str, game: str = "GFL2_EXILIUM"):
    txt = (log_text or "").strip()
    if not txt:
        return "Belum ada live log untuk diringkas."
    return f"""Ubah live log berikut menjadi ringkasan cerita yang rapi untuk game {game}.

Aturan:
- Fokus pada kejadian, dialog, nama karakter, istilah penting, dan konteks adegan.
- Rapikan typo OCR seperlunya tanpa mengubah makna.
- Abaikan baris teknis seperti CACHE, HIT, MISS, PIPE, OCR, VRAM, BOOT, dan WEBUI kecuali penting untuk konteks cerita.
- Jika ada nama karakter yang terlihat salah OCR, tebak secara hati-hati dan jelaskan bila tidak yakin.
- Tulis dalam bahasa Indonesia yang natural, enak dibaca, dan tidak terlalu kaku.
- Hasil akhir berbentuk ringkasan adegan/story, lalu tambahkan daftar poin penting di akhir.

LIVE LOG:
{txt}
"""


def _build_prompt_box(log_text: str, game: str):
    # v7.9: use full session log from disk when available; the UI textbox may show only a safe tail.
    full_log = read_full_session_log_for_recap(log_text)
    return _build_story_prompt(full_log, game)


initial_group = PREFS.get("model_group", "normal")
if initial_group not in GROUP_LABELS:
    initial_group = "normal"
basic_choices = available_model_choices(initial_group)
default_model = PREFS.get("model", basic_choices[0] if basic_choices else None)
if default_model not in basic_choices:
    default_model = basic_choices[0] if basic_choices else None
_initial_model_preset = get_model_user_preset(default_model) if default_model else {}
init_proc = _proc_payload(PREFS.get("game", "GFL2_EXILIUM"))
seed_data = get_game_data(PREFS.get("game", "GFL2_EXILIUM"))
INITIAL_UI_MODE = PREFS.get("ui_mode", "recommended")
_INITIAL_VIS = _ui_mode_visibility(INITIAL_UI_MODE)

with gr.Blocks(title="ORT Translation v8.8.5") as demo:
    gr.HTML("<div class='hero'><h1>ORT Translation v8.8.5</h1><p>GFL2 Recording Stability, Overlay Commit Gate, CT2 Path Resolver, Render Signature, dan Recording Telemetry.</p></div>")
    with gr.Row():
        with gr.Column(scale=11):
            candidate_notice = gr.HTML("")
        with gr.Column(scale=1, elem_id="exit_btn"):
            exit_btn = gr.Button("Exit", variant="stop")

    with gr.Tabs():
        with gr.Tab("Dashboard"):
            with gr.Row():
                with gr.Column(scale=3):
                    with gr.Row():
                        game_dropdown = gr.Dropdown(label="Nama Game", choices=GAME_CHOICES, value=PREFS.get("game", "GFL2_EXILIUM"))
                        ui_mode = gr.Radio(label="Tampilan UI", choices=[("Basic", "basic"), ("Recommended", "recommended"), ("Expert", "expert")], value=INITIAL_UI_MODE)
                    settings_mode = gr.Radio(label="Mode Pengaturan", choices=[("Rekomendasi Sistem", "recommended"), ("Normal / Manual", "manual")], value=PREFS.get("settings_mode", "recommended"))
                    gr.HTML("<div class='mode-note'><b>Rekomendasi Sistem</b> mengatur model/engine/OCR otomatis. <b>Normal / Manual</b> memberi kontrol penuh; non-Lite default Hybrid/GPU, Lite pada game berat tetap CPU/Safe.</div>")
                    game_profile_card = gr.HTML(profile_html(PREFS.get("game", "GFL2_EXILIUM"), _settings_mode_is_manual(PREFS.get("settings_mode", "recommended"))))
                    gr.HTML("<div class='dashboard-tip'>Mode bersih aktif: panel teknis disembunyikan default. Klik <b>Perluas</b> untuk melihat detail rekomendasi, diagnostic, dan status runtime.</div>")
                    with gr.Accordion("Perluas: Rekomendasi Sistem", open=False, visible=_INITIAL_VIS["recommendation"]) as recommendation_panel:
                        gr.HTML("<div class='pro-hint'>Cocok untuk mengecek alasan sistem menyarankan Safe Game, Lite, Fast, CPU/GPU, OCR resolution, dan interval.</div>")
                        recommendation_box = gr.Textbox(label="Rekomendasi sistem", value=recommendation_text(PREFS.get("game", "GFL2_EXILIUM"), _settings_mode_is_manual(PREFS.get("settings_mode", "recommended"))), interactive=False, lines=13, elem_classes=["mono"])
                        apply_rec_btn = gr.Button("Terapkan Rekomendasi Profil", variant="secondary")
                    with gr.Accordion("Perluas: Diagnostic Dashboard", open=False, visible=_INITIAL_VIS["diagnostic"]) as dashboard_diagnostic_panel:
                        gr.HTML("<div class='pro-hint'>Panel teknis untuk user pro: strategy, core bridge, runtime action, cache, online assist, Fast engine, dan session log.</div>")
                        diagnostic_box = gr.Textbox(label="Diagnostic Dashboard", value=diagnostic_text(), interactive=False, lines=18, elem_classes=["mono"])
                        refresh_diag_btn = gr.Button("Refresh Diagnostic")
                    with gr.Group(visible=_INITIAL_VIS["model_controls"]) as model_controls_panel:
                        with gr.Row():
                            model_group = gr.Radio(label="Grup model", choices=group_choices(), value=initial_group)
                            model_dropdown = gr.Dropdown(label="Pilih model", choices=basic_choices, value=default_model)
                        model_default_msg = gr.HTML(model_user_preset_badge_html(default_model))
                        reset_model_default_btn = gr.Button("Reset Default", elem_id="reset_model_default_btn", visible=model_user_preset_is_modified(default_model))
                        gr.HTML("<div class='smallnote'>v8.8.5: perubahan Mode / Engine / Interval / OCR disimpan otomatis per model; override OCR manual tidak diturunkan diam-diam. Badge <b style='color:#fb923c'>• Modification</b> muncul jika model sudah berbeda dari default bawaan.</div>")
                        model_md = gr.Markdown(_model_desc(default_model))
                        with gr.Row():
                            mode_dropdown = gr.Dropdown(label="Mode", choices=[("Auto / Story Otomatis", "auto"), ("Freeze Manual / Klik User", "freeze"), ("Interval / Freeze Otomatis", "interval")], value=_initial_model_preset.get("mode", PREFS.get("mode", "auto")))
                            responsive_story_mode = gr.Checkbox(label="Mode Responsif / Story Cepat (Tanpa Voice)", value=bool(PREFS.get("responsive_story_mode", False)))
                            gr.Markdown("Mode responsif memprioritaskan dialog terbaru dan mengurangi preview usang. Two-Pass Name ROI tetap aktif; v8.8.5 dapat menaikkan OCR sementara bila teks preset rendah rusak.")
                            with gr.Accordion("Diagnostic A/B Test (Advanced)", open=False):
                                diagnostic_profile = gr.Dropdown(label="Profil Uji", choices=[("Baseline Correctness", "baseline"), ("Responsive Story", "responsive_story"), ("Diagnostic No-Name-ROI (uji saja)", "diagnostic_no_name_roi")], value=str(PREFS.get("diagnostic_profile", "baseline")))
                                gr.Markdown("⚠️ **Diagnostic No-Name-ROI** hanya untuk pengukuran performa; label KSVK/Helen/Helena dapat hilang atau salah.")
                            engine_dropdown = gr.Dropdown(label="Engine OCR / Terjemahan", choices=[("CPU", "cpu"), ("GPU", "gpu"), ("Hybrid", "hybrid")], value=_initial_model_preset.get("engine", PREFS.get("engine", "hybrid")))
                        with gr.Row():
                            interval_slider = gr.Slider(label="Interval / capture ms", minimum=45, maximum=1200, step=5, value=max(45, int(_initial_model_preset.get("interval_ms", PREFS.get("interval_ms", 160)))))
                            ocr_resolution_slider = gr.Slider(label="OCR Resolution %", minimum=5, maximum=100, step=5, value=int(_initial_model_preset.get("ocr_resolution", PREFS.get("ocr_resolution", 65))))
                        gr.HTML("<div class='mode-guide'><b>Panduan Mode v8.7:</b><br>Freeze = manual story click, langsung commit. Interval = Freeze otomatis klasik dengan commit cepat setiap snapshot baru. Auto = story otomatis ala visual novel, menerjemahkan bertahap mengikuti teks dialog yang muncul.</div>")
                    performance_policy_info = gr.Markdown("**Kebijakan performa v8.7:** Fast CT2 tetap dipakai jika aktif. Jika CT2 gagal, OCR ultra-rendah tidak direkomendasikan untuk story. Mode capture tetap global. Fast V1/V2/IDN hanya memberi tuning tambahan: V1 speed-first, V2 balanced, Fast IDN naturalisasi Indonesia. Status card menunjukkan requested vs effective dan alasan performa.", visible=_INITIAL_VIS["policy"])
                    with gr.Row():
                        start_btn = gr.Button("Start", variant="primary")
                        refresh_btn = gr.Button("Refresh")
                        stop_btn = gr.Button("Stop", variant="stop")
                    launch_msg = gr.Textbox(label="Status launcher", interactive=False)
                with gr.Column(scale=2):
                    runtime_status_cards = gr.HTML(runtime_effective_status_html())
                    state_box = gr.HTML(_status_html("STATUS: IDLE"))
                    with gr.Accordion("Perluas: Runtime Ringkas", open=False, visible=_INITIAL_VIS["runtime_summary"]) as runtime_summary_panel:
                        runtime_box = gr.Textbox(label="Runtime summary", value=runtime_summary_text(), interactive=False, lines=6, elem_classes=["mono"])
                    with gr.Accordion("Perluas: Deteksi Spesifikasi Laptop", open=False, visible=_INITIAL_VIS["hardware"]) as hardware_panel:
                        hardware_box = gr.Textbox(label="Deteksi spesifikasi laptop", value=hardware_summary_text(), interactive=False, lines=8, elem_classes=["mono"])
                    error_box = gr.Markdown("")

            gr.Markdown("### Live Log & AI Recap")
            with gr.Row():
                gr.HTML("""
                <div class='copylog-wrap'>
                  <button onclick="(function(){const ta=document.querySelector('#live_log textarea'); if(ta){navigator.clipboard.writeText(ta.value); const s=document.getElementById('copylog_status'); if(s){s.textContent='Live log tersalin'; setTimeout(()=>s.textContent='',1500);}}})()">Copy Live Log</button>
                  <span id='copylog_status'></span>
                </div>
                """)
                prompt_btn = gr.Button("Buat Prompt Recap")
                reset_live_log_btn = gr.Button("Reset Live Log")
                analyze_session_btn = gr.Button("Analyze Last Session")
            log_box = gr.Textbox(label="Live log", lines=18, interactive=False, autoscroll=True, elem_classes=["logbox"], elem_id="live_log")
            ai_prompt_box = gr.Textbox(label="Prompt AI Recap dari Live Log", value="", interactive=False, lines=12, elem_classes=["mono"], elem_id="ai_prompt_box")
            session_report_box = gr.Textbox(label="Analyze Last Session / Rekomendasi Performa", value="", interactive=False, lines=10, elem_classes=["mono"])
            gr.HTML("""
            <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:8px'>
              <button class='ai-copy-btn' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||''); const s=document.getElementById('aicopy_status'); if(s){s.textContent='Prompt tersalin'; setTimeout(()=>s.textContent='',1500);}}})()">Copy Prompt</button>
              <button class='ai-link ai-chatgpt' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||'');} window.open('https://chat.openai.com/','_blank');})()">Copy + Buka ChatGPT</button>
              <button class='ai-link ai-gemini' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||'');} window.open('https://gemini.google.com/','_blank');})()">Copy + Buka Gemini</button>
              <span id='aicopy_status' style='color:#a7f3d0;align-self:center'></span>
            </div>
            """)
            gr.Markdown(USER_NOTE)

        with gr.Tab("Model Browser"):
            gr.Markdown("Model v7 disederhanakan menjadi grup yang jelas. Alias model lama tetap diarahkan agar tidak memutus launcher lama.")
            catalog_html = gr.HTML(_render_catalog(initial_group))

        with gr.Tab("Pengaturan UI"):
            gr.Markdown("Tampilan box terjemahan utama dan indikator ping/ms/game/engine tetap dipertahankan. Patch v7 fokus ke profil, performa, dan alur backend.")

        with gr.Tab("Pengolahan Data"):
            gr.Markdown("## Pengolahan Data & Identitas\nKelola speaker tepercaya, istilah, alias OCR, dan blacklist berdasarkan game profile. Nama multi-kata dipertahankan sebagai satu identitas utuh.")
            _identity_initial = get_identity_ui_payload(PREFS.get("game", "GFL2_EXILIUM"), bool(SETTINGS.get("simple_view_enabled", True)))
            with gr.Row():
                identity_game = gr.Dropdown(label="Game Profile", choices=game_choices(), value=PREFS.get("game", "GFL2_EXILIUM"))
                identity_simple = gr.Checkbox(label="Tampilan Sederhana", value=bool(SETTINGS.get("simple_view_enabled", True)))
            identity_header = gr.HTML(_identity_initial[0])
            identity_notice_box = gr.Markdown(_identity_initial[5])
            with gr.Group(visible=bool(SETTINGS.get("simple_view_enabled", True))) as identity_simple_group:
                gr.Markdown("### Nama yang Dilindungi\nKarakter, Commander, dan role speaker yang disetujui berada dalam satu daftar. Nama yang ditambah di sini ditandai orange ketika dibuka pada Mode Normal.")
                identity_names_simple = gr.HTML(_identity_initial[1])
                with gr.Row():
                    identity_add_simple_txt = gr.Textbox(label="Tambah nama karakter / NPC approved / Commander")
                    identity_add_simple_btn = gr.Button("Tambah Nama", variant="primary")
                gr.Markdown("### Kata Khusus — bukan speaker")
                identity_terms_simple = gr.HTML(_identity_initial[2])
                gr.Markdown("### Blacklist / Noise")
                identity_blacklist_simple = gr.HTML(_identity_initial[3])
            with gr.Group(visible=not bool(SETTINGS.get("simple_view_enabled", True))) as identity_normal_group:
                gr.Markdown("### Mode Normal / Detail\n🟠 = ditambahkan dari Tampilan Sederhana dan belum disortir. 🟢 = sudah berada pada kategori detail. Klik item untuk mengaktifkan aksi.")
                identity_names_normal = gr.HTML(_identity_initial[1])
                gr.Markdown("### Katalog Referensi Nama — untuk proteksi ejaan/exact match, bukan auto-label speaker")
                identity_spoiler = gr.Checkbox(label="Tampilkan / Import Karakter Cerita Lanjutan (mengandung spoiler, khusus GFL)", value=bool(SETTINGS.get("show_story_spoilers", False)))
                identity_catalog_html = gr.HTML(render_reference_catalog_html(PREFS.get("game", "GFL2_EXILIUM"), bool(SETTINGS.get("show_story_spoilers", False))))
                gr.Markdown("### Observed Story / Alias Review v8.8.5")
                identity_observed_html = gr.HTML(render_observed_review_html(PREFS.get("game", "GFL2_EXILIUM")))
                identity_select = gr.Radio(label="Klik nama untuk aksi Hapus / Migrasi", choices=_identity_initial[4], value=None)
                with gr.Row():
                    identity_category = gr.Dropdown(label="Kategori tujuan migrasi", choices=[(label, key) for key, label in identity_detail_categories(PREFS.get("game", "GFL2_EXILIUM"))], value=identity_detail_categories(PREFS.get("game", "GFL2_EXILIUM"))[0][0])
                    identity_faction = gr.Textbox(label="Faksi (opsional, mis. Paradeus / Sangvis Ferri)")
                with gr.Row():
                    identity_delete_btn = gr.Button("Hapus Nama Terpilih")
                    identity_migrate_btn = gr.Button("Migrasi Nama Orange", variant="primary")
                with gr.Row():
                    identity_add_detail_txt = gr.Textbox(label="Tambah langsung ke kategori detail")
                    identity_add_detail_btn = gr.Button("Tambah ke Kategori")
                gr.Markdown("### Kata Khusus — bukan speaker")
                identity_terms_normal = gr.HTML(_identity_initial[2])
                gr.Markdown("### Blacklist / Noise")
                identity_blacklist_normal = gr.HTML(_identity_initial[3])
            identity_action_msg = gr.Markdown("")
            gr.Markdown("### Advanced / Kompatibilitas Data Lama\nKandidat, original identity, warna lama, dan cleanup tetap tersedia di bawah. Kandidat baru tidak boleh menjadi label live sebelum disetujui.")
            with gr.Tabs():
                with gr.Tab("Kandidat Baru"):
                    gr.Markdown("Sistem mencatat kandidat sementara saat OCR berjalan. Setelah Stop/ESC, Anda bisa olah kandidat ini sebelum masuk ke data tetap.")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### Kandidat untuk Daftar Nama")
                            cand_names = gr.CheckboxGroup(label="Pilih kandidat nama / panggilan / istilah nama", choices=init_proc[1]["choices"], value=[])
                        with gr.Column():
                            gr.Markdown("### Kandidat untuk Kata Khusus")
                            cand_special = gr.CheckboxGroup(label="Pilih kandidat kata khusus", choices=init_proc[2]["choices"], value=[])
                    with gr.Row():
                        confirm_btn = gr.Button("Konfirmasi Pilihan", variant="primary")
                        skip_btn = gr.Button("Skip Kandidat Sesi Ini")
                        refresh_candidates_btn = gr.Button("Refresh Kandidat")
                        reset_candidates_btn = gr.Button("Reset Kandidat")
                    proc_msg = gr.Textbox(label="Status pengolahan data", interactive=False, value=init_proc[0])
                    gr.Markdown("### Riwayat kandidat terkonfirmasi sesi ini")
                    confirmed_html = gr.HTML(init_proc[3])
                    preview_html = gr.HTML(init_proc[12], label="Preview warna label")

                with gr.Tab("Daftar Nama"):
                    names_html = gr.HTML(init_proc[4])
                    add_name_txt = gr.Textbox(label="Tambah daftar nama (pisahkan dengan koma)")
                    add_name_btn = gr.Button("Tambah ke Daftar Nama")
                    remove_name_pick = gr.CheckboxGroup(label="Pilih nama yang ingin dihapus", choices=seed_data["names"], value=[])
                    remove_name_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Daftar Kata Khusus"):
                    special_html = gr.HTML(init_proc[5])
                    add_special_txt = gr.Textbox(label="Tambah kata khusus (pisahkan dengan koma)")
                    add_special_btn = gr.Button("Tambah ke Kata Khusus")
                    remove_special_pick = gr.CheckboxGroup(label="Pilih kata khusus yang ingin dihapus", choices=seed_data["special_words"], value=[])
                    remove_special_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Original Name"):
                    original_html = gr.HTML(init_proc[7])
                    with gr.Row():
                        original_current = gr.Textbox(label="Nama sekarang")
                        original_old = gr.Textbox(label="Original Name")
                    add_original_btn = gr.Button("Tambah / Perbarui Original Name")
                    remove_original_txt = gr.Textbox(label="Nama sekarang yang ingin dihapus dari Original Name")
                    remove_original_btn = gr.Button("Hapus Original Name")

                with gr.Tab("Blacklist Kata"):
                    blacklist_html = gr.HTML(init_proc[6])
                    add_blacklist_txt = gr.Textbox(label="Tambah blacklist kata (pisahkan dengan koma)")
                    add_blacklist_btn = gr.Button("Tambah ke Blacklist")
                    remove_blacklist_pick = gr.CheckboxGroup(label="Pilih blacklist yang ingin dihapus", choices=seed_data["blacklist"], value=[])
                    remove_blacklist_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Pengaturan Pengolahan"):
                    color_legend_html = gr.HTML(init_proc[13])
                    popup_toggle = gr.Checkbox(label="Aktifkan popup / notifikasi kandidat baru setelah Stop atau ESC", value=SETTINGS.get("popup_on_stop", True))
                    auto_reset_toggle = gr.Checkbox(label="Reset kandidat otomatis saat Start sesi baru", value=SETTINGS.get("auto_reset_candidates", False))
                    with gr.Row():
                        name_color = gr.Radio(label="Warna label Daftar Nama", choices=[(COLOR_LABELS[c], c) for c in COLOR_CHOICES], value=init_proc[8])
                        special_color = gr.Radio(label="Warna label Kata Khusus", choices=[(COLOR_LABELS[c], c) for c in COLOR_CHOICES], value=init_proc[9])
                    save_proc_btn = gr.Button("Simpan Pengaturan Pengolahan Data")

        with gr.Tab("Shortcut"):
            shortcut_box = gr.Textbox(label="Shortcut config", lines=12, elem_classes=["jsonbox"], value=json.dumps({
                "esc_exit_enabled": False,
                "bindings": {
                    "pause_resume": "f1",
                    "reset_area": "f2",
                    "capture_mode": "f3",
                    "ocr_engine": "f9",
                    "interval_mode": "f11",
                }
            }, ensure_ascii=False, indent=2), interactive=False)

        with gr.Tab("Runtime & Tools"):
            gr.Markdown("Panel troubleshooting runtime, GPU, Lite GPU Efficient, Fast CT2, OCR, IDN Quality Layer, dan repair.")
            with gr.Accordion("Perluas: Runtime & GPU Doctor", open=False):
                with gr.Row():
                    runtime_tools = gr.Textbox(label="Runtime ringkas", value=runtime_summary_text(), interactive=False, lines=6, elem_classes=["mono"])
                    gpu_box = gr.Textbox(label="GPU Doctor", value=gpu_summary_text(), interactive=False, lines=12, elem_classes=["mono"])
            with gr.Accordion("Perluas: Strategy/Core Bridge Status", open=False):
                core_status_box = gr.Textbox(label="Strategy/Core Bridge Status", value=core_summary_text(), interactive=False, lines=12, elem_classes=["mono"])
            with gr.Row():
                refresh_gpu_btn = gr.Button("Refresh Runtime/GPU/Engine")
                repair_gpu_btn = gr.Button("Install / Repair GPU (Torch CUDA)", elem_id="gpu_repair_btn")
            gpu_repair_log = gr.Textbox(label="GPU Install / Repair Log", value="", interactive=False, lines=10, elem_classes=["mono"])
            gr.Markdown("### Lite GPU Efficient, Fast Engine & V4 Online Assist")
            with gr.Accordion("Perluas: Fast Engine & Online Assist Status", open=False):
                with gr.Row():
                    lite_gpu_box = gr.Textbox(label="Lite GPU Efficient Status", value=lite_gpu_guard_text(), interactive=False, lines=8, elem_classes=["mono"])
                    fast_box = gr.Textbox(label="Fast CT2 Status / Setup Wizard", value=fast_engine_status_text(), interactive=False, lines=8, elem_classes=["mono"])
                    online_box = gr.Textbox(label="V4 Online Assist Status", value=online_status_text(), interactive=False, lines=8, elem_classes=["mono"])
                with gr.Row():
                    check_lite_gpu_btn = gr.Button("Check Lite GPU Guard")
                    check_fast_btn = gr.Button("Check Fast Engine")
                    setup_fast_btn = gr.Button("Prepare Fast Engine Folder")
                    test_fast_btn = gr.Button("Test Fast Engine")
                    rebind_fast_btn = gr.Button("Repair / Rebind CT2 Model & SPM Path")
                    check_online_btn = gr.Button("Check Online Assist")
                    test_online_btn = gr.Button("Test Online Assist")
            with gr.Accordion("Perluas: Online Assist Config untuk V4 Hybrid", open=False):
                _online_enabled, _online_provider, _online_endpoint, _online_api_key, _online_timeout = online_config_values()
                with gr.Row():
                    online_enabled = gr.Checkbox(label="Enable Online Assist untuk V4", value=_online_enabled)
                    online_provider = gr.Dropdown(label="Provider", choices=["libretranslate", "deeplx", "gas", "custom"], value=_online_provider)
                    online_timeout = gr.Slider(label="Timeout detik", minimum=0.4, maximum=5.0, step=0.1, value=float(_online_timeout))
                online_endpoint = gr.Textbox(label="Endpoint URL", value=_online_endpoint, placeholder="Contoh LibreTranslate: http://127.0.0.1:5000/translate")
                online_api_key = gr.Textbox(label="API Key (opsional)", value=_online_api_key, type="password")
                with gr.Row():
                    save_online_btn = gr.Button("Save Online Assist Config")
                    dependency_btn = gr.Button("Check Runtime Dependency")
                dependency_box = gr.Textbox(label="Dependency Check", value="", interactive=False, lines=10, elem_classes=["mono"])
            with gr.Accordion("Perluas: v8 Diagnostic & Maintenance", open=False):
                with gr.Row():
                    diagnose_repair_btn = gr.Button("Diagnose & Repair Center")
                    export_diag_report_btn = gr.Button("Export Diagnostic Report")
                    analyze_btn_tools = gr.Button("Analyze Last Session")
                    gpu_cuda_btn = gr.Button("GPU / Torch CUDA Diagnostic")
                    conflict_btn = gr.Button("Conflict Detector")
                    npc_cleanup_btn = gr.Button("Clean NPC Database")
                v8_diag_box = gr.Textbox(label="v8 Diagnostic Output", value="", interactive=False, lines=14, elem_classes=["mono"])
                gr.Markdown("### Reset & Maintenance")
                with gr.Row():
                    reset_ui_btn = gr.Button("Reset UI Settings")
                    reset_runtime_btn = gr.Button("Reset Runtime Settings")
                    reset_online_btn = gr.Button("Reset Online Assist")
                    reset_all_btn = gr.Button("Reset All Settings to Default", variant="stop")
                reset_box = gr.Textbox(label="Reset Settings Log", value="", interactive=False, lines=5, elem_classes=["mono"])

    # Dashboard events
    start_btn.click(_start, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode, responsive_story_mode, diagnostic_profile], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice])
    stop_btn.click(_stop, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice, proc_msg, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    refresh_btn.click(_refresh_all, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, error_box, candidate_notice])
    apply_rec_btn.click(_force_apply_recommendation, inputs=[game_dropdown], outputs=[game_profile_card, recommendation_box, model_group, model_dropdown, model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode])
    game_dropdown.change(_apply_recommendation, inputs=[game_dropdown, settings_mode], outputs=[game_profile_card, recommendation_box, model_group, model_dropdown, model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode])
    settings_mode.change(_apply_recommendation, inputs=[game_dropdown, settings_mode], outputs=[game_profile_card, recommendation_box, model_group, model_dropdown, model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode])
    model_group.change(_on_group_change, inputs=[model_group], outputs=[model_dropdown, model_md, catalog_html, model_default_msg, reset_model_default_btn])
    model_dropdown.change(_manual_model_defaults, inputs=[model_dropdown, game_dropdown], outputs=[model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode, model_default_msg, reset_model_default_btn])
    mode_dropdown.change(_auto_save_model_setting, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider], outputs=[model_default_msg, reset_model_default_btn, settings_mode])
    engine_dropdown.change(_auto_save_model_setting, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider], outputs=[model_default_msg, reset_model_default_btn, settings_mode])
    interval_slider.change(_auto_save_model_setting, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider], outputs=[model_default_msg, reset_model_default_btn, settings_mode])
    ocr_resolution_slider.change(_auto_save_model_setting, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider], outputs=[model_default_msg, reset_model_default_btn, settings_mode])
    reset_model_default_btn.click(_reset_model_default_click, inputs=[model_dropdown, game_dropdown], outputs=[model_md, model_default_msg, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode, reset_model_default_btn])
    prompt_btn.click(_build_prompt_box, inputs=[log_box, game_dropdown], outputs=[ai_prompt_box])
    reset_live_log_btn.click(reset_live_log_text, outputs=[log_box])
    analyze_session_btn.click(analyze_last_session_text, outputs=[session_report_box])

    # v8.7.6 Multi-game identity UI events
    identity_ui_outputs = [identity_header, identity_names_simple, identity_terms_simple, identity_blacklist_simple, identity_names_normal, identity_terms_normal, identity_blacklist_normal, identity_select, identity_notice_box, identity_simple_group, identity_normal_group, identity_category]
    identity_game.change(_identity_payload_ui, inputs=[identity_game, identity_simple], outputs=identity_ui_outputs)
    identity_game.change(lambda game: game, inputs=[identity_game], outputs=[game_dropdown])
    game_dropdown.change(_identity_payload_ui, inputs=[game_dropdown, identity_simple], outputs=identity_ui_outputs)
    identity_simple.change(_identity_toggle, inputs=[identity_game, identity_simple], outputs=identity_ui_outputs)
    identity_game.change(render_reference_catalog_html, inputs=[identity_game, identity_spoiler], outputs=[identity_catalog_html])
    game_dropdown.change(render_reference_catalog_html, inputs=[game_dropdown, identity_spoiler], outputs=[identity_catalog_html])
    identity_game.change(render_observed_review_html, inputs=[identity_game], outputs=[identity_observed_html])
    game_dropdown.change(render_observed_review_html, inputs=[game_dropdown], outputs=[identity_observed_html])
    identity_spoiler.change(render_reference_catalog_html, inputs=[identity_game, identity_spoiler], outputs=[identity_catalog_html])
    identity_add_simple_btn.click(_identity_add, inputs=[identity_game, identity_simple, identity_add_simple_txt, identity_category, identity_faction], outputs=[identity_header, identity_names_simple, identity_terms_simple, identity_blacklist_simple, identity_names_normal, identity_terms_normal, identity_blacklist_normal, identity_select, identity_notice_box, identity_add_simple_txt, identity_action_msg])
    identity_add_detail_btn.click(_identity_add, inputs=[identity_game, identity_simple, identity_add_detail_txt, identity_category, identity_faction], outputs=[identity_header, identity_names_simple, identity_terms_simple, identity_blacklist_simple, identity_names_normal, identity_terms_normal, identity_blacklist_normal, identity_select, identity_notice_box, identity_add_detail_txt, identity_action_msg])
    identity_delete_btn.click(_identity_delete, inputs=[identity_game, identity_simple, identity_select], outputs=[identity_header, identity_names_simple, identity_terms_simple, identity_blacklist_simple, identity_names_normal, identity_terms_normal, identity_blacklist_normal, identity_select, identity_notice_box, identity_action_msg])
    identity_migrate_btn.click(_identity_migrate, inputs=[identity_game, identity_select, identity_category, identity_faction], outputs=[identity_header, identity_names_simple, identity_terms_simple, identity_blacklist_simple, identity_names_normal, identity_terms_normal, identity_blacklist_normal, identity_select, identity_notice_box, identity_action_msg])

    # Data processing events
    data_outputs = [proc_msg, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick]
    refresh_candidates_btn.click(_proc_payload, inputs=[game_dropdown], outputs=data_outputs)
    reset_candidates_btn.click(_reset_candidates, inputs=[game_dropdown], outputs=data_outputs)
    save_proc_btn.click(_save_processing_settings, inputs=[game_dropdown, popup_toggle, auto_reset_toggle, name_color, special_color], outputs=[proc_msg, preview_html, color_legend_html])
    confirm_btn.click(_confirm_candidates, inputs=[game_dropdown, cand_names, cand_special, name_color, special_color], outputs=data_outputs)
    skip_btn.click(_skip_candidates, inputs=[game_dropdown], outputs=data_outputs)

    add_name_btn.click(_add_name, inputs=[game_dropdown, add_name_txt], outputs=[proc_msg, add_name_txt, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    add_special_btn.click(_add_special, inputs=[game_dropdown, add_special_txt], outputs=[proc_msg, add_special_txt, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    add_blacklist_btn.click(_add_blacklist, inputs=[game_dropdown, add_blacklist_txt], outputs=[proc_msg, add_blacklist_txt, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    remove_name_btn.click(_remove_name, inputs=[game_dropdown, remove_name_pick], outputs=data_outputs)
    remove_special_btn.click(_remove_special, inputs=[game_dropdown, remove_special_pick], outputs=data_outputs)
    remove_blacklist_btn.click(_remove_blacklist, inputs=[game_dropdown, remove_blacklist_pick], outputs=data_outputs)

    add_original_btn.click(_upsert_original, inputs=[game_dropdown, original_current, original_old], outputs=[proc_msg, original_current, original_old, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    remove_original_btn.click(_remove_original, inputs=[game_dropdown, remove_original_txt], outputs=[proc_msg, remove_original_txt, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    refresh_diag_btn.click(diagnostic_text, outputs=[diagnostic_box])
    refresh_gpu_btn.click(lambda: (runtime_summary_text(), gpu_summary_text(), core_summary_text(), lite_gpu_guard_text(), fast_engine_status_text(), online_status_text()), outputs=[runtime_tools, gpu_box, core_status_box, lite_gpu_box, fast_box, online_box])
    repair_gpu_btn.click(lambda: (runtime_summary_text(), gpu_summary_text(), install_or_repair_gpu()), outputs=[runtime_tools, gpu_box, gpu_repair_log])
    check_lite_gpu_btn.click(lite_gpu_guard_text, outputs=[lite_gpu_box])
    check_fast_btn.click(fast_engine_status_text, outputs=[fast_box])
    setup_fast_btn.click(fast_setup_text, outputs=[fast_box])
    test_fast_btn.click(fast_engine_test_report, outputs=[fast_box])
    rebind_fast_btn.click(fast_engine_rebind_report, outputs=[fast_box])
    check_online_btn.click(online_status_text, outputs=[online_box])
    test_online_btn.click(online_test_text, outputs=[online_box])
    save_online_btn.click(save_online_config_from_ui, inputs=[online_enabled, online_provider, online_endpoint, online_api_key, online_timeout], outputs=[online_box])
    dependency_btn.click(dependency_check_text, outputs=[dependency_box])
    diagnose_repair_btn.click(diagnose_repair_text, outputs=[v8_diag_box])
    export_diag_report_btn.click(export_diagnostic_report_text, outputs=[v8_diag_box])
    analyze_btn_tools.click(analyze_last_session_text, outputs=[v8_diag_box])
    gpu_cuda_btn.click(gpu_cuda_text, outputs=[v8_diag_box])
    conflict_btn.click(conflict_detector_text, outputs=[v8_diag_box])
    reset_ui_btn.click(lambda: reset_settings_text("ui"), outputs=[reset_box])
    reset_runtime_btn.click(lambda: reset_settings_text("runtime"), outputs=[reset_box])
    reset_online_btn.click(lambda: reset_settings_text("online"), outputs=[reset_box])
    reset_all_btn.click(lambda: reset_settings_text("all"), outputs=[reset_box])
    npc_cleanup_btn.click(npc_cleanup_text, outputs=[v8_diag_box])
    ui_mode.change(_ui_mode_updates, inputs=[ui_mode], outputs=[recommendation_panel, dashboard_diagnostic_panel, model_controls_panel, runtime_summary_panel, hardware_panel, performance_policy_info])

    timer = gr.Timer(1.0)
    timer.tick(_refresh_all, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, error_box, candidate_notice])
    timer.tick(runtime_effective_status_html, outputs=[runtime_status_cards])

    def _exit_app():
        try:
            stop_model()
        except Exception:
            pass
        def _delayed_exit():
            time.sleep(0.8)
            os._exit(0)
        threading.Thread(target=_delayed_exit, daemon=True).start()
        return "ORT WebUI sedang ditutup secara aman..."

    exit_btn.click(_exit_app, outputs=[launch_msg])

if __name__ == "__main__":
    def _open_browser():
        time.sleep(2.0)
        webbrowser.open("http://127.0.0.1:7860")

    threading.Thread(target=_open_browser, daemon=True).start()
    demo.queue().launch(server_name="127.0.0.1", server_port=7860, inbrowser=False, css=CSS)
