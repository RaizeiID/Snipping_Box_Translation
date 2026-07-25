from __future__ import annotations

import html
import json
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import gradio as gr

from launcher_backend import load_prefs, runtime_summary_text, core_summary_text, diagnostic_text, read_full_session_log_for_recap, start_model, start_audio_model, stop_model, refresh_state, recommendation_summary, fast_setup_text, fast_engine_status_text, online_status_text, online_test_text, save_online_config_from_ui, online_config_values, dependency_check_text, fast_engine_test_report, fast_engine_rebind_report, analyze_last_session_text, reset_settings_text, reset_live_log_text, profile_resolver_text, conflict_detector_text, gpu_cuda_text, runtime_effective_status_html, npc_cleanup_text, lite_gpu_guard_text, diagnose_repair_text, export_diagnostic_report_text, setup_audio_runtime_text, audio_runtime_status_text, audio_devices_for_ui, audio_runtime_probe, setup_audio_cloud_runtime_text, audio_cloud_runtime_status_text, audio_cloud_config_values, save_audio_cloud_config_from_ui, clear_audio_cloud_credentials_text, prepare_source_switch_stop, finish_source_switch_stop
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
from build_info import APP_DISPLAY_NAME, APP_VERSION_TAG, RELEASE_NAME
from app.open_architecture import (
    architecture_apply_preset,
    architecture_compare_presets,
    architecture_export_plan,
    architecture_initial_payload,
    architecture_provider_choices,
    architecture_preset_choices,
    architecture_refresh,
    architecture_save_custom,
    architecture_runtime_validation_text,
    architecture_start_audio,
    confirmed_prefix_demo,
)
from app.open_architecture.overlay_preview import (
    start_overlay_preview,
    stop_overlay_preview,
    toggle_overlay_preview,
    update_overlay_preview,
)
from app.audio.asr_provider_registry import (
    PROVIDERS as ASR_PROVIDERS,
    PROVIDER_KOTOBA,
    PROVIDER_REAZON,
    PROVIDER_SENSEVOICE,
    normalize_provider_id as normalize_asr_model_provider,
    provider_choices as asr_model_provider_choices,
    provider_status as asr_model_provider_status,
)
from app.audio.provider_benchmark import benchmark_many, results_markdown

PROJECT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
AUDIO_RUNTIME_ROOT = REPOSITORY_ROOT / "ORT_Runtime"
AUDIO_MODEL_ROOT = AUDIO_RUNTIME_ROOT / "audio_cpu" / "models"
AUDIO_CPU_PYTHON = AUDIO_RUNTIME_ROOT / "audio_cpu" / ".venv" / "Scripts" / "python.exe"
AUDIO_GPU_PYTHON = AUDIO_RUNTIME_ROOT / "audio_gpu" / ".venv" / "Scripts" / "python.exe"
AUDIO_PROVIDER_SETUP = PROJECT_ROOT / "tools" / "setup_v9_0_4_audio_providers.py"
AUDIO_PROVIDER_SIDECAR = PROJECT_ROOT / "audio_realtime_local_sidecar.py"
PREFS = load_prefs()
SETTINGS = load_settings()


def render_observed_review_html(game: str) -> str:
    """Render observed speaker/term/alias review without auto-activating aliases."""
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
        "<hr><b>Safe Additions — dipertahankan dari data v8.9.1</b><p class='smallnote'>Nama biru berasal dari log CT2 terbaru dan tidak memakai fuzzy body matching.</p>" + add_chips +
        "<hr><b>Special Terms GFL2 — data v8.9.1 dipertahankan</b><div>" + term_chips + "</div>" +
        "<hr><b>Alias Candidate (ROI-only, belum aktif otomatis)</b><table style='width:100%;margin-top:6px'><tr><th>OCR</th><th>Canonical</th><th>Hits</th><th>Status</th></tr>" + alias_rows +
        "</table><p class='smallnote'>Tidak auto-map Helene. Commander profile-only yang tidak dimasukkan global: " + excluded_text + ".</p></div>"
    )

CSS = """
.oa-lab-banner { border:1px solid rgba(52,211,153,.28); background:linear-gradient(135deg,rgba(6,78,59,.35),rgba(15,23,42,.82)); border-radius:20px; padding:18px; margin-bottom:12px; }
.oa-lab-banner h2 { margin:0 0 6px; }
.oa-lab-banner p { color:#d1fae5; margin:0; line-height:1.5; }
.oa-diagram { display:flex; flex-direction:column; gap:7px; align-items:stretch; padding:10px 0; }
.oa-node { border-radius:15px; padding:11px 14px; border:1px solid rgba(148,163,184,.22); background:rgba(15,23,42,.72); }
.oa-node span { display:block; color:#93c5fd; font-size:10px; font-weight:900; letter-spacing:.9px; }
.oa-node b { display:block; margin-top:3px; }
.oa-node small { display:block; margin-top:4px; color:#cbd5e1; }
.oa-ready { border-color:rgba(52,211,153,.35); }
.oa-warn { border-color:rgba(251,191,36,.36); }
.oa-arrow { text-align:center; color:#60a5fa; font-size:20px; font-weight:900; line-height:1; }
.oa-safety { border:1px solid rgba(96,165,250,.25); background:rgba(30,64,175,.16); color:#dbeafe; border-radius:14px; padding:11px 13px; }
.oa-table-wrap { overflow:auto; border-radius:16px; border:1px solid rgba(148,163,184,.16); }
.oa-table { width:100%; border-collapse:collapse; min-width:760px; }
.oa-table th,.oa-table td { padding:10px 12px; border-bottom:1px solid rgba(148,163,184,.13); text-align:left; vertical-align:top; }
.oa-table th { color:#bfdbfe; background:rgba(15,23,42,.86); }
.oa-table td small { color:#94a3b8; }
.oa-badge-ready,.oa-badge-warn { display:inline-flex; border-radius:999px; padding:3px 8px; font-size:11px; font-weight:900; }
.oa-badge-ready { color:#a7f3d0; background:rgba(6,95,70,.35); }
.oa-badge-warn { color:#fde68a; background:rgba(120,53,15,.35); }

.provider-status-panel { border:1px solid rgba(96,165,250,.24); background:rgba(8,17,32,.82); border-radius:18px; padding:15px; margin:8px 0 12px; }
.provider-status-head { display:flex; justify-content:space-between; gap:12px; align-items:center; }
.provider-status-head small { color:#60a5fa; font-weight:900; letter-spacing:.9px; }
.provider-status-head h3 { margin:3px 0 0; }
.provider-lock-pill { display:inline-flex; border-radius:999px; padding:7px 13px; background:rgba(30,64,175,.42); color:#dbeafe; font-size:11px; font-weight:900; }
.provider-device-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:12px; }
.provider-device-card { border:1px solid rgba(148,163,184,.18); border-radius:999px; padding:10px 16px; background:rgba(15,23,42,.72); min-height:66px; }
.provider-device-title { display:flex; justify-content:space-between; gap:8px; align-items:center; }
.provider-device-pill { display:inline-flex; border-radius:999px; padding:5px 11px; font-size:10px; font-weight:950; letter-spacing:.25px; }
.provider-pill-ready { color:#d1fae5; background:rgba(5,150,105,.36); border:1px solid rgba(52,211,153,.42); }
.provider-pill-missing { color:#fee2e2; background:rgba(153,27,27,.34); border:1px solid rgba(248,113,113,.38); }
.provider-pill-partial,.provider-pill-checking { color:#fef3c7; background:rgba(146,64,14,.34); border:1px solid rgba(251,191,36,.38); }
.provider-pill-unsupported { color:#cbd5e1; background:rgba(51,65,85,.52); border:1px solid rgba(148,163,184,.3); }
.provider-device-size { color:#bfdbfe; font-size:12px; font-weight:800; margin-top:4px; }
.provider-device-detail { color:#94a3b8; font-size:11px; margin-top:3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.provider-meta { color:#94a3b8; font-size:12px; margin-top:11px; }
.setup-progress-card { border-radius:16px; padding:13px 15px; border:1px solid rgba(148,163,184,.22); background:rgba(15,23,42,.74); margin:8px 0; }
.setup-progress-head,.setup-progress-meta { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.setup-progress-head span { border-radius:999px; padding:4px 9px; font-size:10px; font-weight:900; }
.setup-progress-meta { color:#bfdbfe; font-size:12px; margin-top:8px; }
.setup-progress-track { height:12px; border-radius:999px; background:rgba(30,41,59,.95); overflow:hidden; margin-top:9px; }
.setup-progress-fill { height:100%; border-radius:inherit; transition:width .2s ease; background:linear-gradient(90deg,#2563eb,#22d3ee); }
.setup-progress-success { border-color:rgba(52,211,153,.36); }
.setup-progress-success .setup-progress-fill { background:linear-gradient(90deg,#059669,#34d399); }
.setup-progress-failed { border-color:rgba(248,113,113,.4); }
.setup-progress-failed .setup-progress-fill { background:linear-gradient(90deg,#b91c1c,#fb7185); }
.setup-progress-running .setup-progress-head span { color:#dbeafe; background:rgba(30,64,175,.42); }
.setup-progress-success .setup-progress-head span { color:#d1fae5; background:rgba(5,150,105,.36); }
.setup-progress-failed .setup-progress-head span { color:#fee2e2; background:rgba(153,27,27,.34); }
.setup-progress-idle .setup-progress-head span { color:#cbd5e1; background:rgba(51,65,85,.52); }
@media (max-width:760px) { .provider-device-grid { grid-template-columns:1fr; } .provider-device-card { border-radius:18px; } }

.mode-buffer-help { border:1px solid rgba(96,165,250,.22); background:rgba(15,23,42,.55); color:#dbeafe; border-radius:14px; padding:10px 12px; margin-top:-4px; }
.mode-buffer-help .q { display:inline-flex; width:22px; height:22px; align-items:center; justify-content:center; border-radius:999px; background:#1d4ed8; color:white; font-weight:900; margin-left:8px; cursor:help; }
.mode-buffer-help .tip { display:none; margin-top:8px; color:#bfdbfe; font-size:13px; }
.mode-buffer-help:hover .tip { display:block; }

.gradio-container {
  max-width: 1520px !important;
  margin: 0 auto !important;
  padding: 22px 26px 44px !important;
  background:
    radial-gradient(circle at 12% -5%, rgba(37,99,235,.22), transparent 34%),
    radial-gradient(circle at 90% 4%, rgba(14,165,233,.13), transparent 28%),
    linear-gradient(180deg, #07101f 0%, #030711 100%);
  min-height: 100vh;
}
.hero {
  border: 1px solid rgba(96,165,250,.25);
  background: linear-gradient(145deg, rgba(13,28,58,.97), rgba(7,15,29,.92));
  border-radius: 24px;
  padding: 24px 26px;
  box-shadow: 0 18px 60px rgba(0,0,0,.35);
}
.hero h1 { margin: 7px 0 0; font-size: 34px; letter-spacing:-.7px; }
.hero p { margin: 8px 0 0; color: #dbeafe; }
.hero-topline { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.release-badge, .release-channel {
  display:inline-flex; align-items:center; min-height:25px; padding:4px 9px;
  border-radius:999px; font-size:11px; font-weight:800; letter-spacing:.55px;
  text-transform:uppercase;
}
.release-badge { color:#dbeafe; border:1px solid rgba(96,165,250,.3); background:rgba(30,64,175,.24); }
.release-channel { color:#a7f3d0; border:1px solid rgba(52,211,153,.25); background:rgba(6,78,59,.24); }
.hero-subtitle { max-width:920px; line-height:1.55; }
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

/* v8.9.2-R4 information architecture */
@keyframes ort-panel-in {
  from { opacity:0; transform:translateY(7px); }
  to { opacity:1; transform:translateY(0); }
}
.transition-panel { animation:ort-panel-in .22s ease-out both; }
.workspace-card {
  border:1px solid rgba(100,116,139,.2) !important;
  background:linear-gradient(155deg, rgba(15,23,42,.82), rgba(8,15,29,.7)) !important;
  border-radius:20px !important;
  padding:16px !important;
  box-shadow:0 14px 36px rgba(0,0,0,.14);
}
.setup-header {
  display:flex; align-items:flex-start; justify-content:space-between; gap:16px;
  margin:4px 0 12px;
}
.section-kicker {
  color:#60a5fa; font-size:11px; font-weight:900; letter-spacing:1px;
  text-transform:uppercase; margin-bottom:5px;
}
.section-title { color:#f8fafc; font-size:19px; font-weight:850; letter-spacing:-.25px; }
.section-copy { color:#94a3b8; font-size:13px; line-height:1.55; margin-top:5px; }
.step-badge {
  flex:0 0 auto; display:inline-flex; align-items:center; justify-content:center;
  width:30px; height:30px; border-radius:10px; color:#dbeafe; font-size:12px;
  font-weight:900; border:1px solid rgba(96,165,250,.25); background:rgba(30,64,175,.2);
}
.source-stage {
  border:1px solid rgba(56,189,248,.24) !important;
  background:linear-gradient(135deg, rgba(8,47,73,.28), rgba(15,23,42,.64)) !important;
  border-radius:22px !important;
  padding:17px 18px 14px !important;
  margin:12px 0 16px !important;
}
#translation_source [role='radiogroup'], #ui_level [role='radiogroup'] {
  display:grid !important; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:9px !important;
}
#ui_level [role='radiogroup'] { grid-template-columns:repeat(3, minmax(0, 1fr)); }
#translation_source label, #ui_level label {
  position:relative; border:1px solid rgba(148,163,184,.2) !important;
  background:rgba(15,23,42,.7) !important; border-radius:14px !important;
  padding:11px 13px !important; min-height:46px; transition:all .2s ease;
}
#translation_source label:hover, #ui_level label:hover {
  border-color:rgba(96,165,250,.55) !important; transform:translateY(-1px);
}
#translation_source label:has(input:checked), #ui_level label:has(input:checked) {
  border-color:#38bdf8 !important;
  background:linear-gradient(135deg, rgba(2,132,199,.3), rgba(30,64,175,.28)) !important;
  box-shadow:0 0 0 1px rgba(56,189,248,.14), 0 9px 24px rgba(2,132,199,.12);
}
.source-state {
  display:flex; align-items:flex-start; gap:11px; padding:12px 14px; margin-top:8px;
  border-radius:14px; border:1px solid rgba(52,211,153,.2); background:rgba(6,78,59,.17);
}
.source-state.audio { border-color:rgba(251,191,36,.28); background:rgba(120,53,15,.17); }
.source-state.audio.ready { border-color:rgba(52,211,153,.28); background:rgba(6,78,59,.17); }
.source-dot { width:9px; height:9px; margin-top:5px; border-radius:50%; background:#34d399; box-shadow:0 0 13px rgba(52,211,153,.8); }
.source-state.audio .source-dot { background:#fbbf24; box-shadow:0 0 13px rgba(251,191,36,.65); }
.source-state.audio.ready .source-dot { background:#34d399; box-shadow:0 0 13px rgba(52,211,153,.8); }
.source-state b { color:#f8fafc; display:block; font-size:13px; }
.source-state small { color:#cbd5e1; display:block; margin-top:3px; line-height:1.45; }
.guided-banner, .developer-banner {
  border-radius:18px; padding:13px 15px; margin:2px 0 14px;
  border:1px solid rgba(96,165,250,.2); background:rgba(30,64,175,.11);
}
.guided-banner b, .developer-banner b { color:#eff6ff; }
.guided-banner span, .developer-banner span { color:#bfdbfe; font-size:13px; margin-left:5px; }
.developer-banner {
  border-color:rgba(167,139,250,.32);
  background:linear-gradient(135deg, rgba(76,29,149,.24), rgba(30,41,59,.38));
  box-shadow:inset 3px 0 0 #8b5cf6;
}
.developer-banner .developer-tag {
  display:inline-flex; padding:3px 8px; border-radius:999px; margin-right:7px;
  color:#ede9fe; background:rgba(109,40,217,.35); font-size:10px; font-weight:900;
  letter-spacing:.7px; text-transform:uppercase;
}
.audio-preview {
  border:1px solid rgba(251,191,36,.24) !important;
  background:linear-gradient(145deg, rgba(69,26,3,.23), rgba(15,23,42,.72)) !important;
  border-radius:20px !important; padding:16px !important;
}
.availability-card {
  border:1px solid rgba(251,191,36,.26); border-radius:15px; padding:13px 14px;
  background:rgba(120,53,15,.16); color:#fde68a; line-height:1.55;
}
.availability-card strong { color:#fef3c7; }
.availability-card small { display:block; color:#d6d3d1; margin-top:5px; }
.audio-flow-grid {
  display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:9px; margin:12px 0 4px;
}
.audio-flow-item { border:1px solid rgba(148,163,184,.18); border-radius:13px; padding:10px; background:rgba(15,23,42,.5); }
.audio-flow-item.pending { border-style:dashed; opacity:.78; }
.audio-flow-item b { color:#f8fafc; font-size:12px; display:block; }
.audio-flow-item small { color:#94a3b8; font-size:11px; line-height:1.4; display:block; margin-top:4px; }
.control-divider { height:1px; background:linear-gradient(90deg, transparent, rgba(148,163,184,.24), transparent); margin:11px 0 13px; }
#start_primary button {
  background:linear-gradient(135deg, #0284c7, #2563eb) !important;
  color:white !important; border:1px solid rgba(125,211,252,.35) !important;
  box-shadow:0 10px 25px rgba(37,99,235,.22); font-weight:850 !important;
}
#audio_start_primary button {
  background:linear-gradient(135deg, #0f766e, #0284c7) !important;
  color:white !important; border:1px solid rgba(103,232,249,.35) !important;
  box-shadow:0 10px 25px rgba(8,145,178,.2); font-weight:850 !important;
}
.action-row { margin-top:10px; }
.developer-controls {
  border-left:3px solid rgba(139,92,246,.65) !important;
  padding-left:14px !important;
}
.log-accordion { margin-top:14px !important; }
@media (max-width: 820px) {
  .gradio-container { padding:14px 12px 30px !important; }
  .hero { padding:19px 18px; border-radius:19px; }
  .hero h1 { font-size:27px; }
  #translation_source [role='radiogroup'], #ui_level [role='radiogroup'] { grid-template-columns:1fr; }
  .audio-flow-grid { grid-template-columns:1fr; }
}

"""

