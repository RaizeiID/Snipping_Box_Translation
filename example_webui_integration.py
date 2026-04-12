"""
Contoh integrasi ke webui.py
"""
from webui_prefs import load_prefs, save_prefs

# contoh saat WebUI init
# prefs = load_prefs(runtime_root)

# contoh saat Start ditekan
# save_prefs(runtime_root, {
#     "engine_mode": selected_engine,
#     "run_mode": selected_mode,
#     "interval_ms": selected_interval,
#     "game_name": selected_game,
#     "model_name": selected_model,
#     "model_family": selected_family,
# })

# contoh tombol Exit merah di pojok kanan atas pada Gradio:
# exit_btn = gr.Button("Exit", variant="stop", elem_id="ort-exit-top-btn")
# exit_btn.click(fn=shutdown_server, outputs=[])

# contoh toast loading saat Start:
# start_btn.click(None, js="ortShowStartToast")
# start_btn.click(start_model_fn, inputs=[...], outputs=[...]).then(None, js="ortHideStartToast")
