"""Local, accessible tutorial dialog. No model execution, downloads or settings writes."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "tutorial"

SHORTCUTS = [
    ("F1", "pause", "Jeda / lanjutkan", "Hentikan pembacaan sementara, lalu tekan lagi untuk melanjutkan."),
    ("F2", "crop", "Pilih ulang area dialog", "Layar kembali meredup. Tarik kotak baru bila posisi dialog berubah."),
    ("F3", "layers", "Ganti strategi tangkap", "Bergilir melalui Auto, Freeze, High Latency, dan Interval. Periksa indikator mode pada overlay."),
    ("F4", "palette", "Ganti gaya subtitle", "Bergilir melalui gaya tampilan overlay yang tersedia."),
    ("F5", "move", "Ganti posisi subtitle", "Beralih antara posisi mengambang dan posisi menutupi area dialog."),
    ("F6", "minus", "Kecilkan huruf", "Kurangi ukuran huruf subtitle."),
    ("F7", "plus", "Besarkan huruf", "Tambah ukuran huruf subtitle."),
    ("F8", "width", "Ubah lebar subtitle", "Bergilir melalui pilihan lebar box overlay."),
    ("F9", "chip", "Ganti perangkat OCR", "Bergilir antara Adaptif, GPU, dan CPU. Gunakan hanya bila perlu menyesuaikan perangkat saat sesi berjalan."),
    ("F10", "camera", "Tangkap sekali di Freeze", "Ambil satu gambar untuk diterjemahkan. Tekan lagi untuk dialog berikutnya."),
    ("F11", "clock", "Aktifkan / matikan Interval", "Mengaktifkan tangkapan otomatis berulang dengan jeda yang sudah ditentukan."),
    ("Esc", "stop", "Akhiri runtime OCR", "Menghentikan OCR saat runtime aktif. Untuk menutup tutorial ini, gunakan tombol ×."),
]
ADVANCED_SHORTCUTS = [
    ("Ctrl + F11", "expand", "Capture All Screen", "Aktifkan / nonaktifkan pembacaan seluruh layar; berbeda dari area dialog biasa."),
    ("` / Shift + F1", "expand", "Alternatif Capture All Screen", "Kedua shortcut ini juga memanggil fitur Capture All Screen."),
    ("Shift + F9", "layers", "Launcher TitanCore V2", "Membuka launcher tambahan bila komponennya tersedia pada paket yang digunakan."),
]

_PATHS = {
    "pause": '<path d="M9 5v14M15 5v14"/>',
    "crop": '<path d="M6 3v15h15M3 6h15v15"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h3a5 5 0 0 0 5-5c0-3-5-5-9-5Z"/><circle cx="7" cy="10" r=".7"/><circle cx="10" cy="7" r=".7"/><circle cx="15" cy="7" r=".7"/>',
    "move": '<path d="M12 3v18M3 12h18m-12-6 3-3 3 3m-9 9-3-3 3-3m9 12-3 3-3-3m12-9 3 3-3 3"/>',
    "minus": '<path d="M5 12h14"/>', "plus": '<path d="M5 12h14M12 5v14"/>',
    "width": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="m8 10-2 2 2 2m8-4 2 2-2 2M6 12h12"/>',
    "chip": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
    "camera": '<path d="M8 6 9 3h6l1 3h4v14H4V6h4Z"/><circle cx="12" cy="12" r="4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "expand": '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
}


def _icon(name):
    return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + _PATHS[name] + '</svg>'


def _shortcut_cards(items):
    return ''.join(
        f'<article class="ort-key-card"><span class="ort-key-icon">{_icon(icon)}</span>'
        f'<div><kbd>{html.escape(key)}</kbd><h4>{html.escape(title)}</h4><p>{html.escape(text)}</p></div></article>'
        for key, icon, title, text in items
    )


def _figure(filename, alt):
    path = ASSET_DIR / filename
    if not path.is_file():
        return ''
    data = base64.b64encode(path.read_bytes()).decode('ascii')
    try:
        annotations = json.loads((ASSET_DIR / 'annotations.json').read_text(encoding='utf-8')).get(filename, [])
    except (OSError, ValueError):
        annotations = []
    marks = ''.join(
        f'<span class="ort-shot-mark" style="left:{float(m["x"]):.3f}%;top:{float(m["y"]):.3f}%;'
        f'width:{float(m["w"]):.3f}%;height:{float(m["h"]):.3f}%"><b>{int(m["n"])}</b></span>'
        for m in annotations
    )
    return f'<figure class="ort-tutorial-shot"><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}" loading="lazy">{marks}</figure>'


def tutorial_level(mode):
    token = str(mode or "basic").lower()
    if token in {"normal", "recommended"}:
        return "normal"
    if token in {"developer", "expert"}:
        return "developer"
    return "basic"


def tutorial_mode_marker(mode):
    return f'<span id="ort-tutorial-level" data-level="{tutorial_level(mode)}" hidden></span>'


def _normal_content():
    screenshot = _figure('web_normal.png', 'Tangkapan mode Normal: Mode Buffer, strategi capture, perangkat dan mesin OCR, serta status runtime.')
    return f'''
<section class="ort-tutorial-intro"><span class="ort-tutorial-pill">NORMAL · PENGATURAN HARIAN</span><h3>Sesuaikan cara OCR bekerja</h3><p>Normal membuka konfigurasi yang disembunyikan di Basic. Pilih pengaturan sesuai kebutuhan, lalu mulai sesi baru untuk menerapkannya. Pilihan pada halaman ini berbeda dari tingkat tampilan: <strong>Normal tidak otomatis berarti konfigurasi Manual</strong>.</p></section>
<section class="ort-tutorial-section"><h3>Otomatis atau Manual?</h3><div class="ort-tutorial-modes"><article><strong>Otomatis</strong><p>Gunakan rekomendasi profil game sebagai titik awal. Tombol <strong>Terapkan rekomendasi</strong> mengisi kembali pilihan yang disarankan sistem.</p></article><article><strong>Manual</strong><p>Pertahankan model, perangkat, strategi capture, interval, dan resolusi yang Anda pilih. Batas keselamatan runtime tetap dapat berlaku.</p></article><article><strong>Modification</strong><p>Perubahan per model dapat disimpan sebagai override. <strong>Reset default model</strong> menghapus override model tersebut; berbeda dari reset seluruh aplikasi.</p></article></div></section>
<section class="ort-tutorial-section"><h3>Kontrol OCR yang muncul di Normal</h3>{screenshot}<p class="ort-tutorial-muted">Penanda: 7 Mode Buffer · 8 strategi capture · 9 perangkat OCR · 10 mesin pembaca. Gambar menunjukkan letak kontrol; nilai pada contoh bukan rekomendasi untuk semua perangkat.</p><div class="ort-shortcut-grid">
<article class="ort-key-card"><span class="ort-key-icon">{_icon('layers')}</span><div><h4>Keluarga model &amp; profil</h4><p>Pilih Normal, Lite, IDN, Lite IDN, atau Fast, lalu core di dalamnya. Buka Detail model terpilih untuk memahami profil. Memilih core lain dapat mengisi kembali parameter bawaannya.</p></div></article>
<article class="ort-key-card"><span class="ort-key-icon">{_icon('camera')}</span><div><h4>Strategi capture</h4><p><strong>Auto</strong> mengikuti perubahan teks; <strong>Freeze</strong> menunggu F10 setiap tangkapan; <strong>Interval</strong> mengambil tangkapan berulang dengan jeda. Pilih sesuai tempo dialog game.</p></div></article>
<article class="ort-key-card"><span class="ort-key-icon">{_icon('chip')}</span><div><h4>CPU / GPU / Adaptif</h4><p>CPU dan GPU adalah pilihan perangkat yang dikunci. Adaptif mengutamakan GPU dan dapat beralih ketika dibutuhkan. Mesin OCR yang hanya mendukung CPU tidak dapat dipaksa memakai GPU.</p></div></article>
<article class="ort-key-card"><span class="ort-key-icon">{_icon('clock')}</span><div><h4>Interval capture</h4><p>Dalam mode Interval, nilai ini adalah jeda setelah satu tangkapan/OCR selesai. Jeda lebih kecil lebih sering membaca layar. Jalur WebUI memakai minimum 90 ms untuk Interval.</p></div></article>
<article class="ort-key-card"><span class="ort-key-icon">{_icon('expand')}</span><div><h4>Resolusi OCR</h4><p>Skala gambar sebelum OCR. Naikkan bila huruf kecil sulit dibaca, lalu periksa waktu proses dan hasil. Nilai efektif dapat dibatasi guard; Freeze dapat memakai override 100%.</p></div></article>
<article class="ort-key-card"><span class="ort-key-icon">{_icon('pause')}</span><div><h4>Buffer &amp; Responsive Story</h4><p>Mode Buffer menambahkan jeda untuk kestabilan hasil. Responsive Story memprioritaskan dialog terbaru. Ubah satu opsi, jalankan sesi, lalu bandingkan dengan kondisi yang sama.</p></div></article>
</div></section>
<section class="ort-tutorial-section"><h3>Atur beban, lalu periksa hasil efektif</h3><div class="ort-tutorial-modes"><article><strong>Efisien</strong><p>Menekan beban dan mengejar respons cepat. Penghematan tertentu dapat memengaruhi ketelitian pembacaan.</p></article><article><strong>Stabil</strong><p>Titik awal yang seimbang untuk game berjalan bersama OCR. Coba mode ini sebelum menaikkan beban.</p></article><article><strong>Intensive</strong><p>Mengizinkan pemrosesan yang lebih berat. Hasilnya tetap perlu dibandingkan; beban lebih tinggi tidak menjamin semua dialog lebih baik.</p></article></div><p><strong>Level resource</strong> menentukan seberapa kuat karakter mode tersebut. Rentang level adalah 1–5; pada ORT Tools, pergantian ke Normal memakai langkah Terendah/Menengah/Maks dan Developer memungkinkan penyetelan per tingkat. <strong>Resource perangkat</strong> Hemat / Adaptif / Kualitas Optimal mengubah anggaran pemrosesan. Baca <strong>Kesimpulan kombinasi</strong> dan kartu <strong>Status aktif</strong> untuk membedakan pengaturan yang diminta dengan yang diterapkan.</p></section>
<section class="ort-tutorial-section"><h3>Mencoba provider di OCR Lab</h3><p>Pilih mesin pembaca, periksa kesiapan, lalu pilih bahasa tulisan dan perangkat yang didukung. EasyOCR menerapkan paket bahasa; RapidOCR bawaan memakai model Mandarin/Latin tetap; Tesseract memerlukan executable dan traineddata yang sesuai. Konfigurasi sesi Lab disimpan terpisah dari ORT Tools. <strong>Stop</strong> sesi sebelumnya sebelum berpindah pipeline.</p><p>Pengaturan core, capture, interval, resolusi, dan resource Lab dipakai saat <strong>Mulai OCR Lab</strong>. Angka bawaan pada catatan core adalah acuan; slider dapat berisi nilai kustom yang sebelumnya disimpan.</p></section>
<section class="ort-tutorial-section"><h3>Panel tambahan yang tersedia di Normal</h3><ul class="ort-tutorial-drag"><li><strong>Rekomendasi sistem &amp; Detail model:</strong> pahami pilihan profil dan kembalikan default bila diperlukan.</li><li><strong>Model Browser:</strong> bandingkan keluarga dan deskripsi core.</li><li><strong>Pengolahan Data:</strong> kelola nama, istilah, alias, dan blacklist sesuai game. Perubahan di sini memengaruhi data aplikasi.</li><li><strong>Runtime &amp; Tools:</strong> periksa dependensi, Fast engine, GPU, dan diagnostik. Tombol Install/Repair, Reset, dan pemeliharaan dapat mengubah instalasi atau pengaturan; pilih sesuai masalah yang sedang ditangani.</li><li><strong>Live Log &amp; AI Recap:</strong> lihat proses dan salin log sesi. Riwayat tidak dihapus saat tingkat tampilan diganti.</li></ul><details><summary>Profil diagnostic A/B juga tersedia di Normal</summary><p>Biarkan <strong>Baseline Correctness</strong> untuk pemakaian biasa. Opsi uji seperti No-Name-ROI dapat menonaktifkan bagian pembacaan nama; gunakan untuk perbandingan terkontrol, bukan sebagai pilihan lebih cepat tanpa memeriksa hasil.</p></details></section>
'''


def _developer_content():
    screenshot = _figure('web_developer.png', 'Tangkapan mode Developer: diagnostic dashboard dan kartu requested/effective.')
    return f'''
<section class="ort-tutorial-intro ort-tutorial-dev-intro"><span class="ort-tutorial-pill">DEVELOPER · PEMERIKSAAN &amp; PENGUJIAN</span><h3>Telusuri pengaturan sampai ke runtime</h3><p>Developer mempertahankan kontrol Normal dan menambahkan panel analitis, ringkasan runtime/perangkat, serta penjelasan teknis. Tutorial ini menampilkan tambahan Developer terlebih dahulu; panduan kontrol Normal yang tetap tersedia berada di bawahnya.</p></section>
<section class="ort-tutorial-section"><h3>Panel tambahan khusus Developer</h3>{screenshot}<p class="ort-tutorial-muted">Penanda: 11 Diagnostic dashboard · 12 kartu nilai requested/effective. Angka pada gambar adalah contoh status tersimpan; periksa sesi aktif Anda sendiri.</p><div class="ort-shortcut-grid"><article class="ort-key-card"><span class="ort-key-icon">{_icon('chip')}</span><div><h4>Diagnostic dashboard</h4><p>Gunakan Refresh diagnostic untuk membaca strategy, core bridge, runtime action, cache, provider, dan jalur log. Cocokkan informasi ini dengan sesi yang benar-benar aktif.</p></div></article><article class="ort-key-card"><span class="ort-key-icon">{_icon('layers')}</span><div><h4>Runtime ringkas &amp; perangkat</h4><p>Periksa Python/runtime, engine, hardware, serta status strategi. Mendeteksi GPU tidak membuktikan kernel CUDA bisa dipakai; periksa log inisialisasi dan perangkat efektif.</p></div></article><article class="ort-key-card"><span class="ort-key-icon">{_icon('clock')}</span><div><h4>Lima tingkat resource</h4><p>Developer membuka level 1–5. Catat core, mode resource, level, dan resource perangkat bersama-sama agar perbandingan tidak mengubah beberapa variabel tanpa sengaja.</p></div></article></div></section>
<section class="ort-tutorial-section"><h3>Urutan uji yang dapat dibandingkan</h3><ol class="ort-tutorial-drag"><li><strong>Catat baseline.</strong> Gunakan Baseline Correctness, game, bahasa, ROI, core, dan adegan yang sama.</li><li><strong>Ubah satu pengaturan.</strong> Contohnya resolusi OCR atau provider; hentikan sesi, lalu mulai kembali untuk menerapkan konfigurasi.</li><li><strong>Cocokkan requested dan effective.</strong> Baca header START, provider/bahasa, perangkat hasil inisialisasi, applied OCR, serta alasan guard. GPU yang dipilih dapat gagal saat inisialisasi; log adalah bukti perangkat yang akhirnya aktif.</li><li><strong>Pisahkan waktu tiap tahap.</strong> Periksa OCR, antrean, backend terjemahan, dan overlay. Keterlambatan total tidak selalu berasal dari model terjemahan.</li><li><strong>Periksa kualitas, bukan waktu saja.</strong> Bandingkan nama karakter, kata yang hilang, dialog berulang, serta hasil yang tertinggal dari adegan.</li><li><strong>Simpan bukti sesi.</strong> Gunakan Live Log, Analyze Last Session, atau Export Diagnostic Report di Runtime &amp; Tools. Periksa isi log sebelum membagikannya.</li></ol></section>
<section class="ort-tutorial-section"><h3>Membaca eksperimen dan batas pengujian</h3><p><strong>Responsive Story</strong> dan <strong>Diagnostic No-Name-ROI</strong> adalah perlakuan uji yang berbeda. No-Name-ROI dapat menghilangkan akurasi label speaker. Kembalikan ke Baseline setelah pengujian.</p><p>Pada <strong>OCR Lab</strong>, fokuskan validasi pada mesin pembaca, bahasa, perangkat, hasil teks/kotak, dan konfigurasi core. Panel kontrak provider/JSON pipeline yang muncul saat sumber <strong>Audio Lab</strong> dipilih menjelaskan jalur Audio; panel itu bukan konfigurasi pipeline OCR.</p><p>Gunakan keluaran status yang aktual. Nama mode, keberadaan paket, dan estimasi profil belum cukup untuk menyatakan performa atau kompatibilitas sebuah perangkat.</p></section>
'''


def tutorial_html(mode="basic"):
    setup = _figure('web_persiapan.png', 'Tangkapan WebUI: 1 ORT Tools, 2 mode Basic, 3 sumber OCR untuk layar atau Audio untuk suara.')
    start = _figure('web_mulai_ocr.png', 'Tangkapan kontrol OCR: 4 bahasa teks, 5 profil terjemahan, 6 tombol Mulai OCR.')
    installers = sorted(ASSET_DIR.parents[2].glob('*First.bat'))
    installer = html.escape(installers[0].name if installers else 'Install Pertama.bat')
    level = tutorial_level(mode)
    return f'''
<span class="ort-tutorial-launch-slot"><button id="ort-tutorial-open" type="button" aria-haspopup="dialog" aria-controls="ort-tutorial-dialog">{_icon('layers')}<span>Tutorial</span></button></span>
<dialog id="ort-tutorial-dialog" data-level="{level}" aria-labelledby="ort-tutorial-title">
  <header class="ort-tutorial-head"><div><span class="ort-tutorial-eyebrow">PANDUAN PENGGUNA</span><h2 id="ort-tutorial-title">Tutorial ORT · {level.title()}</h2><p id="ort-tutorial-subtitle">Panduan mengikuti tingkat tampilan yang sedang aktif.</p></div><button type="button" class="ort-tutorial-close" aria-label="Tutup tutorial" title="Tutup tutorial">×</button></header>
  <div class="ort-tutorial-scroll">
    <div data-tutorial-for="developer">{_developer_content()}</div>
    <div data-tutorial-for="normal developer">{_normal_content()}</div>
    <div data-tutorial-for="basic">
    <section class="ort-tutorial-intro"><span class="ort-tutorial-pill">UNTUK PENGGUNA BARU · BASIC</span><h3>Mulai dari ORT Tools</h3><p>Gunakan <strong>Basic</strong> dan biarkan profil bawaan bekerja. ORT memakai pengaturan profil serta pemeriksaan CPU/GPU yang tersedia di perangkat Anda. Tidak perlu menaikkan resolusi, jumlah thread, atau beban resource untuk mulai mencoba.</p><details><summary>Belum pernah memasang ORT?</summary><p>Jalankan <strong>{installer}</strong> untuk menyiapkan runtime dan dependensi. Setelah terpasang, buka <strong>Start WebUI.bat</strong>. Tetap biarkan terminal aplikasi terbuka selama digunakan. Model pertama kali mungkin perlu diunduh; tunggu prosesnya selesai.</p></details></section>
    <section class="ort-tutorial-section"><div class="ort-tutorial-step-head"><span>01</span><div><h3>Pilih workspace dan sumber</h3><p>Ikuti penanda pada tangkapan layar WebUI di bawah.</p></div></div><div class="ort-tutorial-columns"><div>{setup}</div><ol class="ort-tutorial-callouts"><li><b>1</b><div><strong>Buka ORT Tools</strong><p>Ini adalah workspace utama untuk penggunaan sehari-hari. Open Architecture Lab tersedia untuk menguji provider lain.</p></div></li><li><b>2</b><div><strong>Pilih Basic, lalu game yang dimainkan</strong><p>Biarkan profil bawaan. Pada Normal, gunakan konfigurasi Otomatis / rekomendasi bila Anda belum ingin mengatur parameter sendiri.</p></div></li><li><b>3</b><div><strong>Tentukan sumber aktif</strong><p><strong>OCR</strong> membaca tulisan yang terlihat pada layar. <strong>Audio</strong> mengenali ucapan dari suara. Untuk panduan terjemahan layar ini, pilih OCR.</p></div></li></ol></div><div class="ort-tutorial-audio"><strong>Jika ingin menerjemahkan suara:</strong> pilih Audio, ikuti pemeriksaan runtime, sumber suara, bahasa dan model yang ditampilkan, lalu tekan <strong>Mulai Audio</strong>. Pemilihan kotak layar pada langkah berikut hanya untuk OCR.</div></section>
    <section class="ort-tutorial-section"><div class="ort-tutorial-step-head"><span>02</span><div><h3>Siapkan OCR dan mulai sesi</h3><p>Bahasa tulisan berbeda dari bahasa suara game.</p></div></div><div class="ort-tutorial-columns"><div>{start}</div><ol class="ort-tutorial-callouts"><li><b>4</b><div><strong>Pilih bahasa teks di layar</strong><p>Contoh: jika teks game Inggris dan suara Jepang, pilih <strong>Inggris</strong>. Hasil diterjemahkan ke Bahasa Indonesia.</p></div></li><li><b>5</b><div><strong>Gunakan profil dan mesin bawaan</strong><p>Pilih game yang sesuai. Biarkan pengaturan teknis direkomendasikan tools; Anda dapat mencoba penyesuaian di Normal setelah sesi pertama berhasil.</p></div></li><li><b>6</b><div><strong>Tekan Mulai OCR, lalu tunggu</strong><p>Buka game dan tampilkan dialognya. Tunggu model siap. Jika belum muncul pemilih area, lihat status dan Live Log; jangan menekan Mulai berulang kali.</p></div></li></ol></div></section>
    <section class="ort-tutorial-section"><div class="ort-tutorial-step-head"><span>03</span><div><h3>Tandai kotak dialog game</h3><p>Layar sedikit meredup dan kursor berubah menjadi tanda + saat pemilihan area siap.</p></div></div>
      <svg class="ort-snip-diagram" viewBox="0 0 920 340" role="img" aria-label="Ilustrasi pemilihan area: tekan dan tahan mouse kiri pada ujung kiri atas dialog, tarik ke kanan bawah, lalu lepaskan."><defs><linearGradient id="ort-scene" x2="1" y2="1"><stop stop-color="#1b3553"/><stop offset="1" stop-color="#101a2d"/></linearGradient><marker id="ort-arrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="#6ee7b7"/></marker></defs><rect width="920" height="340" rx="18" fill="url(#ort-scene)"/><path d="m0 185 140-90 130 95 160-115 180 120 130-140 180 130v155H0" fill="#24354b"/><rect width="920" height="340" rx="18" fill="black" opacity=".35"/><text x="28" y="36" fill="#bfcedd" font-size="16">ILUSTRASI · pemilihan area dialog</text><rect x="125" y="169" width="670" height="128" rx="8" fill="#101827" stroke="#425671"/><text x="150" y="199" fill="#82c6f5" font-size="17">NAMA KARAKTER</text><text x="150" y="231" fill="#eef4ff" font-size="19">Commander, we are ready for the next mission.</text><text x="150" y="260" fill="#eef4ff" font-size="19">Please give us your orders.</text><rect x="112" y="155" width="696" height="155" rx="5" fill="#34d399" fill-opacity=".06" stroke="#6ee7b7" stroke-width="3" stroke-dasharray="8 5"/><path d="M112 143v24m-12-12h24M808 298v24m-12-12h24" stroke="#f8fafc" stroke-width="2"/><circle cx="112" cy="155" r="18" fill="#059669"/><text x="112" y="162" fill="white" font-size="20" text-anchor="middle">1</text><circle cx="808" cy="310" r="18" fill="#059669"/><text x="808" y="317" fill="white" font-size="20" text-anchor="middle">2</text><path d="M148 132 Q460 50 780 141" fill="none" stroke="#6ee7b7" stroke-width="3" marker-end="url(#ort-arrow)"/><text x="460" y="83" fill="#a7f3d0" font-size="18" text-anchor="middle">Tahan klik kiri → tarik ke kanan bawah → lepaskan</text></svg>
      <ol class="ort-tutorial-drag"><li><strong>Mulai dari ujung kiri atas dialog.</strong> Tekan dan tahan tombol kiri mouse.</li><li><strong>Tarik ke ujung kanan bawah.</strong> Sertakan seluruh kalimat dan nama karakter bila ingin ikut dibaca. Hindari menu, tombol, dan bagian layar yang tidak perlu.</li><li><strong>Lepaskan mouse.</strong> Area terkunci dan OCR mulai bekerja. Jika salah memilih, tekan <kbd>F2</kbd> untuk mengulang.</li></ol><div class="ort-tutorial-success"><strong>Sesudah area dipilih:</strong> kembali lanjutkan dialog game. Pada Auto, ORT mengikuti perubahan teks dan menampilkan terjemahan pada overlay. Untuk melihat proses, buka <strong>Aktivitas, Live Log &amp; AI Recap</strong>. Tekan <strong>Stop</strong> di WebUI untuk mengakhiri sesi.</div>
    </section>
    <section class="ort-tutorial-section"><h3>Kenali tiga strategi tangkap</h3><div class="ort-tutorial-modes"><article><strong>Auto</strong><p>Mengikuti perubahan teks secara otomatis. Ini mode awal Basic.</p></article><article><strong>Freeze</strong><p>Satu tangkapan setiap menekan <kbd>F10</kbd>. Tekan lagi untuk dialog berikutnya.</p></article><article><strong>Interval</strong><p>Tangkapan satu per satu secara otomatis. Jeda dijadwalkan setelah proses OCR sebelumnya selesai.</p></article></div><p class="ort-tutorial-muted">Pemilih strategi dan interval tersedia pada Normal / Developer. Angka rekomendasi dan hasil efektif dapat berbeda karena batas keselamatan perangkat.</p></section>
    </div>
    <section class="ort-tutorial-section"><span class="ort-tutorial-pill">SAAT OCR AKTIF</span><h3>Shortcut yang membantu saat bermain</h3><p>Gunakan tombol keyboard pada sesi OCR. Pada laptop, tombol fungsi mungkin perlu ditekan bersama Fn. Shortcut ini untuk runtime OCR, bukan kontrol audio.</p><div class="ort-shortcut-grid">{_shortcut_cards(SHORTCUTS)}</div><details class="ort-tutorial-advanced" data-tutorial-for="normal developer"><summary>Shortcut lanjutan &amp; komponen tambahan</summary><div class="ort-shortcut-grid">{_shortcut_cards(ADVANCED_SHORTCUTS)}</div><p>Capture All Screen membaca seluruh layar dan dapat menangkap teks menu. Untuk pemakaian pertama, gunakan area dialog biasa.</p></details></section>
    <footer class="ort-tutorial-footer"><p>Pengaturan tetap tersimpan. Menutup tutorial tidak mengganti workspace atau menghentikan sesi.</p><button type="button" class="ort-tutorial-done">Mengerti, kembali ke ORT</button></footer>
  </div>
</dialog>'''


TUTORIAL_CSS = r'''
#ort-tutorial-mode-signal {display:none!important}
#ort-tutorial { margin:0!important; padding:0!important; min-height:0!important; border:0!important; }
.ort-tutorial-launch-slot {display:inline-flex;align-self:stretch;align-items:center;flex-shrink:0;}
#ort-tutorial-open {display:inline-flex;gap:7px;align-items:center;justify-content:center;padding:10px 14px;border:1px solid #3a625f;border-radius:9px;color:#a7f3d0;background:#10372f;font:600 14px 'Segoe UI',sans-serif;cursor:pointer;white-space:nowrap;}
#ort-tutorial-open svg {width:17px;height:17px;}
#ort-tutorial-open:hover {background:#175345;color:#fff;}
#ort-tutorial-open:focus-visible,.ort-tutorial-close:focus-visible,.ort-tutorial-done:focus-visible {outline:3px solid #93c5fd;outline-offset:3px;}
#ort-tutorial-dialog {box-sizing:border-box;width:min(1120px,94vw);max-width:1120px;max-height:92vh;height:auto;margin:auto;padding:0;border:1px solid #3c5874;border-radius:22px;background:#0b1626;color:#e8eef8;box-shadow:0 30px 100px #000b;font:15px/1.65 'Segoe UI',sans-serif;overflow:hidden;color-scheme:dark;}
#ort-tutorial-dialog:not([open]) {display:none;}
#ort-tutorial-dialog[open] {display:flex;flex-direction:column;}
#ort-tutorial-dialog::backdrop {background:rgba(1,6,15,.78);backdrop-filter:blur(5px);}
#ort-tutorial-dialog * {box-sizing:border-box;}
#ort-tutorial-dialog [data-tutorial-for] {display:none;}
#ort-tutorial-dialog[data-level="basic"] [data-tutorial-for~="basic"],
#ort-tutorial-dialog[data-level="normal"] [data-tutorial-for~="normal"],
#ort-tutorial-dialog[data-level="developer"] [data-tutorial-for~="developer"] {display:block;}
.ort-tutorial-dev-intro {border-color:#68618d;background:linear-gradient(120deg,#29233e,#102331);}
.ort-tutorial-section>.ort-tutorial-shot {margin-bottom:20px;}

#ort-tutorial-dialog h2,#ort-tutorial-dialog h3,#ort-tutorial-dialog h4 {color:#f8fafc;line-height:1.3;}
#ort-tutorial-dialog h2 {font-size:26px;margin:4px 0 6px;}
#ort-tutorial-dialog h3 {font-size:22px;margin:8px 0 12px;}
#ort-tutorial-dialog h4 {font-size:15px;margin:8px 0 5px;}
#ort-tutorial-dialog p {margin:6px 0 12px;color:#c8d4e5;}
.ort-tutorial-head {display:flex;justify-content:space-between;gap:20px;padding:22px 28px 17px;flex-shrink:0;border-bottom:1px solid #2c425b;background:linear-gradient(110deg,#132a43,#0e2330);}
.ort-tutorial-head p {margin:0!important;font-size:14px;}
.ort-tutorial-eyebrow,.ort-tutorial-pill {font-size:11px;letter-spacing:1.2px;font-weight:800;color:#79e7c1;}
.ort-tutorial-close {flex:0 0 40px;align-self:flex-start;height:40px;width:40px;border:1px solid #4b647d;border-radius:12px;background:#142b40;color:#fff;font-size:29px;line-height:1;cursor:pointer;}
.ort-tutorial-scroll {overflow-y:auto;overscroll-behavior:contain;padding:25px 28px;min-height:0;scrollbar-gutter:stable;}
.ort-tutorial-intro {padding:22px;border:1px solid #2d665c;border-radius:16px;background:linear-gradient(120deg,#10382f,#102331);}
.ort-tutorial-section {margin-top:30px;padding-top:26px;border-top:1px solid #263a52;}
.ort-tutorial-step-head {display:flex;gap:15px;align-items:flex-start;margin-bottom:18px;}
.ort-tutorial-step-head>span {padding:7px 10px;border-radius:11px;background:#183d51;color:#94e7d1;font-size:20px;font-weight:800;}
.ort-tutorial-step-head h3 {margin-top:0!important;}
.ort-tutorial-step-head p {margin-bottom:0!important;}
.ort-tutorial-columns {display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:22px;align-items:start;}
.ort-tutorial-shot {position:relative;margin:0;border:1px solid #3a536e;border-radius:12px;overflow:hidden;background:#111e31;line-height:0;}
.ort-tutorial-shot img {display:block;width:100%;height:auto;}
.ort-shot-mark {position:absolute;border:2px solid #6ee7b7;border-radius:5px;pointer-events:none;box-shadow:0 0 0 1px #03251d;}
.ort-shot-mark b {position:absolute;left:-7px;top:-12px;min-width:23px;height:23px;padding:0 4px;display:flex;align-items:center;justify-content:center;border:1px solid #dcfff1;border-radius:50%;background:#087b5c;color:white;font:bold 13px/1 'Segoe UI',sans-serif;}
.ort-tutorial-callouts {list-style:none;margin:0;padding:0;display:grid;gap:14px;}
.ort-tutorial-callouts li {display:flex;gap:11px;padding:13px;border:1px solid #2c405a;border-radius:12px;background:#111f33;}
.ort-tutorial-callouts li>b {flex:0 0 26px;height:26px;border-radius:50%;background:#087b5c;text-align:center;color:white;}
.ort-tutorial-callouts p {font-size:14px;margin-bottom:0!important;}
.ort-tutorial-audio,.ort-tutorial-success {margin-top:18px;padding:15px 17px;border-radius:12px;background:#102d3b;border-left:3px solid #63b7e7;}
.ort-tutorial-success {background:#10372e;border-left-color:#6ee7b7;}
.ort-snip-diagram {display:block;width:100%;height:auto;border:1px solid #3a536e;border-radius:16px;}
.ort-tutorial-drag {padding-left:23px;}
.ort-tutorial-drag li {margin:10px 0;padding-left:5px;}
.ort-tutorial-modes {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;}
.ort-tutorial-modes article {padding:16px;border-radius:12px;background:#132238;border:1px solid #2b435e;}
.ort-tutorial-muted {font-size:13px;}
.ort-shortcut-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0;}
.ort-key-card {display:flex;gap:12px;padding:16px;border-radius:14px;border:1px solid #2d4560;background:#111f33;}
.ort-key-icon {flex:0 0 27px;color:#78dfc0;padding-top:5px;}
.ort-key-icon svg {width:27px;height:27px;}
.ort-key-card p {font-size:13px;margin:0!important;}
#ort-tutorial-dialog kbd {display:inline-block;padding:2px 8px;border:1px solid #5a6d85;border-bottom-width:3px;border-radius:6px;background:#25374d;color:#f5f9ff;font:700 13px/1.6 'Segoe UI',sans-serif;}
#ort-tutorial-dialog summary {cursor:pointer;color:#b4f1dd;font-weight:600;}
#ort-tutorial-dialog details {padding-top:10px;}
.ort-tutorial-advanced {border:1px solid #304862;border-radius:12px;padding:14px 16px;}
.ort-tutorial-footer {display:flex;justify-content:space-between;align-items:center;gap:18px;margin-top:28px;padding-top:20px;border-top:1px solid #304862;}
.ort-tutorial-footer p {font-size:13px;margin:0!important;}
.ort-tutorial-done {padding:11px 18px;border:0;border-radius:10px;background:#49d2a7;color:#06291f;font:700 14px 'Segoe UI',sans-serif;cursor:pointer;flex-shrink:0;}
@media(max-width:760px){.ort-tutorial-columns,.ort-tutorial-modes{grid-template-columns:1fr}.ort-shortcut-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ort-tutorial-head{padding:17px}.ort-tutorial-scroll{padding:18px}.ort-tutorial-footer{flex-direction:column;align-items:stretch}#ort-tutorial-dialog h2{font-size:21px}}
@media(max-width:480px){.ort-shortcut-grid{grid-template-columns:1fr}.ort-tutorial-intro{padding:16px}#ort-tutorial-dialog{width:96vw;max-height:96dvh;border-radius:14px}}
'''

TUTORIAL_JS = r'''
const dialog = element.querySelector('#ort-tutorial-dialog');
const openButton = element.querySelector('#ort-tutorial-open');
const slot = element.querySelector('.ort-tutorial-launch-slot');
let priorFocus = null;
let priorOverflow = '';
const levelText = {
  basic: ['Tutorial ORT · Basic', 'Panduan sederhana untuk mulai menerjemahkan layar.'],
  normal: ['Tutorial ORT · Normal', 'Konfigurasi harian, core, capture, resource, dan panel yang tersedia di Normal.'],
  developer: ['Tutorial ORT · Developer', 'Diagnostik, pengujian, dan kontrol Normal yang tetap tersedia di Developer.']
};
const applyTutorialMode = () => {
  const level = document.querySelector('#ort-tutorial-level')?.dataset.level || dialog.dataset.level || 'basic';
  const safe = levelText[level] ? level : 'basic';
  if (dialog.dataset.level !== safe) dialog.querySelector('.ort-tutorial-scroll').scrollTop = 0;
  dialog.dataset.level = safe;
  dialog.querySelector('#ort-tutorial-title').textContent = levelText[safe][0];
  dialog.querySelector('#ort-tutorial-subtitle').textContent = levelText[safe][1];
};
const signal = document.querySelector('#ort-tutorial-mode-signal');
if (signal) new MutationObserver(applyTutorialMode).observe(signal, {childList:true,subtree:true,attributes:true});
applyTutorialMode();
openButton.addEventListener('click', () => {
  if (dialog.open) return;
  applyTutorialMode();
  priorFocus = document.activeElement;
  priorOverflow = document.body.style.overflow;
  dialog.showModal();
  document.body.style.overflow = 'hidden';
  dialog.querySelector('.ort-tutorial-close').focus();
});
dialog.querySelectorAll('.ort-tutorial-close,.ort-tutorial-done').forEach(button => {
  button.addEventListener('click', () => dialog.close());
});
dialog.addEventListener('close', () => {
  document.body.style.overflow = priorOverflow;
  if (priorFocus && priorFocus.isConnected) priorFocus.focus();
});
dialog.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const r = dialog.getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
});
// A real button, not a Tab: opening help never changes the selected workspace.
// Keep a span around the button so :nth-of-type tab hiding remains stable.
const attachToTabStrip = () => {
  const tabs = document.querySelector('#ort-workspaces');
  if (!tabs) return false;
  const lastTab = Array.from(tabs.querySelectorAll('[role="tab"]')).find(tab => tab.textContent.trim() === 'Runtime & Tools');
  if (!lastTab) return false;
  if (lastTab.nextElementSibling !== slot) lastTab.after(slot);
  return true;
};
if (!attachToTabStrip()) {
  const observer = new MutationObserver(() => {
    if (attachToTabStrip()) observer.disconnect();
  });
  observer.observe(document.body, {childList:true, subtree:true});
}
'''
