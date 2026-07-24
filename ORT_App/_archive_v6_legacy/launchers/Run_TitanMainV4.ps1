# Run_TitanMainV4.ps1
# Jalankan: PowerShell -> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned (sekali saja jika perlu)
# Lalu: .\Run_TitanMainV4.ps1

# ====== WAJIB SET MINIMAL 1 ENGINE ======

# (Rekomendasi) BOX / LibreTranslate
$env:TITAN_ONLINE_URL  = "http://127.0.0.1:5000/translate"
$env:TITAN_ONLINE_FROM = "auto"
$env:TITAN_ONLINE_TIMEOUT = "8"

# CAS Premium / Google GAS (isi jika kamu pakai)
$env:TITAN_GAS_URL     = "https://script.google.com/macros/s/XXXX/exec"
$env:TITAN_GAS_TOKEN   = ""        # optional
$env:TITAN_GAS_TIMEOUT = "12"

# CAS Free / DeepLX (isi jika kamu pakai)
$env:TITAN_DEEPLX_URL     = "http://127.0.0.1:1188"
$env:TITAN_DEEPLX_MODE    = "free"  # free / v1 / v2 (sesuaikan servermu)
$env:TITAN_DEEPLX_TIMEOUT = "10"

# (Opsional) fallback online antar engine
$env:TITAN_V4_FALLBACK_ONLINE = "1"   # 1=ON, 0=OFF
$env:TITAN_V4_BOX_PRIMARY     = "AUTO" # AUTO / GAS / DEEPLX / LIBRE

# ====== RUN ======
$py = "C:\Users\Raizei\AppData\Local\Programs\Python\Python312\python.exe"
$script = Join-Path $PSScriptRoot "TitanMainV4.py"
& $py $script
