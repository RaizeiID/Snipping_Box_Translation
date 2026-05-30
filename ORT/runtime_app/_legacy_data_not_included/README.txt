v8.7 Full Release Hygiene
=========================

Paket baru ini tidak membawa log sesi, cache terjemahan lama, status runtime sementara, atau database NPC/unique term yang terkontaminasi hasil OCR lama.

Alasan:
- v8.7 berfokus pada pencegahan footer noise/false speaker GFL. Membawa database lama yang berisi false learning akan membuat validasi awal bias.
- Glossary valid awal tetap tersedia melalui data_processing_store.json dan configs/gfl_dialogue_profile.json; npc_database.json/unique_terms.json dirilis ulang hanya dengan seed berkeyakinan tinggi.

Folder instalasi lama pengguna tetap menjadi backup apabila ada cache atau konfigurasi yang ingin dipindahkan secara manual setelah evaluasi.