USER_NOTE = """**Catatan Audio Tri-Mode · Japanese Quality Update**

- **OCR** dan **Audio** tetap saling eksklusif. Pergantian sumber menghentikan proses lama sebelum proses baru dijalankan.
- CPU memakai ASR CPU INT8 tanpa memeriksa CUDA. GPU memakai ASR CUDA secara ketat dan tidak berpindah diam-diam ke CPU.
- Hybrid memakai GPU sebagai utama dan CPU sebagai pemulihan; segmen aktif diputar ulang dengan ID yang sama jika worker CUDA gagal.
- Mode bawaan untuk GFL2 dub Jepang adalah **Hybrid + VAD + Normal + Japanese**.
- Quality gate menolak no-speech, pengulangan, kepadatan token tidak wajar, probabilitas rendah, dan frasa halusinasi sebelum diterjemahkan.
- Uji **File audio** tersedia untuk validasi pertama; Audio internal langsung memakai WASAPI loopback pada Windows.
- Normal menjaga alur tetap ringkas dan terpandu; Developer membuka kontrol pembangunan serta diagnostik lengkap.
- Untuk Girls' Frontline seri pertama, pilih game **GFL** agar footer `GFsystem` dan ikon kanan bawah tidak mencemari OCR, cache, atau NPC learning.
- **Freeze**, **Interval**, dan **Auto** mempertahankan perilaku runtime v8.9.2; Mode Buffer tetap OFF secara default.
- Jika Fast CT2 belum aktif, model Fast akan fallback dan belum valid untuk perbandingan performa Fast/Lite.
- Runtime cards dan Analyze Last Session membedakan requested vs effective settings.
"""

GAME_CHOICES = game_choices()
OA_GAME_CHOICES = [
    ("Daily / Media · film, YouTube, musik", "DAILY_MEDIA"),
    ("Girls' Frontline 2: Exilium", "GFL2_EXILIUM"),
    ("Girls' Frontline", "GFL"),
    ("Wuthering Waves", "WUTHERING_WAVES"),
    ("Game / aplikasi lain", "CUSTOM"),
]
OA_LANGUAGE_CHOICES = {
    "DAILY_MEDIA": [
        ("Smart Auto", "auto"), ("English", "en"),
        ("Japanese Specialist", "ja_specialist"), ("Chinese", "zh"), ("Korean", "ko"),
    ],
    "GFL2_EXILIUM": [("Japanese Specialist", "ja_specialist"), ("Chinese", "zh")],
    "GFL": [("Japanese Specialist", "ja_specialist")],
    "WUTHERING_WAVES": [
        ("English", "en"), ("Japanese Specialist", "ja_specialist"),
        ("Chinese", "zh"), ("Korean", "ko"),
    ],
    "CUSTOM": [
        ("Smart Auto", "auto"), ("English", "en"),
        ("Japanese Specialist", "ja_specialist"), ("Japanese Multilingual", "ja"),
        ("Chinese", "zh"), ("Korean", "ko"),
    ],
}


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


def _normalize_ui_mode(mode: str) -> str:
    token = str(mode or "recommended").strip().lower()
    if token in {"expert", "developer"}:
        return "developer"
    return "recommended"


def _ui_mode_visibility(mode: str):
    mode = _normalize_ui_mode(mode)
    return {
        "guided_header": mode != "developer",
        "developer_header": mode == "developer",
        "recommendation": mode in {"recommended", "developer"},
        "diagnostic": mode == "developer",
        "model_controls": mode in {"recommended", "developer"},
        "advanced_controls": mode == "developer",
        "runtime_summary": mode == "developer",
        "hardware": mode == "developer",
        "policy": mode == "developer",
    }


def _ui_mode_updates(mode: str):
    mode = _normalize_ui_mode(mode)
    _save_ui_pref(ui_mode=mode)
    v = _ui_mode_visibility(mode)
    return (
        gr.update(visible=v["guided_header"]),
        gr.update(visible=v["developer_header"]),
        gr.update(visible=v["recommendation"]),
        gr.update(visible=v["diagnostic"]),
        gr.update(visible=v["model_controls"]),
        gr.update(visible=v["advanced_controls"]),
        gr.update(visible=v["runtime_summary"]),
        gr.update(visible=v["hardware"]),
        gr.update(visible=v["policy"]),
    )


def _translation_source_status_html(source: str, profile: str = "normal", audio_mode: str = "hybrid", audio_engine: str = "azure_fallback", audio_usage: str = "live_media") -> str:
    source = str(source or "ocr").strip().lower()
    if source == "audio":
        probe = audio_runtime_probe(False, profile, audio_mode, audio_engine, audio_usage)
        ready = bool(probe.get("ready"))
        dependencies_ready = bool(probe.get("dependencies_ready"))
        model_ready = bool(probe.get("model_ready"))
        file_ready = bool(probe.get("file_test"))
        loopback_ready = bool(probe.get("live_loopback"))
        requested_mode = str(probe.get("requested_mode") or audio_mode).upper()
        effective_mode = str(probe.get("effective_mode") or audio_mode).upper()
        requested_engine = str(probe.get("audio_engine_requested") or audio_engine).upper()
        effective_engine = str(probe.get("audio_engine_effective") or audio_engine).upper()
        engine_reason = str(probe.get("audio_engine_reason") or "")
        cloud_probe = probe.get("cloud") or {}
        if effective_engine == "AZURE":
            loopback_ready = bool(cloud_probe.get("wasapi"))
            file_ready = True
        if ready:
            title = f"Audio · {str(audio_usage).replace('_', ' ').title()} · {requested_engine} siap"
            detail = (
                f"Mesin efektif={effective_engine}; perangkat lokal={effective_mode}. "
                f"WASAPI loopback={'siap' if loopback_ready else 'belum'}. "
                + (
                    "Azure menampilkan interim selama karakter berbicara; hasil final menguncinya."
                    if effective_engine == "AZURE"
                    else (
                        "Local Live memakai rolling-partial ASR: subtitle mulai diperbarui selama ucapan berlangsung. "
                        "Jeda hanya mengunci final; GPU mempercepat pembaruan dan Hybrid beralih ke CPU bila CUDA gagal."
                    )
                )
            )
        elif requested_engine != "LOCAL" and not bool(cloud_probe.get("ready")):
            title = "Azure Live Media · Perlu setup"
            detail = (
                f"{str(cloud_probe.get('message') or 'Siapkan runtime dan kredensial Azure.')} "
                f"Status={engine_reason or 'AZURE_NOT_READY'}. API key tidak pernah ditulis ke ZIP atau log."
            )
        elif dependencies_ready and not model_ready:
            model_status = probe.get("model_status") or {}
            problem_state = model_status.get("fallback") if str(audio_mode).lower() == "hybrid" else model_status.get("primary")
            problem_state = problem_state or model_status
            problems = list(problem_state.get("missing_files") or []) + list(problem_state.get("invalid_files") or [])
            title = "Audio Translate · Unduhan model belum lengkap"
            detail = (
                f"Tekan Siapkan Audio {requested_mode} lagi untuk melanjutkan unduhan cache. "
                + (("Berkas yang belum siap: " + ", ".join(problems) + ". ") if problems else "")
                + "Mulai Audio tetap dikunci sampai validasi lengkap lulus."
            )
        else:
            title = "Audio Translate · Perlu setup satu kali"
            detail = f"Tekan Siapkan Audio {requested_mode} pada panel di bawah. Runtime Audio dipasang terisolasi sehingga runtime OCR tidak diubah."
        return (
            f"<div class='source-state audio{' ready' if ready else ''}'><span class='source-dot'></span><div>"
            f"<b>{html.escape(title)}</b>"
            f"<small>{html.escape(detail)}</small>"
            "</div></div>"
        )
    return (
        "<div class='source-state'><span class='source-dot'></span><div>"
        "<b>OCR Translate · Siap digunakan</b>"
        "<small>Membaca dialog dari area tangkapan dan menerjemahkannya ke overlay. "
        "Ini adalah sumber runtime aktif pada rilis saat ini.</small>"
        "</div></div>"
    )


def _stop_runtime_for_source_switch() -> None:
    try:
        stop_model()
    except Exception:
        pass
    finally:
        finish_source_switch_stop()


def _translation_source_updates(source: str, profile: str = "normal", audio_mode: str = "hybrid", audio_engine: str = "azure_fallback", audio_usage: str = "live_media"):
    source = str(source or "ocr").strip().lower()
    if source not in {"ocr", "audio"}:
        source = "ocr"
    _save_ui_pref(translation_source=source)
    is_ocr = source == "ocr"
    if prepare_source_switch_stop():
        threading.Thread(target=_stop_runtime_for_source_switch, daemon=True, name="ort-source-switch-stop").start()
    return (
        _translation_source_status_html(source, profile, audio_mode, audio_engine, audio_usage),
        gr.update(visible=is_ocr),
        gr.update(visible=not is_ocr),
        gr.update(visible=is_ocr),
        gr.update(visible=not is_ocr),
    )


def _audio_profile_description(profile: str, audio_mode: str = "hybrid") -> str:
    mode = str(audio_mode or "hybrid").lower()
    mapping = {
        "speed": {"cpu": "base CPU INT8", "gpu": "small GPU INT8-FP16", "hybrid": "small GPU → base CPU"},
        "normal": {"cpu": "small CPU INT8", "gpu": "small GPU INT8-FP16", "hybrid": "small GPU → base CPU"},
        "accurate": {"cpu": "small CPU INT8", "gpu": "medium GPU INT8-FP16", "hybrid": "medium GPU → small CPU"},
    }
    key = str(profile or "normal").lower()
    label = mapping.get(key, mapping["normal"]).get(mode, mapping["normal"]["hybrid"])
    detail = {
        "speed": "Azure memakai endpoint Jepang sekitar 280 ms, partial paling awal, dan frame 20 ms. Fallback lokal memakai potongan responsif.",
        "normal": "Azure memakai endpoint Jepang sekitar 350 ms dengan keseimbangan stabilitas dan kecepatan. Ini pilihan rekomendasi.",
        "accurate": "Azure memberi jeda sekitar 480 ms agar frasa lebih lengkap; fallback lokal memakai model dan beam lebih besar.",
    }.get(key, "")
    return f"**{key.title()} · {label}** — {detail}"


def _audio_input_updates(input_mode: str):
    file_mode = str(input_mode or "loopback").lower() == "file"
    return gr.update(visible=file_mode), gr.update(interactive=not file_mode)


def _audio_language_for_game(game: str, current_language: str):
    current = str(current_language or "auto").lower()
    if str(game or "").upper() == "GFL2_EXILIUM" and current in {"", "auto", "auto_detect"}:
        _save_ui_pref(audio_language="ja")
        return "ja"
    return current


def _refresh_audio_devices_ui(audio_mode: str, profile: str, audio_engine: str, audio_usage: str):
    choices, value, message = audio_devices_for_ui(True, audio_mode, audio_engine)
    return gr.update(choices=choices, value=value), message, _translation_source_status_html("audio", profile, audio_mode, audio_engine, audio_usage)


def _setup_audio_ui(audio_mode: str, profile: str, audio_engine: str, audio_usage: str):
    message = setup_audio_runtime_text(profile, audio_mode)
    choices, value, device_message = audio_devices_for_ui(True, audio_mode, audio_engine)
    combined = message + "\n\n" + device_message + "\n\n" + audio_runtime_status_text(profile, audio_mode, audio_engine, audio_usage)
    status_html = _translation_source_status_html("audio", profile, audio_mode, audio_engine, audio_usage)
    return combined, gr.update(choices=choices, value=value), status_html, status_html


def _audio_mode_updates(audio_mode: str, profile: str, audio_engine: str, audio_usage: str):
    mode = str(audio_mode or "hybrid").lower()
    choices, value, _ = audio_devices_for_ui(False, mode, audio_engine)
    return (
        _audio_profile_description(profile, mode),
        gr.update(value=f"Siapkan Fallback Lokal {mode.upper()}" if str(audio_engine) != "local" else f"Siapkan Audio {mode.upper()}"),
        _translation_source_status_html("audio", profile, mode, audio_engine, audio_usage),
        audio_runtime_status_text(profile, mode, audio_engine, audio_usage),
        gr.update(choices=choices, value=value),
    )


