from __future__ import annotations

import html
import json
import threading
import time
import webbrowser
from pathlib import Path

import gradio as gr
from launcher_backend import load_prefs, runtime_summary_text, start_model, stop_model, refresh_state
from data_processing_backend import (
    load_settings,
    save_settings,
    get_game_data,
    save_game_data,
    get_candidate_groups,
    merge_selected,
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
)
from gpu_runtime import gpu_summary_text, install_or_repair_gpu

PROJECT_ROOT = Path(__file__).resolve().parent
PREFS = load_prefs()
SETTINGS = load_settings()

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
.copylog-wrap button { background:#0f766e; color:white; border:none; border-radius:10px; padding:10px 14px; cursor:pointer; font-weight:700; }
.copylog-wrap span { margin-left:10px; color:#a7f3d0; font-size:13px; }
.ai-link {
  display:inline-flex; align-items:center; justify-content:center;
  padding:10px 14px; border-radius:12px; text-decoration:none; color:white;
  border:1px solid rgba(255,255,255,.08); font-weight:700;
}
.ai-chatgpt { background:#0f172a; }
.ai-gemini { background:#111827; }
"""
USER_NOTE = """**Catatan penggunaan**\n\n- Gunakan **Start** untuk menjalankan model.\n- **Stop** melakukan hard-stop agar OCR tidak perlu di-spam.\n- **Refresh** berguna jika box ditutup dari shortcut dan web belum sinkron.\n- Runtime custom yang valid akan tampil pada ringkasan runtime.\n"""

MODEL_GROUPS = {
    "basic": [
        "ORTCore V1", "ORTCore V2", "ORTCore V3", "ORTCore V4", "ORTCore V5",
        "ORTCore V5 Lv1", "ORTCore V5 Lv2", "ORTCore V5 Lv3", "ORTCore V5 Lv4",
    ],
    "lite": [
        "ORTCore V1 Lite", "ORTCore V2 Lite", "ORTCore V3 Lite", "ORTCore V4 Lite", "ORTCore V5 Lite",
        "ORTCore V5 Lv1 Lite", "ORTCore V5 Lv2 Lite", "ORTCore V5 Lv3 Lite", "ORTCore V5 Lv4 Lite",
    ],
    "idn": [
        "ORTCore V1 IDN", "ORTCore V1 Lite IDN",
        "ORTCore V2 IDN", "ORTCore V2 Lite IDN",
        "ORTCore V3 IDN", "ORTCore V3 Lite IDN",
        "ORTCore V4 IDN", "ORTCore V4 Lite IDN",
        "ORTCore V5 IDN", "ORTCore V5 Lite IDN",
    ],
}
MODEL_DESCRIPTIONS = {
    "ORTCore V1": "Paling ringan dan cepat. Cocok untuk perangkat lemah dan dialog sederhana.",
    "ORTCore V2": "Seimbang antara kecepatan dan akurasi untuk penggunaan umum.",
    "ORTCore V3": "Lebih berat tetapi lebih teliti untuk dialog kompleks.",
    "ORTCore V4": "Hybrid online + offline untuk mempercepat hasil naturalisasi.",
    "ORTCore V5": "Basis naturalisasi generasi terbaru.",
    "ORTCore V5 Lv1": "Naturalisasi level 1 yang cepat dan ringan.",
    "ORTCore V5 Lv2": "Naturalisasi level 2 yang lebih seimbang.",
    "ORTCore V5 Lv3": "Naturalisasi level 3 yang lebih akurat.",
    "ORTCore V5 Lv4": "Naturalisasi level 4 paling maksimal.",
}
GAME_CHOICES = [("Girls' Frontline 2 Exilium", "GFL2_EXILIUM")]


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
    return MODEL_DESCRIPTIONS.get(name, f"{name} siap dipakai. Deskripsi rinci belum ditulis.")


def _render_catalog(group_key: str) -> str:
    items = MODEL_GROUPS.get(group_key, MODEL_GROUPS["basic"])
    chunks = []
    for item in items:
        desc = html.escape(_model_desc(item))
        chunks.append(f"<div class='card'><b>{html.escape(item)}</b><div style='margin-top:8px;color:#dbeafe'>{desc}</div></div>")
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
        'name_labels': [x[0] for x in name_choices],
        'name_map': {label: item for label, item in name_choices},
        'special_labels': [x[0] for x in special_choices],
        'special_map': {label: item for label, item in special_choices},
    }


def _proc_payload(game: str, message: str = ""):
    data = get_game_data(game)
    cmap = _candidate_map(game)
    settings = load_settings()
    return (
        message,
        gr.update(choices=cmap['name_labels'], value=[]),
        gr.update(choices=cmap['special_labels'], value=[]),
        render_list_html(data['names'], data['name_color'], 'Belum ada daftar nama tersimpan.'),
        render_list_html(data['special_words'], data['special_color'], 'Belum ada daftar kata khusus tersimpan.'),
        render_list_html(data['blacklist'], 'yellow', 'Belum ada blacklist kata.'),
        render_original_table(game),
        data['name_color'],
        data['special_color'],
        settings.get('popup_on_stop', True),
        settings.get('auto_reset_candidates', False),
        render_badge_preview(game),
        _render_color_legend(data['name_color'], data['special_color']),
        gr.update(choices=data['names'], value=[]),
        gr.update(choices=data['special_words'], value=[]),
        gr.update(choices=data['blacklist'], value=[]),
    )


def _on_group_change(group_key: str):
    choices = MODEL_GROUPS.get(group_key, MODEL_GROUPS["basic"])
    value = choices[0] if choices else None
    return gr.update(choices=choices, value=value), _model_desc(value), _render_catalog(group_key)


def _refresh_all(game: str):
    status, log, err, notice = refresh_state()
    err_md = f"**Error terakhir:**\n\n```\n{err}\n```" if err else ""
    notice_md = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return _status_html(status), runtime_summary_text(), log, err_md, notice_md


def _start(model, game, mode, engine, interval_ms):
    status, log, msg, notice = start_model(model, game, mode, engine, interval_ms)
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
    save_settings({'popup_on_stop': bool(popup_on_stop), 'auto_reset_candidates': bool(auto_reset_candidates)})
    data = get_game_data(game)
    data['name_color'] = name_color
    data['special_color'] = special_color
    save_game_data(game, data)
    return "Pengaturan Pengolahan Data disimpan.", render_badge_preview(game), _render_color_legend(name_color, special_color)


def _confirm_candidates(game, name_labels, special_labels, name_color, special_color):
    cmap = _candidate_map(game)
    chosen_names = [cmap['name_map'][x] for x in (name_labels or []) if x in cmap['name_map']]
    chosen_special = [cmap['special_map'][x] for x in (special_labels or []) if x in cmap['special_map']]
    merge_selected(game, names=chosen_names, special_words=chosen_special, name_color=name_color, special_color=special_color)
    clear_candidates(game)
    return _proc_payload(game, f"Konfirmasi berhasil. Nama +{len(chosen_names)}, kata khusus +{len(chosen_special)}.")


def _skip_candidates(game):
    clear_candidates(game)
    return _proc_payload(game, "Kandidat baru di-skip untuk sesi ini.")


def _reset_candidates(game):
    clear_candidates(game)
    return _proc_payload(game, "Daftar kandidat sesi ini dibersihkan.")


def _add_name(game, text):
    items = [x.strip() for x in str(text or '').split(',') if x.strip()]
    merge_selected(game, names=items)
    return ('Daftar Nama diperbarui.', '', *_proc_payload(game)[1:])


def _add_special(game, text):
    items = [x.strip() for x in str(text or '').split(',') if x.strip()]
    merge_selected(game, special_words=items)
    return ('Daftar Kata Khusus diperbarui.', '', *_proc_payload(game)[1:])


def _add_blacklist(game, text):
    items = [x.strip() for x in str(text or '').split(',') if x.strip()]
    merge_selected(game, blacklist=items)
    return ('Blacklist diperbarui.', '', *_proc_payload(game)[1:])


def _remove_name(game, items):
    remove_items(game, 'names', items)
    return _proc_payload(game, 'Item nama dihapus.')


def _remove_special(game, items):
    remove_items(game, 'special_words', items)
    return _proc_payload(game, 'Item kata khusus dihapus.')


def _remove_blacklist(game, items):
    remove_items(game, 'blacklist', items)
    return _proc_payload(game, 'Item blacklist dihapus.')


def _upsert_original(game, current_name, original_name):
    try:
        upsert_original_name(game, current_name, original_name)
        payload = _proc_payload(game, 'Original Name diperbarui.')
        return (payload[0], '', '', *payload[1:])
    except Exception as e:
        payload = _proc_payload(game, f'Gagal menyimpan Original Name: {e}')
        return (payload[0], current_name, original_name, *payload[1:])


def _remove_original(game, current_name):
    remove_original_name(game, current_name)
    payload = _proc_payload(game, 'Original Name dihapus.')
    return (payload[0], '', *payload[1:])


def _build_story_prompt(log_text: str, game: str = "GFL2_EXILIUM"):
    txt = (log_text or "").strip()
    if not txt:
        return "Belum ada live log untuk diringkas."
    return f"""Ubah live log berikut menjadi ringkasan cerita bergaya visual novel untuk game {game}.

Aturan:
- Fokus pada kejadian, dialog, nama karakter, dan konteks adegan.
- Rapikan typo OCR seperlunya tanpa mengubah makna.
- Abaikan baris teknis seperti CACHE, HIT, MISS, PIPE, OCR kecuali penting untuk konteks.
- Tulis dalam bahasa Indonesia yang natural dan enak dibaca.
- Hasil akhir berbentuk ringkasan adegan / story.

LIVE LOG:
{txt}
"""


def _copy_prompt_status(log_text: str):
    return _build_story_prompt(log_text)


basic_choices = MODEL_GROUPS.get(PREFS.get("model_group", "basic"), MODEL_GROUPS["basic"])
default_model = PREFS.get("model", basic_choices[0] if basic_choices else None)
if default_model not in basic_choices:
    default_model = basic_choices[0] if basic_choices else None
init_proc = _proc_payload(PREFS.get('game', 'GFL2_EXILIUM'))
seed_data = get_game_data(PREFS.get('game', 'GFL2_EXILIUM'))

with gr.Blocks(title="ORT Translation v6.6 Patch 1.3") as demo:
    gr.HTML("<div class='hero'><h1>ORT Translation v6.6 Patch 1.3</h1><p>Fokus patch: Pengolahan Data dibuat lebih rapi untuk user awam, model browser dikembalikan lengkap, kandidat baru lebih cerdas, tombol copy live log, dan reset kandidat manual/otomatis.</p></div>")
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
                        model_group = gr.Radio(label="Kolom model", choices=[("Model dasar", "basic"), ("Lite", "lite"), ("IDN", "idn")], value=PREFS.get("model_group", "basic"))
                        model_dropdown = gr.Dropdown(label="Pilih model", choices=basic_choices, value=default_model)
                    model_md = gr.Markdown(_model_desc(default_model))
                    with gr.Row():
                        game_dropdown = gr.Dropdown(label="Nama Game", choices=GAME_CHOICES, value=PREFS.get("game", "GFL2_EXILIUM"))
                        mode_dropdown = gr.Dropdown(label="Mode", choices=[("Otomatis", "auto"), ("Jeda / Freeze", "freeze"), ("Interval", "interval")], value=PREFS.get("mode", "freeze"))
                    with gr.Row():
                        engine_dropdown = gr.Dropdown(label="Engine OCR / Terjemahan", choices=[("CPU", "cpu"), ("GPU", "gpu"), ("Hybrid", "hybrid")], value=PREFS.get("engine", "gpu"))
                        interval_slider = gr.Slider(label="Interval / capture ms", minimum=40, maximum=500, step=10, value=int(PREFS.get("interval_ms", 80)))
                    with gr.Row():
                        start_btn = gr.Button("Start", variant="primary")
                        refresh_btn = gr.Button("Refresh")
                        stop_btn = gr.Button("Stop", variant="stop")
                    launch_msg = gr.Textbox(label="Status launcher", interactive=False)
                with gr.Column(scale=2):
                    state_box = gr.HTML(_status_html("STATUS: IDLE"))
                    runtime_box = gr.Textbox(label="Runtime summary", value=runtime_summary_text(), interactive=False, lines=6, elem_classes=["mono"])
                    error_box = gr.Markdown("")
            with gr.Row():
                gr.HTML("<div class='copylog-wrap'><button onclick=\"(function(){const ta=document.querySelector('#live_log textarea'); if(ta){navigator.clipboard.writeText(ta.value); const s=document.getElementById('copylog_status'); if(s){s.textContent='Live log tersalin'; setTimeout(()=>s.textContent='',1500);}}})()\">Copy Live Log</button><span id='copylog_status'></span></div>")
            log_box = gr.Textbox(label="Live log", lines=18, interactive=False, autoscroll=True, elem_classes=["logbox"], elem_id="live_log")
            gr.Markdown(USER_NOTE)

        with gr.Tab("Model Browser"):
            catalog_html = gr.HTML(_render_catalog(PREFS.get("model_group", "basic")))

        with gr.Tab("Pengaturan UI"):
            gr.Markdown("Tampilan rich UI dipertahankan. Patch ini fokus ke Pengolahan Data, model browser, dan perbaikan kualitas kandidat.")

        with gr.Tab("Pengolahan Data"):
            gr.Markdown("Pengolahan Data dibuat seperti halaman aplikasi biasa: klik, pilih, dan simpan. Tidak perlu mengetik JSON atau perintah manual.")
            with gr.Tabs():
                with gr.Tab("Kandidat Baru"):
                    gr.Markdown("Sistem akan mencatat kandidat **sementara** saat OCR berjalan. Setelah Stop atau ESC, Anda bisa olah kandidat ini sebelum benar-benar masuk ke data tetap.")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### Kandidat untuk Daftar Nama")
                            cand_names = gr.CheckboxGroup(label="Pilih kandidat nama / panggilan / istilah nama", choices=init_proc[1]['choices'], value=[])
                        with gr.Column():
                            gr.Markdown("### Kandidat untuk Kata Khusus")
                            cand_special = gr.CheckboxGroup(label="Pilih kandidat kata khusus", choices=init_proc[2]['choices'], value=[])
                    with gr.Row():
                        confirm_btn = gr.Button("Konfirmasi Pilihan", variant="primary")
                        skip_btn = gr.Button("Skip Kandidat Sesi Ini")
                        refresh_candidates_btn = gr.Button("Refresh Kandidat")
                        reset_candidates_btn = gr.Button("Reset Kandidat")
                    proc_msg = gr.Textbox(label="Status pengolahan data", interactive=False, value=init_proc[0])
                    preview_html = gr.HTML(init_proc[11], label="Preview warna label")

                with gr.Tab("Daftar Nama"):
                    gr.Markdown("Kolom ini mencakup **nama karakter, panggilan, dan istilah nama** yang ingin Anda tandai saat muncul di hasil terjemahan.")
                    names_html = gr.HTML(init_proc[3])
                    add_name_txt = gr.Textbox(label="Tambah daftar nama (pisahkan dengan koma)")
                    add_name_btn = gr.Button("Tambah ke Daftar Nama")
                    remove_name_pick = gr.CheckboxGroup(label="Pilih nama yang ingin dihapus", choices=seed_data['names'], value=[])
                    remove_name_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Daftar Kata Khusus"):
                    gr.Markdown("Kata Khusus berguna sebagai notifikasi konteks, misalnya **T-Doll**, **Lviv**, **Project Eden**, atau istilah lain yang ingin ditandai warna berbeda.")
                    special_html = gr.HTML(init_proc[4])
                    add_special_txt = gr.Textbox(label="Tambah kata khusus (pisahkan dengan koma)")
                    add_special_btn = gr.Button("Tambah ke Kata Khusus")
                    remove_special_pick = gr.CheckboxGroup(label="Pilih kata khusus yang ingin dihapus", choices=seed_data['special_words'], value=[])
                    remove_special_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Original Name"):
                    gr.Markdown("Kolom ini berisi nama asli / original name karakter dari GFL sebelumnya, misalnya **Alva = AN-94** atau **Voymastina = AK-15**.")
                    original_html = gr.HTML(init_proc[6])
                    with gr.Row():
                        original_current = gr.Textbox(label="Nama sekarang")
                        original_old = gr.Textbox(label="Original Name")
                    add_original_btn = gr.Button("Tambah / Perbarui Original Name")
                    remove_original_txt = gr.Textbox(label="Nama sekarang yang ingin dihapus dari Original Name")
                    remove_original_btn = gr.Button("Hapus Original Name")

                with gr.Tab("Blacklist Kata"):
                    gr.Markdown("Kata dalam blacklist tidak perlu diterjemahkan. Ini berguna untuk menghemat proses dan menghindari OCR memproses kata UI atau kata tetap.")
                    blacklist_html = gr.HTML(init_proc[5])
                    add_blacklist_txt = gr.Textbox(label="Tambah blacklist kata (pisahkan dengan koma)")
                    add_blacklist_btn = gr.Button("Tambah ke Blacklist")
                    remove_blacklist_pick = gr.CheckboxGroup(label="Pilih blacklist yang ingin dihapus", choices=seed_data['blacklist'], value=[])
                    remove_blacklist_btn = gr.Button("Hapus yang Dipilih")

                with gr.Tab("Pengaturan Pengolahan"):
                    gr.Markdown("Gunakan pengaturan ini agar Pengolahan Data tetap nyaman dipakai user awam.")
                    color_legend_html = gr.HTML(init_proc[12])
                    popup_toggle = gr.Checkbox(label="Aktifkan popup / notifikasi kandidat baru setelah Stop atau ESC", value=SETTINGS.get('popup_on_stop', True))
                    auto_reset_toggle = gr.Checkbox(label="Reset kandidat otomatis saat Start sesi baru", value=SETTINGS.get('auto_reset_candidates', False))
                    with gr.Row():
                        name_color = gr.Radio(label="Warna label Daftar Nama", choices=[(COLOR_LABELS[c], c) for c in COLOR_CHOICES], value=init_proc[7])
                        special_color = gr.Radio(label="Warna label Kata Khusus", choices=[(COLOR_LABELS[c], c) for c in COLOR_CHOICES], value=init_proc[8])
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
            gr.Markdown("Panel troubleshooting runtime, GPU, dan ringkasan AI dari Live Log.")
            with gr.Row():
                runtime_tools = gr.Textbox(label="Runtime ringkas", value=runtime_summary_text(), interactive=False, lines=6, elem_classes=["mono"])
                gpu_box = gr.Textbox(label="GPU Doctor", value=gpu_summary_text(), interactive=False, lines=12, elem_classes=["mono"])
            with gr.Row():
                refresh_gpu_btn = gr.Button("Refresh GPU Doctor")
                repair_gpu_btn = gr.Button("Install / Repair GPU (Torch CUDA)")
            gpu_repair_log = gr.Textbox(label="GPU Install / Repair Log", value="", interactive=False, lines=10, elem_classes=["mono"])
            ai_prompt_box = gr.Textbox(label="Prompt ringkasan story dari Live Log", value="", interactive=False, lines=14, elem_classes=["mono"])
            gr.HTML("""
            <div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:8px'>
              <a class='ai-link ai-chatgpt' href='https://chat.openai.com/' target='_blank'>Buka ChatGPT</a>
              <a class='ai-link ai-gemini' href='https://gemini.google.com/' target='_blank'>Buka Gemini</a>
            </div>
            <p style='color:#cbd5e1;margin-top:10px'>Salin prompt di atas lalu tempel ke ChatGPT atau Gemini untuk membuat ringkasan story GFL2 dari live log.</p>
            """)

    start_btn.click(_start, inputs=[model_dropdown, game_dropdown, mode_dropdown, engine_dropdown, interval_slider], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice])
    stop_btn.click(_stop, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, launch_msg, error_box, candidate_notice, proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    refresh_btn.click(_refresh_all, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, error_box, candidate_notice])
    model_group.change(_on_group_change, inputs=[model_group], outputs=[model_dropdown, model_md, catalog_html])
    model_dropdown.change(lambda m: _model_desc(m), inputs=[model_dropdown], outputs=[model_md])

    refresh_candidates_btn.click(_proc_payload, inputs=[game_dropdown], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    reset_candidates_btn.click(_reset_candidates, inputs=[game_dropdown], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    save_proc_btn.click(_save_processing_settings, inputs=[game_dropdown, popup_toggle, auto_reset_toggle, name_color, special_color], outputs=[proc_msg, preview_html, color_legend_html])
    confirm_btn.click(_confirm_candidates, inputs=[game_dropdown, cand_names, cand_special, name_color, special_color], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    skip_btn.click(_skip_candidates, inputs=[game_dropdown], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    add_name_btn.click(_add_name, inputs=[game_dropdown, add_name_txt], outputs=[proc_msg, add_name_txt, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    add_special_btn.click(_add_special, inputs=[game_dropdown, add_special_txt], outputs=[proc_msg, add_special_txt, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    add_blacklist_btn.click(_add_blacklist, inputs=[game_dropdown, add_blacklist_txt], outputs=[proc_msg, add_blacklist_txt, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    remove_name_btn.click(_remove_name, inputs=[game_dropdown, remove_name_pick], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    remove_special_btn.click(_remove_special, inputs=[game_dropdown, remove_special_pick], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    remove_blacklist_btn.click(_remove_blacklist, inputs=[game_dropdown, remove_blacklist_pick], outputs=[proc_msg, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    add_original_btn.click(_upsert_original, inputs=[game_dropdown, original_current, original_old], outputs=[proc_msg, original_current, original_old, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])
    remove_original_btn.click(_remove_original, inputs=[game_dropdown, remove_original_txt], outputs=[proc_msg, remove_original_txt, cand_names, cand_special, names_html, special_html, blacklist_html, original_html, name_color, special_color, popup_toggle, auto_reset_toggle, preview_html, color_legend_html, remove_name_pick, remove_special_pick, remove_blacklist_pick])

    refresh_gpu_btn.click(lambda log: (runtime_summary_text(), gpu_summary_text(), _build_story_prompt(log)), inputs=[log_box], outputs=[runtime_tools, gpu_box, ai_prompt_box])
    repair_gpu_btn.click(lambda log: (runtime_summary_text(), gpu_summary_text(), install_or_repair_gpu(), _build_story_prompt(log)), inputs=[log_box], outputs=[runtime_tools, gpu_box, gpu_repair_log, ai_prompt_box])

    timer = gr.Timer(1.0)
    timer.tick(_refresh_all, inputs=[game_dropdown], outputs=[state_box, runtime_box, log_box, error_box, candidate_notice])

    def _exit_app():
        raise SystemExit(0)

    exit_btn.click(_exit_app)

if __name__ == '__main__':
    def _open_browser():
        time.sleep(2.0)
        webbrowser.open('http://127.0.0.1:7860')

    threading.Thread(target=_open_browser, daemon=True).start()
    demo.queue().launch(server_name='127.0.0.1', server_port=7860, inbrowser=False, css=CSS)