def _audio_engine_updates(audio_engine: str, audio_mode: str, profile: str, audio_usage: str):
    engine = str(audio_engine or "azure_fallback").lower()
    _save_ui_pref(audio_engine=engine)
    choices, value, message = audio_devices_for_ui(False, audio_mode, engine)
    setup_label = f"Siapkan Audio {str(audio_mode).upper()}" if engine == "local" else f"Siapkan Fallback Lokal {str(audio_mode).upper()}"
    return (
        _translation_source_status_html("audio", profile, audio_mode, engine, audio_usage),
        audio_runtime_status_text(profile, audio_mode, engine, audio_usage),
        gr.update(choices=choices, value=value),
        message,
        gr.update(value=setup_label),
    )


def _audio_usage_updates(audio_usage: str, profile: str, audio_mode: str, audio_engine: str):
    usage = str(audio_usage or "live_media").lower()
    _save_ui_pref(audio_usage=usage)
    return _translation_source_status_html("audio", profile, audio_mode, audio_engine, usage)


def _setup_audio_cloud_ui(audio_engine: str, profile: str, audio_mode: str, audio_usage: str):
    message = setup_audio_cloud_runtime_text()
    combined = message + "\n\n" + audio_cloud_runtime_status_text()
    return combined, _translation_source_status_html("audio", profile, audio_mode, audio_engine, audio_usage)


def _save_audio_cloud_ui(region: str, api_key: str, language: str, audio_engine: str, profile: str, audio_mode: str, audio_usage: str):
    source_locale = {
        "ja": "ja-JP",
        "en": "en-US",
        "zh": "zh-CN",
        "ko": "ko-KR",
    }.get(str(language or "").lower(), str(language or "ja-JP"))
    message = save_audio_cloud_config_from_ui(region, api_key, source_locale, "id")
    combined = message + "\n\n" + audio_cloud_runtime_status_text()
    return combined, gr.update(value=""), _translation_source_status_html("audio", profile, audio_mode, audio_engine, audio_usage)


def _clear_audio_cloud_ui(audio_engine: str, profile: str, audio_mode: str, audio_usage: str):
    message = clear_audio_cloud_credentials_text()
    combined = message + "\n\n" + audio_cloud_runtime_status_text()
    return combined, _translation_source_status_html("audio", profile, audio_mode, audio_engine, audio_usage)


def _upload_path(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("path") or value.get("name") or "")
    return str(getattr(value, "name", "") or value)


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


def _start(model, game, mode, engine, interval_ms, ocr_resolution, settings_mode, responsive_story_mode, diagnostic_profile, mode_buffer_enabled, translation_source="ocr"):
    if str(translation_source or "ocr").strip().lower() != "ocr":
        _, log, _, notice = refresh_state()
        msg = (
            "Sumber aktif adalah Audio. Gunakan tombol 'Mulai Audio' agar konfigurasi WASAPI/ASR yang dipilih diterapkan."
        )
        notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
        return _status_html("STATUS: AUDIO READY"), runtime_summary_text(), log, msg, "", notice_md
    manual = _settings_mode_is_manual(settings_mode)
    # v8.6: restore the previous safe interval floor for Interval mode.
    # 45ms remains technically possible only in custom experiments, but the normal WebUI path
    # should no longer silently make Interval more aggressive than the pre-v8.2.1 behavior.
    try:
        if str(mode or "").lower() == "interval" and int(interval_ms) < 90:
            interval_ms = 90
    except Exception:
        pass
    status, log, msg, notice = start_model(model, game, mode, engine, interval_ms, ocr_resolution, "normal" if manual else "auto", manual, settings_mode, bool(responsive_story_mode), str(diagnostic_profile or "baseline"), bool(mode_buffer_enabled))
    err_md = ""
    if "ERROR" in (status or ""):
        err_md = f"**Error:**\n\n```\n{msg}\n```"
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return _status_html(status), runtime_summary_text(), log, msg, err_md, notice_md


def _start_audio(model, game, input_mode, device_index, language, language_correction, language_lock, processing, audio_usage, audio_engine, audio_mode, profile, test_file):
    file_path = _upload_path(test_file)
    _save_ui_pref(
        translation_source="audio",
        audio_input_mode=str(input_mode or "loopback"),
        audio_device_index=str(device_index or "-1"),
        audio_language=str(language or "auto"),
        audio_language_correction=str(language_correction or "balanced"),
        audio_language_lock=bool(language_lock),
        audio_processing=str(processing or "vad"),
        audio_profile=str(profile or "normal"),
        audio_mode=str(audio_mode or "hybrid"),
        audio_usage=str(audio_usage or "live_media"),
        audio_engine=str(audio_engine or "azure_fallback"),
    )
    status, log, msg, notice = start_audio_model(
        model,
        game,
        input_mode,
        device_index,
        language,
        processing,
        profile,
        file_path,
        audio_mode,
        audio_usage,
        audio_engine,
        language_correction,
        language_lock,
    )
    err_md = ""
    if "ERROR" in (status or ""):
        err_md = f"**Audio Error:**\n\n```\n{msg}\n```"
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return _status_html(status), audio_runtime_status_text(profile, audio_mode, audio_engine, audio_usage), log, msg, err_md, notice_md


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


def _oa_ui_mode_is_developer(mode: str) -> bool:
    return str(mode or "normal").strip().lower() in {"developer", "expert"}


def _oa_ui_mode_updates(mode: str):
    token = "developer" if _oa_ui_mode_is_developer(mode) else "normal"
    _save_ui_pref(oa_ui_mode=token)
    if token == "developer":
        help_html = (
            "<div class='developer-banner'><span class='developer-tag'>Developer workspace</span>"
            "<b>Seluruh kontrak pipeline dan diagnostik ditampilkan.</b>"
            "<span>Gunakan mode ini saat membangun provider, memeriksa ID internal, A/B test, JSON plan, dan log runtime.</span></div>"
        )
    else:
        help_html = (
            "<div class='guided-banner'><b>Normal Mode:</b>"
            "<span>pilih preset → periksa status siap → tekan Mulai Audio Lab. "
            "Detail provider tetap disembunyikan agar alur penggunaan konsisten.</span></div>"
        )
    return gr.update(value=help_html), gr.update(visible=token == "developer")


def _oa_overlay_mode_updates(mode: str):
    token = str(mode or "adaptive").strip().lower()
    if token not in {"adaptive", "fixed", "custom"}:
        token = "adaptive"
    _save_ui_pref(oa_overlay_mode=token)
    return (
        gr.update(visible=token in {"fixed", "custom"}),
        gr.update(visible=token == "custom"),
    )


def _oa_game_profile_updates(game: str, current_language: str):
    game_key = str(game or "DAILY_MEDIA").strip().upper()
    choices = OA_LANGUAGE_CHOICES.get(game_key, OA_LANGUAGE_CHOICES["CUSTOM"])
    values = {value for _label, value in choices}
    current = str(current_language or "").strip().lower()
    value = current if current in values else choices[0][1]
    _save_ui_pref(oa_game=game_key, oa_language=value)
    notes = {
        "DAILY_MEDIA": "Daily / Media tidak mengunci Japanese Specialist. English memakai transcribe langsung; Jepang/China/Korea memakai jalur speech → English → Indonesia.",
        "GFL2_EXILIUM": "Profil GFL2 pada instalasi ini dibatasi ke dub Japanese dan Chinese.",
        "GFL": "Girls' Frontline memakai dub Japanese sebagai pilihan utama.",
        "WUTHERING_WAVES": "Wuthering Waves menyediakan pilihan English, Japanese, Chinese, dan Korean.",
    }
    note = notes.get(game_key, "Profil Custom membiarkan user memilih bahasa yang tersedia pada aplikasi.")
    return gr.update(choices=choices, value=value), note


def _oa_resource_policy_updates(policy: str):
    token = str(policy or "normal").strip().lower()
    if token not in {"efficient", "normal", "optimal"}:
        token = "normal"
    _save_ui_pref(oa_resource_policy=token)
    descriptions = {
        "efficient": "**Efficient:** satu stream ASR ringan, tanpa koreksi model kedua, konteks lebih pendek, prioritas stabilitas dan penggunaan resource rendah.",
        "normal": "**Normal:** satu model utama yang stabil. Japanese Specialist tetap digunakan ketika dipilih, tetapi dual-stream correction dimatikan.",
        "optimal": "**Optimal:** mengukur headroom VRAM dan latency preflight. GPU hanya dipakai ketika cukup sehat; jika tidak, sistem beralih ke CPU single-stream.",
    }
    return descriptions[token]


def _oa_overlay_config(
    mode: str, width: int, height: int, font_size: int, opacity: int, show_source: bool, alignment: str,
) -> dict:
    return {
        "mode": str(mode or "adaptive"),
        "width_percent": int(width or 92),
        "height_px": int(height or 190),
        "font_size": int(font_size or 15),
        "opacity_percent": int(opacity or 91),
        "show_source": bool(show_source),
        "alignment": str(alignment or "left"),
    }


def _oa_toggle_preview_ui(
    active: bool, mode: str, width: int, height: int, font_size: int, opacity: int,
    show_source: bool, alignment: str,
):
    config = _oa_overlay_config(mode, width, height, font_size, opacity, show_source, alignment)
    state, label, message = toggle_overlay_preview(bool(active), config)
    return state, gr.update(value=label), message


def _oa_update_preview_ui(
    active: bool, mode: str, width: int, height: int, font_size: int, opacity: int,
    show_source: bool, alignment: str,
):
    if not bool(active):
        return "Preview belum aktif"
    config = _oa_overlay_config(mode, width, height, font_size, opacity, show_source, alignment)
    update_overlay_preview(config, active=True)
    return "Preview aktif · perubahan diterapkan realtime"


def _oa_provider_device(provider_id: str, audio_mode: str) -> tuple[str, Path]:
    provider = normalize_asr_model_provider(provider_id)
    mode = str(audio_mode or "cpu").strip().lower()
    if provider == PROVIDER_SENSEVOICE:
        return "cpu", AUDIO_CPU_PYTHON
    if mode in {"gpu", "hybrid"} and AUDIO_GPU_PYTHON.is_file():
        return "cuda", AUDIO_GPU_PYTHON
    return "cpu", AUDIO_CPU_PYTHON


def _oa_delivery_mode_updates(delivery_mode: str, cloud_provider: str):
    mode = str(delivery_mode or "offline").strip().lower()
    if mode not in {"offline", "online", "hybrid"}:
        mode = "offline"
    cloud = str(cloud_provider or "azure").strip().lower()
    if cloud not in {"azure", "google", "aws"}:
        cloud = "azure"
    _save_ui_pref(oa_delivery_mode=mode, oa_cloud_provider=cloud)
    messages = {
        "offline": "**Offline:** seluruh ASR dan terjemahan berjalan lokal. Cloud provider tidak digunakan.",
        "online": "**Online:** Azure menjadi provider live pada v9.0.4. Google dan AWS tersedia sebagai katalog benchmark, belum sebagai live adapter.",
        "hybrid": "**Hybrid delivery:** Azure primary dengan local locked-provider fallback. Model lokal yang dipilih tetap dikunci dan tidak diganti.",
    }
    extra = "" if cloud == "azure" or mode == "offline" else "\n\n> Provider ini catalog-only; Start akan diblokir sampai Azure dipilih."
    return messages[mode] + extra


def _oa_human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _oa_device_pill(device: str, item: dict) -> str:
    level = str(item.get("status_level") or ("ready" if item.get("ready") else "missing"))
    labels = {
        "ready": ("READY", "provider-pill-ready"),
        "partial": ("BELUM TERVERIFIKASI", "provider-pill-partial"),
        "unsupported": ("TIDAK DIDUKUNG", "provider-pill-unsupported"),
        "missing": ("BELUM TERPASANG", "provider-pill-missing"),
    }
    label, css = labels.get(level, labels["missing"])
    downloaded = int(item.get("model_downloaded_bytes", 0) or 0)
    total = int(item.get("model_total_bytes", 0) or 0)
    size_text = "Ukuran belum diketahui"
    if total:
        size_text = f"{_oa_human_bytes(downloaded)} / {_oa_human_bytes(total)}"
    bridge = item.get("bridge_ready")
    bridge_text = ""
    if bridge is True:
        bridge_text = " · Bridge READY"
    elif bridge is False:
        bridge_text = " · Bridge belum siap"
    detail = "; ".join(item.get("errors") or item.get("warnings") or []) or item.get("recommended_for") or "-"
    return (
        "<div class='provider-device-card'>"
        f"<div class='provider-device-title'><b>{html.escape(device.upper())}</b>"
        f"<span class='provider-device-pill {css}'>{html.escape(label)}</span></div>"
        f"<div class='provider-device-size'>{html.escape(size_text + bridge_text)}</div>"
        f"<div class='provider-device-detail'>{html.escape(str(detail))}</div>"
        "</div>"
    )


def _oa_provider_status_ui(provider_id: str, audio_mode: str | None = None) -> str:
    provider = normalize_asr_model_provider(provider_id)
    _save_ui_pref(oa_asr_model_provider=provider)
    spec = ASR_PROVIDERS[provider]
    cpu = asr_model_provider_status(AUDIO_MODEL_ROOT, provider, "cpu", AUDIO_CPU_PYTHON)
    cuda = asr_model_provider_status(AUDIO_MODEL_ROOT, provider, "cuda", AUDIO_GPU_PYTHON)
    return (
        "<div class='provider-status-panel'>"
        f"<div class='provider-status-head'><div><small>MODEL HARD LOCK</small><h3>{html.escape(spec.label)}</h3></div>"
        "<span class='provider-lock-pill'>TERKUNCI</span></div>"
        "<p>Periksa status membaca instalasi CPU dan GPU secara terpisah. Model tidak akan diganti otomatis saat sesi berjalan.</p>"
        "<div class='provider-device-grid'>"
        f"{_oa_device_pill('cpu', cpu)}{_oa_device_pill('gpu', cuda)}"
        "</div>"
        f"<div class='provider-meta'>Pemilik: <b>{html.escape(spec.owner)}</b> · Backend: "
        f"<b>{html.escape(spec.backend)}</b> · Output: <b>{html.escape(spec.output_language)}</b></div>"
        "</div>"
    )



def _oa_refresh_provider_status_ui(provider_id: str, audio_mode: str | None = None) -> str:
    """Run a fresh CPU/GPU probe when the user explicitly checks model status.

    `_oa_provider_status_ui` already reads the persistent setup manifests, validates
    model files, probes the selected runtime modules, checks CUDA-vs-CPU wheels,
    and verifies the Japanese translation bridge. Keeping the explicit refresh
    callback as a thin wrapper avoids stale UI wiring while preserving one source
    of truth for status rendering.
    """
    return _oa_provider_status_ui(provider_id, audio_mode)


def _oa_progress_html(state: dict | None = None) -> str:
    data = state or {}
    percent = max(0.0, min(100.0, float(data.get("percent", 0.0) or 0.0)))
    total = int(data.get("total_bytes", 0) or 0)
    downloaded = int(data.get("downloaded_bytes", 0) or 0)
    phase = str(data.get("phase") or "Belum ada proses setup")
    device = str(data.get("device") or "-").upper()
    status = str(data.get("status") or "idle")
    status_label = {
        "idle": "MENUNGGU",
        "running": "BERJALAN",
        "success": "BERHASIL",
        "failed": "GAGAL",
    }.get(status, status.upper())
    css = {
        "idle": "setup-progress-idle",
        "running": "setup-progress-running",
        "success": "setup-progress-success",
        "failed": "setup-progress-failed",
    }.get(status, "setup-progress-idle")
    if total:
        amount = f"{_oa_human_bytes(downloaded)} dari {_oa_human_bytes(total)}"
    else:
        amount = "Ukuran model sedang diperiksa" if status == "running" else "Belum ada unduhan"
    return (
        f"<div class='setup-progress-card {css}'>"
        f"<div class='setup-progress-head'><b>{html.escape(phase)}</b><span>{html.escape(status_label)}</span></div>"
        f"<div class='setup-progress-meta'><span>Target: {html.escape(device)}</span><span>{html.escape(amount)}</span>"
        f"<strong>{percent:.1f}%</strong></div>"
        f"<div class='setup-progress-track'><div class='setup-progress-fill' style='width:{percent:.2f}%'></div></div>"
        "</div>"
    )


def _oa_setup_devices(setup_target: str | None, provider: str) -> list[tuple[str, Path]]:
    target = str(setup_target or "").strip().lower()
    if target not in {"cpu", "gpu", "both"}:
        raise ValueError("Pilih target setup: CPU, GPU, atau Keduanya sebelum memulai.")
    spec = ASR_PROVIDERS[provider]
    requested = ["cpu", "cuda"] if target == "both" else (["cuda"] if target == "gpu" else ["cpu"])
    targets: list[tuple[str, Path]] = []
    for device in requested:
        if device not in spec.supported_devices:
            raise ValueError(f"{spec.label} tidak mendukung target {device.upper()}.")
        runtime = AUDIO_GPU_PYTHON if device == "cuda" else AUDIO_CPU_PYTHON
        if not runtime.is_file():
            raise FileNotFoundError(f"Runtime {device.upper()} tidak ditemukan: {runtime}")
        targets.append((device, runtime))
    return targets


def _oa_setup_command(python_path: Path, provider: str, device: str) -> list[str]:
    return [
        str(python_path), str(AUDIO_PROVIDER_SETUP), provider,
        "--runtime-root", str(AUDIO_RUNTIME_ROOT),
        "--model-root", str(AUDIO_MODEL_ROOT),
        "--status-root", str(AUDIO_RUNTIME_ROOT / "provider_setup_status"),
        "--python", str(python_path),
        "--device", "cuda" if device == "cuda" else "cpu",
        "--cuda-variant", "auto",
    ]


def _oa_parse_setup_event(line: str) -> dict | None:
    prefix = "ORT_SETUP_EVENT "
    if not line.startswith(prefix):
        return None
    try:
        value = json.loads(line[len(prefix):].strip())
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _oa_stream_setup_process(command: list[str], timeout_seconds: int = 3600):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        command, cwd=str(PROJECT_ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    output_queue: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            output_queue.put(raw.rstrip("\r\n"))
        output_queue.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    started = time.monotonic()
    finished_reader = False
    while process.poll() is None or not finished_reader or not output_queue.empty():
        if time.monotonic() - started > timeout_seconds:
            process.kill()
            raise TimeoutError("Setup provider melewati batas 60 menit.")
        try:
            line = output_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        if line is None:
            finished_reader = True
            continue
        yield line
    thread.join(timeout=3)
    if process.returncode != 0:
        raise RuntimeError(f"Proses setup berhenti dengan exit code {process.returncode}.")


def _oa_setup_selected_provider_ui(provider_id: str, setup_target: str | None):
    provider = normalize_asr_model_provider(provider_id)
    logs: list[str] = []
    state = {"status": "running", "phase": "Memulai setup provider", "device": setup_target or "-", "percent": 0.0}
    last_logged_percent = -10
    try:
        targets = _oa_setup_devices(setup_target, provider)
    except Exception as exc:
        message = f"SETUP: GAGAL · {type(exc).__name__}: {exc}"
        logs.append(message)
        state.update(status="failed", phase="Setup tidak dimulai")
        yield _oa_progress_html(state), "\n".join(logs), _oa_provider_status_ui(provider), gr.update(visible=True), gr.update(value=None), ""
        return

    logs.append(f"ORT {APP_VERSION_TAG} Setup Provider · model terkunci={provider}")
    logs.append("Target yang dipilih: " + ", ".join(device.upper() for device, _ in targets))
    yield _oa_progress_html(state), "\n".join(logs), _oa_provider_status_ui(provider), gr.update(visible=True), gr.update(), ""

    try:
        for device, runtime_python in targets:
            state.update(status="running", phase=f"Menyiapkan {ASR_PROVIDERS[provider].label} {device.upper()}", device=device, percent=0.0, total_bytes=0, downloaded_bytes=0)
            commands = [_oa_setup_command(runtime_python, provider, device)]
            if ASR_PROVIDERS[provider].output_language == "ja":
                commands.append(_oa_setup_command(runtime_python, "argos_bridge", device))
            for command in commands:
                for line in _oa_stream_setup_process(command):
                    event = _oa_parse_setup_event(line)
                    if event:
                        kind = str(event.get("event") or "")
                        if kind in {"model_info", "download_progress", "download_complete"}:
                            state.update(
                                total_bytes=int(event.get("total_bytes", state.get("total_bytes", 0)) or 0),
                                downloaded_bytes=int(event.get("downloaded_bytes", state.get("downloaded_bytes", 0)) or 0),
                                percent=float(event.get("percent", state.get("percent", 0.0)) or 0.0),
                            )
                            current_bucket = int(float(state.get("percent", 0)) // 10 * 10)
                            if current_bucket >= last_logged_percent + 10:
                                last_logged_percent = current_bucket
                                logs.append(
                                    f"DOWNLOAD {device.upper()}: {_oa_human_bytes(state['downloaded_bytes'])} / "
                                    f"{_oa_human_bytes(state['total_bytes'])} ({state['percent']:.1f}%)"
                                )
                        elif kind == "phase":
                            state["phase"] = str(event.get("message") or event.get("phase") or state["phase"])
                            logs.append(f"FASE {device.upper()}: {state['phase']}")
                        elif kind == "download_retry":
                            delay = float(event.get("delay_seconds", 0) or 0)
                            attempt = int(event.get("attempt", 0) or 0)
                            maximum = int(event.get("max_attempts", 0) or 0)
                            label = str(event.get("label") or "unduhan model")
                            state["phase"] = f"Koneksi terputus · mencoba ulang {attempt}/{maximum}"
                            logs.append(
                                f"RETRY {device.upper()}: {label} · percobaan {attempt}/{maximum} "
                                f"dalam {delay:.1f} detik · {event.get('error', '')}"
                            )
                        elif kind == "cache_reuse":
                            logs.append(
                                f"CACHE {device.upper()}: memakai kembali "
                                f"{_oa_human_bytes(int(event.get('downloaded_bytes', 0) or 0))} "
                                f"yang sudah selesai ({float(event.get('percent', 0) or 0):.1f}%)."
                            )
                        elif kind == "runtime_reuse":
                            logs.append(
                                f"RUNTIME {device.upper()}: sudah siap; instalasi dependency dilewati."
                            )
                        elif kind == "hf_auth":
                            auth_label = "TERAUTENTIKASI" if event.get("authenticated") else "TANPA LOGIN"
                            logs.append(f"HUGGING FACE: {auth_label}")
                        elif kind == "setup_start":
                            state["device"] = str(event.get("device") or device)
                        elif kind in {"device_ready", "bridge_ready"}:
                            logs.append(f"STATUS {device.upper()}: {kind.upper()} = READY")
                        elif kind == "setup_failed":
                            logs.append("ERROR: " + str(event.get("error") or "Setup gagal"))
                    elif line.strip():
                        logs.append(line)
                    if len(logs) > 900:
                        logs = logs[-900:]
                    yield _oa_progress_html(state), "\n".join(logs), _oa_provider_status_ui(provider), gr.update(visible=True), gr.update(), ""
            logs.append(f"TARGET {device.upper()}: BERHASIL")
        state.update(status="success", phase="Model dan runtime berhasil disiapkan", percent=100.0)
        logs.append("SETUP: BERHASIL")
    except BaseException as exc:
        state.update(status="failed", phase="Unduhan/setup terhenti · aman untuk dilanjutkan")
        logs.append(f"SETUP: GAGAL · {type(exc).__name__}: {exc}")
        logs.append(
            "STATUS PEMULIHAN: file yang sudah selesai tetap tersimpan di cache. "
            "Pilih target yang sama lalu tekan Siapkan model yang dipilih untuk melanjutkan."
        )
    yield _oa_progress_html(state), "\n".join(logs), _oa_provider_status_ui(provider), gr.update(visible=bool(logs)), gr.update(value=None), ""



def _oa_benchmark_providers_ui(test_file, providers, device: str):
    wav_path = Path(_upload_path(test_file) or "")
    if not wav_path.is_file():
        return "### Benchmark belum berjalan\nPilih satu file WAV PCM terlebih dahulu."
    selected = [normalize_asr_model_provider(item) for item in (providers or [])]
    if not selected:
        return "### Benchmark belum berjalan\nPilih minimal satu model ASR."
    requested_device = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    runtime_python = AUDIO_GPU_PYTHON if requested_device == "cuda" else AUDIO_CPU_PYTHON
    if not runtime_python.is_file():
        return f"### Benchmark gagal\nRuntime {requested_device} tidak ditemukan: `{runtime_python}`"
    results = benchmark_many(
        runtime_python, AUDIO_PROVIDER_SIDECAR, AUDIO_MODEL_ROOT,
        wav_path, selected, requested_device,
    )
    return results_markdown(results)


def _oa_provider_transparency_text() -> str:
    status = {}
    try:
        path = PROJECT_ROOT / "status" / "audio_runtime.json"
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            status = loaded if isinstance(loaded, dict) else {}
    except Exception:
        status = {}
    selected = normalize_asr_model_provider(
        status.get("asr_provider") or PREFS.get("oa_asr_model_provider", PROVIDER_KOTOBA)
    )
    spec = ASR_PROVIDERS[selected]
    effective_model = status.get("model") or status.get("asr_model") or "belum ada sesi"
    effective_device = status.get("asr_device") or status.get("device") or "-"
    translation_engine = status.get("translation_engine") or "belum ada hasil"
    resource = status.get("resource_policy") or status.get("audio_resource_policy") or "normal"
    fallback = status.get("translation_process_mode") or "locked-provider"
    delivery = status.get("delivery_mode") or PREFS.get("oa_delivery_mode", "offline")
    cloud = status.get("cloud_provider") or PREFS.get("oa_cloud_provider", "azure")
    locked = status.get("model_lock", True)
    return f"""### Transparansi provider aktif

| Tahap | Provider / pemilik | Lisensi | Peran | Efektif saat ini |
|---|---|---|---|---|
| Audio capture | PyAudioWPatch community | MIT | WASAPI loopback Windows | `{status.get('device_index', '-')}` |
| Model ASR | {spec.label} · {spec.owner} | {spec.license} | {spec.purpose} | `{effective_model}` · `{effective_device}` |
| Backend ASR | {spec.backend} | lihat provider | Eksekusi provider yang dipilih | lock=`{locked}` |
| Translation | OPUS-MT CTranslate2 + Argos bridge untuk sumber Jepang | Apache-2.0 / Argos packages | EN/JA → Indonesian | `{translation_engine}` |
| Delivery | ORT cloud router | ORT native | Offline / Online / Hybrid | `{delivery}` · cloud=`{cloud}` |
| VAD | ORT RMS + semantic no-speech gate | ORT native | Menolak noise dan segmen palsu | `{status.get('processing', 'vad')}` |
| Recovery | ORT latest-wins locked worker | ORT native | Restart tanpa substitusi provider | `{fallback}` |

Resource policy efektif: **{resource}**. Requested provider dan effective provider harus sama selama model lock aktif."""

def _oa_live_log_tick(enabled: bool, profile: str, audio_mode: str):
    if not bool(enabled):
        return (gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    status, log_text, err, _notice = refresh_state()
    err_md = f"**Error terakhir:**\n\n```\n{err}\n```" if err else ""
    return (
        _status_html(status),
        audio_runtime_status_text(profile, audio_mode, "local", "live_media"),
        log_text,
        err or "",
        err_md,
        _oa_provider_transparency_text(),
    )


def _oa_apply_preset_ui(preset_id: str, language: str, agreement_passes: int, ui_mode: str):
    values = architecture_apply_preset(preset_id)
    validation = architecture_runtime_validation_text(
        values[0], values[1], values[2], values[3], values[4], values[5],
        language, agreement_passes, ui_mode,
    )
    return (*values, validation)


def _oa_refresh_with_validation(
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    language: str,
    agreement_passes: int,
    ui_mode: str,
):
    rendered = architecture_refresh(source, vad, asr, streaming, translation, overlay)
    validation = architecture_runtime_validation_text(
        source, vad, asr, streaming, translation, overlay,
        language, agreement_passes, ui_mode,
    )
    return (*rendered, validation)


def _oa_runtime_validation_ui(
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    language: str,
    agreement_passes: int,
    ui_mode: str,
):
    return architecture_runtime_validation_text(
        source, vad, asr, streaming, translation, overlay,
        language, agreement_passes, ui_mode,
    )


def _oa_start_audio_ui(
    game: str,
    input_mode: str,
    device_index: str,
    language: str,
    audio_mode: str,
    profile: str,
    test_file,
    preset_id: str,
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    agreement_passes: int,
    language_correction: str,
    language_lock: bool,
    ui_mode: str,
    overlay_mode: str,
    overlay_width_percent: int,
    overlay_height_px: int,
    overlay_font_size: int,
    overlay_opacity_percent: int,
    overlay_show_source: bool,
    overlay_alignment: str,
    resource_policy: str,
    asr_model_provider: str,
    model_lock: bool,
    delivery_mode: str,
    cloud_provider: str,
):
    file_path = _upload_path(test_file)
    validation = architecture_runtime_validation_text(
        source, vad, asr, streaming, translation, overlay,
        language, agreement_passes, ui_mode,
    )
    stop_overlay_preview()
    _save_ui_pref(
        oa_game=str(game or "DAILY_MEDIA"),
        oa_language=str(language or "auto"),
        oa_resource_policy=str(resource_policy or "normal"),
        oa_asr_model_provider=normalize_asr_model_provider(asr_model_provider),
        oa_delivery_mode=str(delivery_mode or "offline"),
        oa_cloud_provider=str(cloud_provider or "azure"),
        oa_overlay_mode=str(overlay_mode or "adaptive"),
        oa_overlay_width_percent=int(overlay_width_percent or 92),
        oa_overlay_height_px=int(overlay_height_px or 190),
        oa_overlay_font_size=int(overlay_font_size or 15),
        oa_overlay_opacity_percent=int(overlay_opacity_percent or 91),
        oa_overlay_show_source=bool(overlay_show_source),
        oa_overlay_alignment=str(overlay_alignment or "left"),
    )
    status, log, msg, notice = architecture_start_audio(
        game,
        input_mode,
        device_index,
        language,
        audio_mode,
        profile,
        file_path,
        source,
        vad,
        asr,
        streaming,
        translation,
        overlay,
        agreement_passes,
        language_correction,
        language_lock,
        preset_id,
        overlay_mode,
        overlay_width_percent,
        overlay_height_px,
        overlay_font_size,
        overlay_opacity_percent,
        overlay_show_source,
        overlay_alignment,
        resource_policy,
        normalize_asr_model_provider(asr_model_provider),
        bool(model_lock),
        str(delivery_mode or "offline"),
        str(cloud_provider or "azure"),
    )
    err_md = ""
    if "ERROR" in str(status or "").upper():
        err_md = f"**Audio Lab Error:**\n\n```\n{msg}\n```"
    if notice:
        validation += "\n\n> " + str(notice)
    return (
        _status_html(status),
        audio_runtime_status_text(profile, audio_mode, "local", "live_media"),
        log,
        msg,
        err_md,
        validation,
        False,
        gr.update(value="Preview"),
    )


def _oa_stop_audio_ui(profile: str, audio_mode: str):
    status, log, msg, notice = stop_model()
    note = "### Sesi Audio Lab dihentikan\nPipeline produksi tetap tidak berubah."
    if notice:
        note += "\n\n> " + str(notice)
    return (
        _status_html(status),
        audio_runtime_status_text(profile, audio_mode, "local", "live_media"),
        log,
        msg,
        "",
        note,
    )


def _oa_refresh_runtime_ui(profile: str, audio_mode: str):
    status, log, err, notice = refresh_state()
    err_md = f"**Error terakhir:**\n\n```\n{err}\n```" if err else ""
    note = "### Status Audio Lab diperbarui"
    if notice:
        note += "\n\n> " + str(notice)
    return (
        _status_html(status),
        audio_runtime_status_text(profile, audio_mode, "local", "live_media"),
        log,
        err or "",
        err_md,
        note,
    )


def _oa_setup_audio_runtime_ui(
    audio_mode: str,
    profile: str,
    source: str,
    vad: str,
    asr: str,
    streaming: str,
    translation: str,
    overlay: str,
    language: str,
    agreement_passes: int,
    ui_mode: str,
):
    setup_log = setup_audio_runtime_text(profile, audio_mode)
    choices, default, message = audio_devices_for_ui(True, audio_mode, "local")
    validation = architecture_runtime_validation_text(
        source, vad, asr, streaming, translation, overlay,
        language, agreement_passes, ui_mode,
    )
    return setup_log, gr.update(choices=choices, value=default), message, validation


def _oa_refresh_audio_devices_ui(audio_mode: str):
    choices, default, message = audio_devices_for_ui(True, audio_mode, "local")
    return gr.update(choices=choices, value=default), message

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
INITIAL_UI_MODE = _normalize_ui_mode(PREFS.get("ui_mode", "recommended"))
_INITIAL_VIS = _ui_mode_visibility(INITIAL_UI_MODE)
INITIAL_TRANSLATION_SOURCE = str(PREFS.get("translation_source", "ocr") or "ocr").lower()
if INITIAL_TRANSLATION_SOURCE not in {"ocr", "audio"}:
    INITIAL_TRANSLATION_SOURCE = "ocr"
INITIAL_AUDIO_INPUT = str(PREFS.get("audio_input_mode", "loopback") or "loopback").lower()
if INITIAL_AUDIO_INPUT not in {"loopback", "file"}:
    INITIAL_AUDIO_INPUT = "loopback"
INITIAL_AUDIO_PROCESSING = str(PREFS.get("audio_processing", "vad") or "vad").lower()
if INITIAL_AUDIO_PROCESSING not in {"normal", "vad"}:
    INITIAL_AUDIO_PROCESSING = "vad"
INITIAL_AUDIO_PROFILE = str(PREFS.get("audio_profile", "normal") or "normal").lower()
if INITIAL_AUDIO_PROFILE not in {"speed", "normal", "accurate"}:
    INITIAL_AUDIO_PROFILE = "normal"
INITIAL_AUDIO_LANGUAGE = str(PREFS.get("audio_language", "auto") or "auto").lower()
if str(PREFS.get("game", "")).upper() == "GFL2_EXILIUM" and INITIAL_AUDIO_LANGUAGE in {"auto", "auto_detect", ""}:
    INITIAL_AUDIO_LANGUAGE = "ja"
INITIAL_AUDIO_LANGUAGE_CORRECTION = str(PREFS.get("audio_language_correction", "balanced") or "balanced").lower()
if INITIAL_AUDIO_LANGUAGE_CORRECTION not in {"off", "conservative", "balanced", "aggressive"}:
    INITIAL_AUDIO_LANGUAGE_CORRECTION = "balanced"
INITIAL_AUDIO_LANGUAGE_LOCK = bool(PREFS.get("audio_language_lock", False))
INITIAL_AUDIO_MODE = str(PREFS.get("audio_mode", "hybrid") or "hybrid").lower()
if INITIAL_AUDIO_MODE not in {"cpu", "gpu", "hybrid"}:
    INITIAL_AUDIO_MODE = "hybrid"
INITIAL_AUDIO_USAGE = str(PREFS.get("audio_usage", "live_media") or "live_media").lower()
if INITIAL_AUDIO_USAGE not in {"live_media", "conversation"}:
    INITIAL_AUDIO_USAGE = "live_media"
INITIAL_AUDIO_ENGINE = str(PREFS.get("audio_engine", "azure_fallback") or "azure_fallback").lower()
if INITIAL_AUDIO_ENGINE not in {"local", "azure", "azure_fallback"}:
    INITIAL_AUDIO_ENGINE = "azure_fallback"
INITIAL_CLOUD_CONFIG = audio_cloud_config_values()
INITIAL_AZURE_REGION = str(INITIAL_CLOUD_CONFIG.get("region") or "")
_AUDIO_DEVICE_CHOICES, _AUDIO_DEVICE_DEFAULT, _AUDIO_DEVICE_MESSAGE = audio_devices_for_ui(False, INITIAL_AUDIO_MODE, INITIAL_AUDIO_ENGINE)
_saved_audio_device = str(PREFS.get("audio_device_index", _AUDIO_DEVICE_DEFAULT) or _AUDIO_DEVICE_DEFAULT)
_available_audio_values = {str(value) for _, value in _AUDIO_DEVICE_CHOICES}
INITIAL_AUDIO_DEVICE = _saved_audio_device if _saved_audio_device in _available_audio_values else _AUDIO_DEVICE_DEFAULT

_OA_PRESET_CHOICES = architecture_preset_choices()
_OA_INITIAL = architecture_apply_preset("japanese_live_lab")
_OA_SOURCE_CHOICES = architecture_provider_choices("source")
_OA_VAD_CHOICES = architecture_provider_choices("vad")
_OA_ASR_CHOICES = architecture_provider_choices("asr")
_OA_STREAMING_CHOICES = architecture_provider_choices("streaming")
_OA_TRANSLATION_CHOICES = architecture_provider_choices("translation")
_OA_OVERLAY_CHOICES = architecture_provider_choices("overlay")
INITIAL_OA_UI_MODE = "developer" if str(PREFS.get("oa_ui_mode", "normal")).lower() in {"developer", "expert"} else "normal"
INITIAL_OA_OVERLAY_MODE = str(PREFS.get("oa_overlay_mode", "adaptive") or "adaptive").lower()
if INITIAL_OA_OVERLAY_MODE not in {"adaptive", "fixed", "custom"}:
    INITIAL_OA_OVERLAY_MODE = "adaptive"
INITIAL_OA_RESOURCE_POLICY = str(PREFS.get("oa_resource_policy", "normal") or "normal").lower()
if INITIAL_OA_RESOURCE_POLICY not in {"efficient", "normal", "optimal"}:
    INITIAL_OA_RESOURCE_POLICY = "normal"
INITIAL_OA_ASR_MODEL_PROVIDER = normalize_asr_model_provider(PREFS.get("oa_asr_model_provider", PROVIDER_KOTOBA))
INITIAL_OA_DELIVERY_MODE = str(PREFS.get("oa_delivery_mode", "offline") or "offline").lower()
if INITIAL_OA_DELIVERY_MODE not in {"offline", "online", "hybrid"}:
    INITIAL_OA_DELIVERY_MODE = "offline"
INITIAL_OA_CLOUD_PROVIDER = str(PREFS.get("oa_cloud_provider", "azure") or "azure").lower()
if INITIAL_OA_CLOUD_PROVIDER not in {"azure", "google", "aws"}:
    INITIAL_OA_CLOUD_PROVIDER = "azure"
OA_ASR_MODEL_CHOICES = asr_model_provider_choices(include_auto=False)
INITIAL_OA_GAME = str(PREFS.get("oa_game", PREFS.get("game", "GFL2_EXILIUM")) or "GFL2_EXILIUM").upper()
if INITIAL_OA_GAME not in OA_LANGUAGE_CHOICES:
    INITIAL_OA_GAME = "CUSTOM"
INITIAL_OA_LANGUAGE_CHOICES = OA_LANGUAGE_CHOICES[INITIAL_OA_GAME]
INITIAL_OA_LANGUAGE_VALUES = {value for _label, value in INITIAL_OA_LANGUAGE_CHOICES}
INITIAL_OA_LANGUAGE = str(PREFS.get("oa_language", "ja_specialist") or "ja_specialist").lower()
if INITIAL_OA_LANGUAGE not in INITIAL_OA_LANGUAGE_VALUES:
    INITIAL_OA_LANGUAGE = INITIAL_OA_LANGUAGE_CHOICES[0][1]
_OA_INITIAL_RUNTIME_STATUS = architecture_runtime_validation_text(
    _OA_INITIAL[0], _OA_INITIAL[1], _OA_INITIAL[2], _OA_INITIAL[3], _OA_INITIAL[4], _OA_INITIAL[5],
    INITIAL_OA_LANGUAGE, 2, INITIAL_OA_UI_MODE,
)

with gr.Blocks(title=APP_DISPLAY_NAME) as demo:
    gr.HTML(
        f"<div class='hero'><div class='hero-topline'>"
        f"<span class='release-badge'>{APP_VERSION_TAG}</span>"
        "<span class='release-channel'>Original Pipeline · Open Architecture Lab</span>"
        f"</div><h1>{APP_DISPLAY_NAME}</h1>"
        f"<p class='hero-subtitle'>{RELEASE_NAME}. Pilih sumber terjemahan, game, dan tingkat tampilan; "
        "pengaturan lanjutan hanya muncul ketika benar-benar dibutuhkan.</p></div>"
    )
    with gr.Row():
        with gr.Column(scale=11):
            candidate_notice = gr.HTML("")
        with gr.Column(scale=1, elem_id="exit_btn"):
            exit_btn = gr.Button("Exit", variant="stop")

    with gr.Tabs():
        with gr.Tab("Mulai"):
            with gr.Group(elem_classes=["workspace-card"]):
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Persiapan</div><div class='section-title'>Atur sesi penerjemahan</div><div class='section-copy'>Pilih game dan sudut pandang. Normal menjaga halaman tetap ringkas; Developer menampilkan seluruh parameter pembangunan, runtime, dan diagnostik.</div></div><span class='step-badge'>1</span></div>")
                with gr.Row():
                    game_dropdown = gr.Dropdown(label="Game", choices=GAME_CHOICES, value=PREFS.get("game", "GFL2_EXILIUM"))
                    ui_mode = gr.Radio(label="Tingkat tampilan", choices=[("Normal", "recommended"), ("Developer", "developer")], value=INITIAL_UI_MODE, elem_id="ui_level")
                    settings_mode = gr.Radio(label="Konfigurasi", choices=[("Otomatis", "recommended"), ("Manual", "manual")], value=PREFS.get("settings_mode", "recommended"))
                gr.HTML("<div class='smallnote'><b>Otomatis</b> memakai profil aman sesuai game. <b>Manual</b> mempertahankan pilihan model, engine, interval, dan resolusi OCR Anda.</div>")

            with gr.Group(elem_classes=["source-stage"]):
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Sumber terjemahan</div><div class='section-title'>Pilih cara ORT membaca dialog</div><div class='section-copy'>OCR dan Audio dirancang saling eksklusif agar satu overlay tidak menerima dua hasil yang bertabrakan.</div></div><span class='step-badge'>2</span></div>")
                translation_source = gr.Radio(
                    label="Sumber aktif",
                    choices=[("OCR · Siap", "ocr"), ("Audio · Live Media/Local", "audio")],
                    value=INITIAL_TRANSLATION_SOURCE,
                    elem_id="translation_source",
                )
                source_status = gr.HTML(_translation_source_status_html(INITIAL_TRANSLATION_SOURCE, INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE, INITIAL_AUDIO_ENGINE, INITIAL_AUDIO_USAGE))

            guided_header_panel = gr.HTML(
                "<div class='guided-banner'><b>Alur cepat:</b><span>pilih OCR atau Audio → gunakan pengaturan bawaan → tekan tombol Mulai yang sesuai. Panel teknis tetap tersimpan tetapi tidak memenuhi layar.</span></div>",
                visible=_INITIAL_VIS["guided_header"],
            )
            developer_header_panel = gr.HTML(
                "<div class='developer-banner'><span class='developer-tag'>Developer workspace</span><b>Kontrol profesional aktif.</b><span>Model, capture, OCR, engine, policy, runtime, hardware, dan diagnostic tersedia dalam satu workspace.</span></div>",
                visible=_INITIAL_VIS["developer_header"],
            )

            with gr.Row():
                with gr.Column(scale=3):
                    with gr.Group(visible=INITIAL_TRANSLATION_SOURCE == "ocr", elem_classes=["transition-panel"]) as ocr_runtime_panel:
                        gr.HTML("<div class='setup-header'><div><div class='section-kicker'>OCR workspace</div><div class='section-title'>Konfigurasi pembacaan layar</div></div><span class='step-badge'>3</span></div>")
                        game_profile_card = gr.HTML(profile_html(PREFS.get("game", "GFL2_EXILIUM"), _settings_mode_is_manual(PREFS.get("settings_mode", "recommended"))))
                        with gr.Accordion("Rekomendasi sistem", open=False, visible=_INITIAL_VIS["recommendation"]) as recommendation_panel:
                            gr.HTML("<div class='pro-hint'>Alasan pemilihan model, Safe Game, Fast, CPU/GPU, resolusi OCR, dan interval.</div>")
                            recommendation_box = gr.Textbox(label="Rekomendasi", value=recommendation_text(PREFS.get("game", "GFL2_EXILIUM"), _settings_mode_is_manual(PREFS.get("settings_mode", "recommended"))), interactive=False, lines=11, elem_classes=["mono"])
                            apply_rec_btn = gr.Button("Terapkan rekomendasi", variant="secondary")
                        with gr.Accordion("Diagnostic dashboard", open=False, visible=_INITIAL_VIS["diagnostic"]) as dashboard_diagnostic_panel:
                            gr.HTML("<div class='pro-hint'>Strategy, core bridge, runtime action, cache, Online Assist, Fast engine, dan session log.</div>")
                            diagnostic_box = gr.Textbox(label="Diagnostic", value=diagnostic_text(), interactive=False, lines=16, elem_classes=["mono"])
                            refresh_diag_btn = gr.Button("Refresh diagnostic")
                        with gr.Group(visible=_INITIAL_VIS["model_controls"]) as model_controls_panel:
                            with gr.Row():
                                model_group = gr.Radio(label="Keluarga model", choices=group_choices(), value=initial_group)
                                model_dropdown = gr.Dropdown(label="Model", choices=basic_choices, value=default_model)
                            model_default_msg = gr.HTML(model_user_preset_badge_html(default_model))
                            reset_model_default_btn = gr.Button("Reset default model", elem_id="reset_model_default_btn", visible=model_user_preset_is_modified(default_model))
                            with gr.Accordion("Detail model terpilih", open=False):
                                model_md = gr.Markdown(_model_desc(default_model))
                            with gr.Group(visible=_INITIAL_VIS["advanced_controls"], elem_classes=["developer-controls", "transition-panel"]) as advanced_controls_panel:
                                gr.HTML(f"<div class='section-kicker'>Advanced OCR controls · {APP_VERSION_TAG}</div><div class='smallnote'>Perubahan Mode / Engine / Interval / OCR disimpan otomatis per model. Badge <b style='color:#fb923c'>• Modification</b> menandai override dari default bawaan.</div>")
                                mode_buffer_checkbox = gr.Checkbox(label="Mode Buffer", value=bool(PREFS.get("mode_buffer_enabled", False)))
                                gr.HTML("<div class='mode-buffer-help' title='Mode Buffer menambahkan jeda kecil terkontrol agar final terjemahan lebih lengkap/stabil saat rekaman. Default OFF.'><b>Mode Buffer</b><span class='q'>?</span><div class='tip'>Menambahkan buffer kecil terkontrol untuk membantu hasil story lebih lengkap. Opsi ini dapat menambah sedikit latensi dan tetap OFF secara default.</div></div>")
                                with gr.Row():
                                    mode_dropdown = gr.Dropdown(label="Strategi capture", choices=[("Auto / Story Otomatis", "auto"), ("Freeze Manual / Klik User", "freeze"), ("Interval / Freeze Otomatis", "interval")], value=_initial_model_preset.get("mode", PREFS.get("mode", "auto")))
                                    engine_dropdown = gr.Dropdown(label="Engine OCR / Terjemahan", choices=[("CPU", "cpu"), ("GPU", "gpu"), ("Hybrid", "hybrid")], value=_initial_model_preset.get("engine", PREFS.get("engine", "hybrid")))
                                responsive_story_mode = gr.Checkbox(label="Responsive Story / Dialog Cepat", value=bool(PREFS.get("responsive_story_mode", False)))
                                gr.Markdown(f"Memprioritaskan dialog terbaru, membuang hasil generasi lama, dan mempertahankan overlay sampai hasil baru siap pada {APP_VERSION_TAG}.")
                                with gr.Row():
                                    interval_slider = gr.Slider(label="Interval capture (ms)", minimum=45, maximum=1200, step=5, value=max(45, int(_initial_model_preset.get("interval_ms", PREFS.get("interval_ms", 160)))))
                                    ocr_resolution_slider = gr.Slider(label="Resolusi OCR (%)", minimum=5, maximum=100, step=5, value=int(_initial_model_preset.get("ocr_resolution", PREFS.get("ocr_resolution", 65))))
                                with gr.Accordion("Profil diagnostic A/B", open=False):
                                    diagnostic_profile = gr.Dropdown(label="Profil uji", choices=[("Baseline Correctness", "baseline"), ("Responsive Story", "responsive_story"), ("Diagnostic No-Name-ROI", "diagnostic_no_name_roi")], value=str(PREFS.get("diagnostic_profile", "baseline")))
                                    gr.Markdown("**Peringatan:** No-Name-ROI hanya untuk pengukuran performa; label KSVK/Helen/Helena dapat hilang atau salah.")
                                gr.HTML("<div class='mode-guide'><b>Strategi capture:</b> Auto mengikuti teks dialog progresif; Freeze memproses klik manual; Interval mengambil snapshot otomatis dengan jeda tetap.</div>")
                        performance_policy_info = gr.Markdown("**Performance policy:** Fast CT2 dipertahankan ketika aktif; OCR ultra-rendah tidak direkomendasikan untuk story. Status card membedakan requested dan effective settings.", visible=_INITIAL_VIS["policy"])

                    with gr.Group(visible=INITIAL_TRANSLATION_SOURCE == "audio", elem_classes=["audio-preview", "transition-panel"]) as audio_preview_panel:
                        gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Audio workspace</div><div class='section-title'>Real-Time Video Translation</div><div class='section-copy'>Audio video/game dikirim sebagai aliran satu arah per 20 ms. Azure maupun Local Live memperbarui subtitle selama karakter masih berbicara; jeda hanya mengunci final dan tidak lagi memulai proses terjemahan.</div></div><span class='step-badge'>3</span></div>")
                        audio_availability = gr.HTML(_translation_source_status_html("audio", INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE, INITIAL_AUDIO_ENGINE, INITIAL_AUDIO_USAGE))
                        with gr.Row():
                            audio_usage = gr.Radio(
                                label="Jenis penggunaan",
                                choices=[("Live Media · Rekomendasi", "live_media"), ("Conversation", "conversation")],
                                value=INITIAL_AUDIO_USAGE,
                            )
                            audio_engine = gr.Radio(
                                label="Mesin Audio",
                                choices=[("Local Live · Rolling partial/offline", "local"), ("Azure Cloud · Streaming", "azure"), ("Azure + Local Live Fallback · Rekomendasi", "azure_fallback")],
                                value=INITIAL_AUDIO_ENGINE,
                            )
                        audio_mode = gr.Radio(
                            label="Perangkat ASR lokal / fallback",
                            choices=[("CPU · Kompatibel", "cpu"), ("GPU · ASR CUDA ketat", "gpu"), ("Hybrid · Rekomendasi", "hybrid")],
                            value=INITIAL_AUDIO_MODE,
                        )
                        with gr.Row():
                            audio_input_mode = gr.Radio(
                                label="Sumber audio",
                                choices=[("Audio internal (WASAPI)", "loopback"), ("File audio uji", "file")],
                                value=INITIAL_AUDIO_INPUT,
                            )
                            audio_device = gr.Dropdown(
                                label="Perangkat output / loopback",
                                choices=_AUDIO_DEVICE_CHOICES,
                                value=INITIAL_AUDIO_DEVICE,
                                interactive=INITIAL_AUDIO_INPUT != "file",
                            )
                        audio_test_file = gr.File(
                            label="File audio uji (WAV, MP3, M4A, MKV, atau MP4)",
                            file_types=["audio", "video"],
                            type="filepath",
                            visible=INITIAL_AUDIO_INPUT == "file",
                        )
                        with gr.Row():
                            audio_language = gr.Dropdown(
                                label="Bahasa utama awal",
                                choices=[("Smart Auto · Rekomendasi", "auto"), ("English", "en"), ("Japanese · Multilingual", "ja"), ("Japanese Specialist · Kotoba", "ja_specialist"), ("Chinese", "zh"), ("Korean", "ko")],
                                value=INITIAL_AUDIO_LANGUAGE,
                            )
                            audio_processing = gr.Radio(
                                label="Pemrosesan lokal/fallback",
                                choices=[("Normal", "normal"), ("VAD · Rekomendasi", "vad")],
                                value=INITIAL_AUDIO_PROCESSING,
                            )
                        with gr.Row():
                            audio_language_correction = gr.Dropdown(
                                label="Auto-Correct bahasa",
                                choices=[
                                    ("Nonaktif", "off"),
                                    ("Conservative · 12 detik", "conservative"),
                                    ("Balanced · 8 detik · Rekomendasi", "balanced"),
                                    ("Aggressive · 5 detik", "aggressive"),
                                ],
                                value=INITIAL_AUDIO_LANGUAGE_CORRECTION,
                            )
                            audio_language_lock = gr.Checkbox(
                                label="Kunci bahasa utama (code-switch sementara tetap dideteksi)",
                                value=INITIAL_AUDIO_LANGUAGE_LOCK,
                            )
                        audio_profile = gr.Radio(
                            label="Respons subtitle / profil fallback",
                            choices=[("Instant · Paling real-time", "speed"), ("Balanced · Rekomendasi", "normal"), ("Accurate · Jeda lebih longgar", "accurate")],
                            value=INITIAL_AUDIO_PROFILE,
                        )
                        audio_profile_info = gr.Markdown(_audio_profile_description(INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE))
                        gr.HTML("<div class='audio-flow-grid'><div class='audio-flow-item'><b>20 ms Live Stream</b><small>Audio diproses terus-menerus dan hasil Indonesia diperbarui selama ucapan berlangsung.</small></div><div class='audio-flow-item'><b>Safe Auto-Correct</b><small>Balanced memerlukan bukti dominan sekitar 8 detik; dialog asing pendek diperlakukan sebagai code-switch tanpa mengganti bahasa utama.</small></div><div class='audio-flow-item'><b>Japanese Specialist</b><small>Kotoba dipertahankan saat GPU gagal dengan memuat model yang sama di CPU. Output berulang atau bridge Jepang yang gagal diblokir sebelum overlay.</small></div></div>")
                        with gr.Accordion("Azure Speech · setup & kredensial", open=INITIAL_AUDIO_ENGINE != "local"):
                            gr.Markdown("Audio akan dikirim ke Microsoft Azure dan dapat menimbulkan biaya layanan. API key disimpan melalui Windows Credential Manager, tidak di dalam proyek, ZIP, atau log.")
                            with gr.Row():
                                azure_region = gr.Textbox(label="Azure Speech region", value=INITIAL_AZURE_REGION, placeholder="contoh: southeastasia")
                                azure_api_key = gr.Textbox(label="Azure Speech API key", value="", type="password", placeholder="kosongkan jika sudah tersimpan")
                            with gr.Row():
                                setup_cloud_btn = gr.Button("Siapkan Runtime Azure", variant="secondary")
                                save_test_cloud_btn = gr.Button("Simpan & Uji Azure", variant="primary")
                                clear_cloud_btn = gr.Button("Hapus Kredensial Azure", variant="stop")
                            cloud_setup_log = gr.Textbox(label="Status Azure", value=audio_cloud_runtime_status_text(), interactive=False, lines=12, elem_classes=["mono"])
                        with gr.Row():
                            setup_audio_btn = gr.Button(
                                f"Siapkan Audio {INITIAL_AUDIO_MODE.upper()}" if INITIAL_AUDIO_ENGINE == "local" else f"Siapkan Fallback Lokal {INITIAL_AUDIO_MODE.upper()}",
                                variant="secondary",
                            )
                            refresh_audio_devices_btn = gr.Button("Deteksi ulang perangkat")
                        audio_device_message = gr.Textbox(label="Deteksi perangkat", value=_AUDIO_DEVICE_MESSAGE, interactive=False, lines=2)
                        with gr.Accordion("Setup & diagnostic Audio lengkap", open=False):
                            audio_setup_log = gr.Textbox(label="Setup Audio", value=audio_runtime_status_text(INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE, INITIAL_AUDIO_ENGINE, INITIAL_AUDIO_USAGE), interactive=False, lines=16, elem_classes=["mono"])

                    with gr.Row(elem_classes=["action-row"]):
                        start_btn = gr.Button("Mulai OCR", variant="primary", visible=INITIAL_TRANSLATION_SOURCE == "ocr", elem_id="start_primary")
                        audio_start_btn = gr.Button("Mulai Audio", variant="primary", visible=INITIAL_TRANSLATION_SOURCE == "audio", elem_id="audio_start_primary")
                        refresh_btn = gr.Button("Refresh status")
                        stop_btn = gr.Button("Stop", variant="stop")
                    launch_msg = gr.Textbox(label="Status sesi", interactive=False)

                with gr.Column(scale=2):
                    with gr.Group(elem_classes=["workspace-card"]):
                        gr.HTML("<div class='section-kicker'>Runtime monitor</div><div class='section-title'>Status aktif</div>")
                        state_box = gr.HTML(_status_html("STATUS: IDLE"))
                        runtime_status_cards = gr.HTML(runtime_effective_status_html())
                        with gr.Accordion("Runtime ringkas", open=False, visible=_INITIAL_VIS["runtime_summary"]) as runtime_summary_panel:
                            runtime_box = gr.Textbox(label="Runtime summary", value=runtime_summary_text(), interactive=False, lines=6, elem_classes=["mono"])
                        with gr.Accordion("Spesifikasi perangkat", open=False, visible=_INITIAL_VIS["hardware"]) as hardware_panel:
                            hardware_box = gr.Textbox(label="Hardware", value=hardware_summary_text(), interactive=False, lines=8, elem_classes=["mono"])
                        error_box = gr.Markdown("")

            with gr.Accordion("Aktivitas, Live Log & AI Recap", open=INITIAL_UI_MODE == "developer", elem_classes=["log-accordion"]):
                with gr.Row():
                    gr.HTML("""
                    <div class='copylog-wrap'>
                      <button onclick="(function(){const ta=document.querySelector('#live_log textarea'); if(ta){navigator.clipboard.writeText(ta.value); const s=document.getElementById('copylog_status'); if(s){s.textContent='Live log tersalin'; setTimeout(()=>s.textContent='',1500);}}})()">Copy Live Log</button>
                      <span id='copylog_status'></span>
                    </div>
                    """)
                    prompt_btn = gr.Button("Buat prompt recap")
                    reset_live_log_btn = gr.Button("Reset live log")
                    analyze_session_btn = gr.Button("Analyze last session")
                log_box = gr.Textbox(label="Live log", lines=16, interactive=False, autoscroll=True, elem_classes=["logbox"], elem_id="live_log")
                ai_prompt_box = gr.Textbox(label="Prompt AI Recap", value="", interactive=False, lines=10, elem_classes=["mono"], elem_id="ai_prompt_box")
                session_report_box = gr.Textbox(label="Analisis sesi / rekomendasi performa", value="", interactive=False, lines=9, elem_classes=["mono"])
                gr.HTML("""
                <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:8px'>
                  <button class='ai-copy-btn' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||''); const s=document.getElementById('aicopy_status'); if(s){s.textContent='Prompt tersalin'; setTimeout(()=>s.textContent='',1500);}}})()">Copy Prompt</button>
                  <button class='ai-link ai-chatgpt' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||'');} window.open('https://chat.openai.com/','_blank');})()">Copy + Buka ChatGPT</button>
                  <button class='ai-link ai-gemini' onclick="(function(){const ta=document.querySelector('#ai_prompt_box textarea'); if(ta){navigator.clipboard.writeText(ta.value||'');} window.open('https://gemini.google.com/','_blank');})()">Copy + Buka Gemini</button>
                  <span id='aicopy_status' style='color:#a7f3d0;align-self:center'></span>
                </div>
                """)
            with gr.Accordion("Catatan rilis dan kompatibilitas", open=False):
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
                gr.Markdown("### Observed Story / Alias Review — data v8.9.1")
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

        with gr.Tab("Open Architecture Lab"):
            gr.HTML(
                "<div class='oa-lab-banner'><h2>ORT Open Architecture Lab</h2>"
                "<p>Lingkungan eksperimen terisolasi untuk menjalankan dan membandingkan pipeline Audio Lab. "
                "Normal Mode menyediakan alur sederhana; Developer Mode membuka provider, kontrak runtime, A/B, JSON, dan diagnostik. "
                "Satu ProcessManager tetap mencegah pipeline produksi dan Lab berjalan bersamaan.</p></div>"
            )

            with gr.Group(elem_classes=["workspace-card"]):
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Tampilan Lab</div><div class='section-title'>Pilih sudut pandang penggunaan</div><div class='section-copy'>Normal untuk penggunaan sehari-hari. Developer untuk pembangunan provider, pengujian, dan diagnosis.</div></div><span class='step-badge'>1</span></div>")
                oa_ui_mode = gr.Radio(
                    label="Mode tampilan Lab",
                    choices=[("Normal", "normal"), ("Developer", "developer")],
                    value=INITIAL_OA_UI_MODE,
                )
                oa_mode_help = gr.HTML(
                    "<div class='developer-banner'><span class='developer-tag'>Developer workspace</span><b>Seluruh kontrak pipeline dan diagnostik ditampilkan.</b><span>Gunakan mode ini saat membangun provider, memeriksa ID internal, A/B test, JSON plan, dan log runtime.</span></div>"
                    if INITIAL_OA_UI_MODE == "developer"
                    else "<div class='guided-banner'><b>Normal Mode:</b><span>pilih preset → periksa status siap → tekan Mulai Audio Lab. Detail provider disembunyikan agar alur tetap konsisten.</span></div>"
                )

            with gr.Group(elem_classes=["workspace-card"]):
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Preset Lab</div><div class='section-title'>Pilih pipeline yang akan diuji</div><div class='section-copy'>Japanese Live Lab adalah preset eksperimen pertama yang dapat dijalankan langsung untuk anime atau game Jepang.</div></div><span class='step-badge'>2</span></div>")
                with gr.Row():
                    oa_preset = gr.Dropdown(
                        label="Preset arsitektur",
                        choices=_OA_PRESET_CHOICES,
                        value="japanese_live_lab",
                    )
                    oa_apply_preset_btn = gr.Button("Terapkan ulang preset", variant="secondary")
                    oa_refresh_btn = gr.Button("Validasi provider")

            with gr.Group(elem_classes=["workspace-card"]):
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Audio Lab runtime</div><div class='section-title'>Atur sesi dan mulai terjemahan</div><div class='section-copy'>Urutannya selalu sama: pilih sumber → atur box → validasi → Preload & Mulai Audio Lab. Segmentasi adaptif memisahkan jeda panjang dan menggulir subtitle saat monolog terlalu panjang.</div></div><span class='step-badge'>3</span></div>")
                oa_preview_active = gr.State(False)
                with gr.Row():
                    oa_lab_game = gr.Dropdown(
                        label="Game / profil",
                        choices=OA_GAME_CHOICES,
                        value=INITIAL_OA_GAME,
                    )
                    oa_overlay_mode = gr.Radio(
                        label="Mode box terjemahan",
                        choices=[
                            ("Adaptif · mengikuti teks", "adaptive"),
                            ("Fix · ukuran tetap mengikuti monitor", "fixed"),
                            ("Custom · ukuran dan layout bebas", "custom"),
                        ],
                        value=INITIAL_OA_OVERLAY_MODE,
                    )
                    oa_preview_btn = gr.Button("Preview", variant="secondary")
                oa_preview_status = gr.Markdown("Preview belum aktif")
                oa_profile_language_note = gr.Markdown(
                    _oa_game_profile_updates(INITIAL_OA_GAME, INITIAL_OA_LANGUAGE)[1]
                )
                gr.Markdown("**Mesin terjemahan Audio Lab:** ORTCore Fast V2 dipilih otomatis oleh route arsitektur. Daftar model OCR tidak lagi digunakan pada halaman ini.")
                with gr.Group(visible=INITIAL_OA_OVERLAY_MODE in {"fixed", "custom"}) as oa_overlay_size_panel:
                    with gr.Row():
                        oa_overlay_width = gr.Slider(
                            label="Lebar box terhadap monitor (%)",
                            minimum=40,
                            maximum=100,
                            step=1,
                            value=int(PREFS.get("oa_overlay_width_percent", 92)),
                        )
                        oa_overlay_height = gr.Slider(
                            label="Tinggi box tetap (px)",
                            minimum=110,
                            maximum=420,
                            step=5,
                            value=int(PREFS.get("oa_overlay_height_px", 190)),
                        )
                        oa_overlay_opacity = gr.Slider(
                            label="Opacity box (%)",
                            minimum=45,
                            maximum=100,
                            step=1,
                            value=int(PREFS.get("oa_overlay_opacity_percent", 91)),
                        )
                with gr.Group(visible=INITIAL_OA_OVERLAY_MODE == "custom") as oa_overlay_custom_panel:
                    with gr.Row():
                        oa_overlay_font = gr.Slider(
                            label="Ukuran font terjemahan",
                            minimum=10,
                            maximum=30,
                            step=1,
                            value=int(PREFS.get("oa_overlay_font_size", 15)),
                        )
                        oa_overlay_alignment = gr.Radio(
                            label="Perataan teks",
                            choices=[("Kiri", "left"), ("Tengah", "center")],
                            value=str(PREFS.get("oa_overlay_alignment", "left")),
                        )
                        oa_overlay_show_source = gr.Checkbox(
                            label="Tampilkan preview Inggris",
                            value=bool(PREFS.get("oa_overlay_show_source", True)),
                        )
                with gr.Row():
                    oa_lab_input_mode = gr.Radio(
                        label="Sumber audio",
                        choices=[("Audio internal (WASAPI)", "loopback"), ("File WAV uji", "file")],
                        value=INITIAL_AUDIO_INPUT,
                    )
                    oa_lab_device = gr.Dropdown(
                        label="Perangkat output / loopback",
                        choices=_AUDIO_DEVICE_CHOICES,
                        value=INITIAL_AUDIO_DEVICE,
                        interactive=INITIAL_AUDIO_INPUT != "file",
                    )
                oa_lab_test_file = gr.File(
                    label="Replay file Lab (WAV PCM 16-bit)",
                    file_types=["audio"],
                    type="filepath",
                    visible=INITIAL_AUDIO_INPUT == "file",
                )
                with gr.Row():
                    oa_lab_language = gr.Dropdown(
                        label="Bahasa utama",
                        choices=INITIAL_OA_LANGUAGE_CHOICES,
                        value=INITIAL_OA_LANGUAGE,
                    )
                    oa_lab_audio_mode = gr.Radio(
                        label="Perangkat ASR",
                        choices=[("CPU", "cpu"), ("GPU", "gpu"), ("Hybrid", "hybrid")],
                        value=INITIAL_AUDIO_MODE,
                    )
                    oa_resource_policy = gr.Radio(
                        label="Kebijakan resource",
                        choices=[
                            ("Efficient", "efficient"),
                            ("Normal · Stabil", "normal"),
                            ("Optimal · Adaptif", "optimal"),
                        ],
                        value=INITIAL_OA_RESOURCE_POLICY,
                    )
                oa_resource_note = gr.Markdown(_oa_resource_policy_updates(INITIAL_OA_RESOURCE_POLICY))
                with gr.Row():
                    oa_asr_model_provider = gr.Dropdown(
                        label="Model ASR Jepang · hard lock",
                        choices=OA_ASR_MODEL_CHOICES,
                        value=INITIAL_OA_ASR_MODEL_PROVIDER,
                    )
                    oa_model_lock = gr.Checkbox(
                        label="Kunci model selama sesi",
                        value=True,
                        interactive=False,
                    )
                oa_provider_status = gr.HTML(
                    _oa_provider_status_ui(INITIAL_OA_ASR_MODEL_PROVIDER, INITIAL_AUDIO_MODE)
                )
                oa_setup_target = gr.Radio(
                    label="Target setup/download · wajib dipilih setiap kali",
                    choices=[("CPU", "cpu"), ("GPU", "gpu"), ("CPU + GPU", "both")],
                    value=None,
                    info="Pilihan ini hanya mengatur model/runtime yang akan dipasang. Perangkat ASR untuk sesi tetap dipilih pada pengaturan di atas.",
                )
                with gr.Row():
                    oa_setup_provider_btn = gr.Button("Siapkan model yang dipilih", variant="secondary")
                    oa_refresh_provider_btn = gr.Button("Periksa status model")
                oa_provider_progress = gr.HTML(_oa_progress_html())
                with gr.Row():
                    oa_delivery_mode = gr.Radio(
                        label="Mode delivery",
                        choices=[("Offline", "offline"), ("Online", "online"), ("Hybrid Cloud + Local", "hybrid")],
                        value=INITIAL_OA_DELIVERY_MODE,
                    )
                    oa_cloud_provider = gr.Dropdown(
                        label="Cloud provider",
                        choices=[("Azure Speech · live", "azure"), ("Google Cloud · benchmark catalog", "google"), ("AWS Transcribe · benchmark catalog", "aws")],
                        value=INITIAL_OA_CLOUD_PROVIDER,
                    )
                oa_delivery_note = gr.Markdown(
                    _oa_delivery_mode_updates(INITIAL_OA_DELIVERY_MODE, INITIAL_OA_CLOUD_PROVIDER)
                )
                oa_provider_setup_log = gr.Textbox(
                    label="Log unduhan & setup provider",
                    value="",
                    interactive=False,
                    lines=14,
                    elem_classes=["mono"],
                    info="Log ini terisi otomatis saat setup dimulai dan menunjukkan fase download, ukuran, persentase, verifikasi, keberhasilan, atau kegagalan.",
                )
                with gr.Row():
                    oa_copy_provider_log_btn = gr.Button("Salin log setup provider", visible=False)
                    oa_provider_copy_message = gr.Markdown("")
                with gr.Accordion("Provider Benchmark Lab · WAV yang sama", open=False):
                    oa_benchmark_file = gr.File(
                        label="Klip benchmark WAV PCM", file_types=["audio"], type="filepath"
                    )
                    oa_benchmark_providers = gr.CheckboxGroup(
                        label="Model yang dibandingkan",
                        choices=OA_ASR_MODEL_CHOICES,
                        value=[item[1] for item in OA_ASR_MODEL_CHOICES],
                    )
                    oa_benchmark_device = gr.Radio(
                        label="Device benchmark", choices=[("CPU", "cpu"), ("GPU", "cuda")], value="cpu"
                    )
                    oa_benchmark_btn = gr.Button("Jalankan benchmark provider")
                    oa_benchmark_output = gr.Markdown("Benchmark belum dijalankan.")
                oa_lab_profile = gr.Radio(
                    label="Respons subtitle",
                    choices=[("Instant", "speed"), ("Balanced · Rekomendasi", "normal"), ("Accurate", "accurate")],
                    value=INITIAL_AUDIO_PROFILE,
                )
                with gr.Row():
                    oa_setup_audio_btn = gr.Button("Siapkan Runtime Audio Lab", variant="secondary")
                    oa_refresh_devices_btn = gr.Button("Deteksi ulang perangkat")
                oa_device_message = gr.Textbox(
                    label="Status perangkat",
                    value=_AUDIO_DEVICE_MESSAGE,
                    interactive=False,
                    lines=2,
                )
                with gr.Accordion("Setup runtime Lab", open=False):
                    oa_audio_setup_log = gr.Textbox(
                        label="Setup Audio Lab",
                        value=audio_runtime_status_text(INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE, "local", "live_media"),
                        interactive=False,
                        lines=14,
                        elem_classes=["mono"],
                    )

                oa_runtime_validation = gr.Markdown(_OA_INITIAL_RUNTIME_STATUS)
                with gr.Row(elem_classes=["action-row"]):
                    oa_validate_runtime_btn = gr.Button("Validasi Pipeline Lab")
                    oa_start_audio_btn = gr.Button("Preload & Mulai Audio Lab", variant="primary", elem_id="oa_start_primary")
                    oa_stop_audio_btn = gr.Button("Stop Audio Lab", variant="stop")
                    oa_refresh_runtime_btn = gr.Button("Refresh Status Lab")

                oa_runtime_state = gr.HTML(_status_html("STATUS: IDLE"))
                oa_runtime_message = gr.Textbox(label="Status sesi Audio Lab", interactive=False)
                oa_runtime_error = gr.Markdown("")
                with gr.Accordion("Runtime monitor & log Lab", open=True):
                    gr.HTML("""
                    <div class='copylog-wrap'>
                      <button onclick="(function(){const ta=document.querySelector('#oa_live_log textarea'); if(ta){navigator.clipboard.writeText(ta.value); const s=document.getElementById('oa_copylog_status'); if(s){s.textContent='Log Lab tersalin'; setTimeout(()=>s.textContent='',1800);}}})()">Copy Log Lab</button>
                      <span id='oa_copylog_status'></span>
                    </div>
                    <div class='smallnote'>Log diperbarui otomatis selama sesi. Pause hanya menghentikan tampilan, bukan pencatatan ke file.</div>
                    """)
                    oa_realtime_log_enabled = gr.Checkbox(
                        label="Log realtime",
                        value=True,
                    )
                    oa_runtime_summary = gr.Textbox(
                        label="Runtime Audio Lab",
                        value=audio_runtime_status_text(INITIAL_AUDIO_PROFILE, INITIAL_AUDIO_MODE, "local", "live_media"),
                        interactive=False,
                        lines=10,
                        elem_classes=["mono"],
                    )
                    oa_runtime_log = gr.Textbox(
                        label="Live log Audio Lab",
                        value="",
                        interactive=False,
                        lines=18,
                        autoscroll=True,
                        elem_id="oa_live_log",
                        elem_classes=["logbox"],
                    )
                    oa_provider_transparency = gr.Markdown(_oa_provider_transparency_text())
                    oa_live_timer = gr.Timer(value=0.75, active=True) if hasattr(gr, "Timer") else None

            with gr.Group(
                visible=INITIAL_OA_UI_MODE == "developer",
                elem_classes=["developer-controls", "workspace-card"],
            ) as oa_developer_panel:
                gr.HTML("<div class='setup-header'><div><div class='section-kicker'>Developer contract</div><div class='section-title'>Provider dan kebijakan pipeline</div><div class='section-copy'>Panel ini adalah POV developer. User Normal tidak perlu mengubah ID provider atau membaca JSON runtime.</div></div><span class='step-badge'>DEV</span></div>")
                with gr.Row():
                    oa_source = gr.Dropdown(label="Source Provider", choices=_OA_SOURCE_CHOICES, value=_OA_INITIAL[0])
                    oa_vad = gr.Dropdown(label="VAD Provider", choices=_OA_VAD_CHOICES, value=_OA_INITIAL[1])
                    oa_asr = gr.Dropdown(label="ASR Provider", choices=_OA_ASR_CHOICES, value=_OA_INITIAL[2])
                with gr.Row():
                    oa_streaming = gr.Dropdown(label="Streaming Strategy", choices=_OA_STREAMING_CHOICES, value=_OA_INITIAL[3])
                    oa_translation = gr.Dropdown(label="Translation Route", choices=_OA_TRANSLATION_CHOICES, value=_OA_INITIAL[4])
                    oa_overlay = gr.Dropdown(label="Overlay Provider", choices=_OA_OVERLAY_CHOICES, value=_OA_INITIAL[5])
                with gr.Row():
                    oa_language_correction = gr.Dropdown(
                        label="Language watchdog",
                        choices=[
                            ("Off", "off"),
                            ("Conservative", "conservative"),
                            ("Balanced", "balanced"),
                            ("Aggressive", "aggressive"),
                        ],
                        value=INITIAL_AUDIO_LANGUAGE_CORRECTION,
                    )
                    oa_language_lock = gr.Checkbox(
                        label="Kunci bahasa utama",
                        value=INITIAL_AUDIO_LANGUAGE_LOCK,
                    )
                    oa_runtime_agreement = gr.Slider(
                        label="Agreement passes",
                        minimum=2,
                        maximum=4,
                        step=1,
                        value=2,
                    )
                oa_status = gr.Markdown(_OA_INITIAL[9])
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### Pipeline aktif di Lab")
                        oa_diagram = gr.HTML(_OA_INITIAL[6])
                    with gr.Column(scale=3):
                        gr.Markdown("### Provider, asal, dan lisensi")
                        oa_provider_table = gr.HTML(_OA_INITIAL[7])
                with gr.Accordion("Rencana pipeline JSON", open=False):
                    oa_config_json = gr.Textbox(
                        label="Open Architecture Plan",
                        value=_OA_INITIAL[8],
                        interactive=False,
                        lines=18,
                        elem_classes=["mono"],
                    )
                with gr.Row():
                    oa_custom_name = gr.Textbox(label="Nama preset custom", value="my_open_architecture_lab")
                    oa_save_btn = gr.Button("Simpan preset Lab")
                    oa_export_btn = gr.Button("Export architecture plan")
                oa_action_message = gr.Textbox(
                    label="Status penyimpanan/export",
                    value="",
                    interactive=False,
                    lines=3,
                )

                gr.Markdown("## A/B Architecture Comparison")
                with gr.Row():
                    oa_compare_left = gr.Dropdown(label="Pipeline A", choices=_OA_PRESET_CHOICES, value="original_audio")
                    oa_compare_right = gr.Dropdown(label="Pipeline B", choices=_OA_PRESET_CHOICES, value="japanese_live_lab")
                    oa_compare_btn = gr.Button("Bandingkan arsitektur")
                oa_compare_output = gr.Markdown(
                    architecture_compare_presets("original_audio", "japanese_live_lab")
                )

                with gr.Accordion("Confirmed Prefix / Local Agreement Demo", open=False):
                    gr.Markdown("Masukkan hipotesis ASR berurutan, satu baris per pembaruan. Tokenizer Lab mendukung Latin dan CJK/Jepang.")
                    oa_hypotheses = gr.Textbox(
                        label="ASR hypotheses",
                        value="私たちは\n私たちはここを\n私たちはここを離れなければならない",
                        lines=7,
                    )
                    oa_agreement = gr.Slider(label="Demo agreement passes", minimum=2, maximum=4, step=1, value=2)
                    oa_demo_btn = gr.Button("Jalankan confirmed-prefix demo")
                    oa_demo_html = gr.HTML("")
                    oa_demo_json = gr.Textbox(label="Demo JSON", value="", interactive=False, lines=14, elem_classes=["mono"])

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

    # Open Architecture Lab events
    _oa_render_outputs = [
        oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
        oa_diagram, oa_provider_table, oa_config_json, oa_status,
    ]
    _oa_preset_outputs = [*_oa_render_outputs, oa_runtime_validation]
    oa_apply_preset_btn.click(
        _oa_apply_preset_ui,
        inputs=[oa_preset, oa_lab_language, oa_runtime_agreement, oa_ui_mode],
        outputs=_oa_preset_outputs,
    )
    oa_preset.change(
        _oa_apply_preset_ui,
        inputs=[oa_preset, oa_lab_language, oa_runtime_agreement, oa_ui_mode],
        outputs=_oa_preset_outputs,
    )
    oa_refresh_btn.click(
        _oa_refresh_with_validation,
        inputs=[
            oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
            oa_lab_language, oa_runtime_agreement, oa_ui_mode,
        ],
        outputs=[oa_diagram, oa_provider_table, oa_config_json, oa_status, oa_runtime_validation],
    )
    for _oa_control in (oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay):
        _oa_control.change(
            _oa_refresh_with_validation,
            inputs=[
                oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
                oa_lab_language, oa_runtime_agreement, oa_ui_mode,
            ],
            outputs=[oa_diagram, oa_provider_table, oa_config_json, oa_status, oa_runtime_validation],
        )
    oa_lab_game.change(
        _oa_game_profile_updates,
        inputs=[oa_lab_game, oa_lab_language],
        outputs=[oa_lab_language, oa_profile_language_note],
    )
    oa_resource_policy.change(
        _oa_resource_policy_updates,
        inputs=[oa_resource_policy],
        outputs=[oa_resource_note],
    )
    oa_asr_model_provider.change(
        _oa_provider_status_ui,
        inputs=[oa_asr_model_provider, oa_lab_audio_mode],
        outputs=[oa_provider_status],
    )
    oa_lab_audio_mode.change(
        _oa_provider_status_ui,
        inputs=[oa_asr_model_provider, oa_lab_audio_mode],
        outputs=[oa_provider_status],
    )
    oa_setup_provider_btn.click(
        _oa_setup_selected_provider_ui,
        inputs=[oa_asr_model_provider, oa_setup_target],
        outputs=[
            oa_provider_progress,
            oa_provider_setup_log,
            oa_provider_status,
            oa_copy_provider_log_btn,
            oa_setup_target,
            oa_provider_copy_message,
        ],
    )
    oa_copy_provider_log_btn.click(
        fn=None,
        inputs=[oa_provider_setup_log],
        outputs=[oa_provider_copy_message],
        js="""(text) => {
            if (!text || !text.trim()) return 'Log setup masih kosong.';
            navigator.clipboard.writeText(text);
            return 'Log setup provider sudah disalin.';
        }""",
    )
    oa_refresh_provider_btn.click(
        _oa_refresh_provider_status_ui,
        inputs=[oa_asr_model_provider, oa_lab_audio_mode],
        outputs=[oa_provider_status],
    )
    oa_delivery_mode.change(
        _oa_delivery_mode_updates,
        inputs=[oa_delivery_mode, oa_cloud_provider],
        outputs=[oa_delivery_note],
    )
    oa_cloud_provider.change(
        _oa_delivery_mode_updates,
        inputs=[oa_delivery_mode, oa_cloud_provider],
        outputs=[oa_delivery_note],
    )
    oa_benchmark_btn.click(
        _oa_benchmark_providers_ui,
        inputs=[oa_benchmark_file, oa_benchmark_providers, oa_benchmark_device],
        outputs=[oa_benchmark_output],
    )
    oa_lab_language.change(
        _oa_runtime_validation_ui,
        inputs=[
            oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
            oa_lab_language, oa_runtime_agreement, oa_ui_mode,
        ],
        outputs=[oa_runtime_validation],
    )
    oa_runtime_agreement.change(
        _oa_runtime_validation_ui,
        inputs=[
            oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
            oa_lab_language, oa_runtime_agreement, oa_ui_mode,
        ],
        outputs=[oa_runtime_validation],
    )
    oa_ui_mode.change(
        _oa_ui_mode_updates,
        inputs=[oa_ui_mode],
        outputs=[oa_mode_help, oa_developer_panel],
    )
    oa_validate_runtime_btn.click(
        _oa_runtime_validation_ui,
        inputs=[
            oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
            oa_lab_language, oa_runtime_agreement, oa_ui_mode,
        ],
        outputs=[oa_runtime_validation],
    )
    oa_overlay_mode.change(
        _oa_overlay_mode_updates,
        inputs=[oa_overlay_mode],
        outputs=[oa_overlay_size_panel, oa_overlay_custom_panel],
    )
    oa_preview_btn.click(
        _oa_toggle_preview_ui,
        inputs=[
            oa_preview_active, oa_overlay_mode, oa_overlay_width, oa_overlay_height,
            oa_overlay_font, oa_overlay_opacity, oa_overlay_show_source, oa_overlay_alignment,
        ],
        outputs=[oa_preview_active, oa_preview_btn, oa_preview_status],
    )
    for _oa_overlay_control in (
        oa_overlay_mode, oa_overlay_width, oa_overlay_height, oa_overlay_font,
        oa_overlay_opacity, oa_overlay_show_source, oa_overlay_alignment,
    ):
        _oa_overlay_control.change(
            _oa_update_preview_ui,
            inputs=[
                oa_preview_active, oa_overlay_mode, oa_overlay_width, oa_overlay_height,
                oa_overlay_font, oa_overlay_opacity, oa_overlay_show_source, oa_overlay_alignment,
            ],
            outputs=[oa_preview_status],
        )
    oa_start_audio_btn.click(
        _oa_start_audio_ui,
        inputs=[
            oa_lab_game, oa_lab_input_mode, oa_lab_device,
            oa_lab_language, oa_lab_audio_mode, oa_lab_profile, oa_lab_test_file,
            oa_preset, oa_source, oa_vad, oa_asr, oa_streaming,
            oa_translation, oa_overlay, oa_runtime_agreement,
            oa_language_correction, oa_language_lock, oa_ui_mode,
            oa_overlay_mode, oa_overlay_width, oa_overlay_height,
            oa_overlay_font, oa_overlay_opacity, oa_overlay_show_source,
            oa_overlay_alignment, oa_resource_policy,
            oa_asr_model_provider, oa_model_lock, oa_delivery_mode, oa_cloud_provider,
        ],
        outputs=[
            oa_runtime_state, oa_runtime_summary, oa_runtime_log,
            oa_runtime_message, oa_runtime_error, oa_runtime_validation,
            oa_preview_active, oa_preview_btn,
        ],
    )
    if oa_live_timer is not None:
        oa_live_timer.tick(
            _oa_live_log_tick,
            inputs=[oa_realtime_log_enabled, oa_lab_profile, oa_lab_audio_mode],
            outputs=[
                oa_runtime_state, oa_runtime_summary, oa_runtime_log,
                oa_runtime_message, oa_runtime_error, oa_provider_transparency,
            ],
        )
    oa_stop_audio_btn.click(
        _oa_stop_audio_ui,
        inputs=[oa_lab_profile, oa_lab_audio_mode],
        outputs=[
            oa_runtime_state, oa_runtime_summary, oa_runtime_log,
            oa_runtime_message, oa_runtime_error, oa_runtime_validation,
        ],
    )
    oa_refresh_runtime_btn.click(
        _oa_refresh_runtime_ui,
        inputs=[oa_lab_profile, oa_lab_audio_mode],
        outputs=[
            oa_runtime_state, oa_runtime_summary, oa_runtime_log,
            oa_runtime_message, oa_runtime_error, oa_runtime_validation,
        ],
    )
    oa_setup_audio_btn.click(
        _oa_setup_audio_runtime_ui,
        inputs=[
            oa_lab_audio_mode, oa_lab_profile,
            oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay,
            oa_lab_language, oa_runtime_agreement, oa_ui_mode,
        ],
        outputs=[oa_audio_setup_log, oa_lab_device, oa_device_message, oa_runtime_validation],
    )
    oa_refresh_devices_btn.click(
        _oa_refresh_audio_devices_ui,
        inputs=[oa_lab_audio_mode],
        outputs=[oa_lab_device, oa_device_message],
    )
    oa_lab_input_mode.change(
        _audio_input_updates,
        inputs=[oa_lab_input_mode],
        outputs=[oa_lab_test_file, oa_lab_device],
    )
    oa_save_btn.click(
        architecture_save_custom,
        inputs=[oa_custom_name, oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay],
        outputs=[oa_action_message],
    )
    oa_export_btn.click(
        architecture_export_plan,
        inputs=[oa_source, oa_vad, oa_asr, oa_streaming, oa_translation, oa_overlay],
        outputs=[oa_action_message],
    )
    oa_compare_btn.click(
        architecture_compare_presets,
        inputs=[oa_compare_left, oa_compare_right],
        outputs=[oa_compare_output],
    )
    oa_demo_btn.click(
        confirmed_prefix_demo,
        inputs=[oa_hypotheses, oa_agreement],
        outputs=[oa_demo_html, oa_demo_json],
    )

    # Dashboard events
    start_btn.click(_start, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode, responsive_story_mode, diagnostic_profile, mode_buffer_checkbox, translation_source], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice])
    audio_start_btn.click(_start_audio, inputs=[model_dropdown, game_dropdown, audio_input_mode, audio_device, audio_language, audio_language_correction, audio_language_lock, audio_processing, audio_usage, audio_engine, audio_mode, audio_profile, audio_test_file], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice])
    setup_audio_btn.click(_setup_audio_ui, inputs=[audio_mode, audio_profile, audio_engine, audio_usage], outputs=[audio_setup_log, audio_device, audio_availability, source_status])
    refresh_audio_devices_btn.click(_refresh_audio_devices_ui, inputs=[audio_mode, audio_profile, audio_engine, audio_usage], outputs=[audio_device, audio_device_message, audio_availability])
    setup_cloud_btn.click(_setup_audio_cloud_ui, inputs=[audio_engine, audio_profile, audio_mode, audio_usage], outputs=[cloud_setup_log, audio_availability])
    save_test_cloud_btn.click(_save_audio_cloud_ui, inputs=[azure_region, azure_api_key, audio_language, audio_engine, audio_profile, audio_mode, audio_usage], outputs=[cloud_setup_log, azure_api_key, audio_availability])
    clear_cloud_btn.click(_clear_audio_cloud_ui, inputs=[audio_engine, audio_profile, audio_mode, audio_usage], outputs=[cloud_setup_log, audio_availability])
    audio_input_mode.change(_audio_input_updates, inputs=[audio_input_mode], outputs=[audio_test_file, audio_device])
    audio_profile.change(_audio_profile_description, inputs=[audio_profile, audio_mode], outputs=[audio_profile_info])
    audio_mode.change(_audio_mode_updates, inputs=[audio_mode, audio_profile, audio_engine, audio_usage], outputs=[audio_profile_info, setup_audio_btn, audio_availability, audio_setup_log, audio_device])
    audio_engine.change(_audio_engine_updates, inputs=[audio_engine, audio_mode, audio_profile, audio_usage], outputs=[audio_availability, audio_setup_log, audio_device, audio_device_message, setup_audio_btn])
    audio_usage.change(_audio_usage_updates, inputs=[audio_usage, audio_profile, audio_mode, audio_engine], outputs=[audio_availability])
    stop_btn.click(_stop, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice, proc_msg, cand_names, cand_special, confirmed_html, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    refresh_btn.click(_refresh_all, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, error_box, candidate_notice])
    apply_rec_btn.click(_force_apply_recommendation, inputs=[game_dropdown], outputs=[game_profile_card, recommendation_box, model_group, model_dropdown, model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode])
    game_dropdown.change(_apply_recommendation, inputs=[game_dropdown, settings_mode], outputs=[game_profile_card, recommendation_box, model_group, model_dropdown, model_md, mode_dropdown, engine_dropdown, interval_slider, ocr_resolution_slider, settings_mode])
    game_dropdown.change(_audio_language_for_game, inputs=[game_dropdown, audio_language], outputs=[audio_language])
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
    translation_source.change(_translation_source_updates, inputs=[translation_source, audio_profile, audio_mode, audio_engine, audio_usage], outputs=[source_status, ocr_runtime_panel, audio_preview_panel, start_btn, audio_start_btn])
    ui_mode.change(_ui_mode_updates, inputs=[ui_mode], outputs=[guided_header_panel, developer_header_panel, recommendation_panel, dashboard_diagnostic_panel, model_controls_panel, advanced_controls_panel, runtime_summary_panel, hardware_panel, performance_policy_info])

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


# v8.9.1 note: runtime supports Name/Term Prediction Guard, UI/Dialog Filter,
# Dialogue Timeout Safety, and general Name/Term Ambiguity Guard.
