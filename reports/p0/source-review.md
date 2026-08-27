# P0.5 Source Review and Gold Query Authoring

## Outcome

Evidence teknis sudah dikumpulkan untuk 50 source row dari 39 sumber resmi. Berdasarkan konfirmasi manual pengguna dan pengecekan status portal/JDIH, seluruh 50 row telah berstatus 'verified'. Seluruh source row dapat menjadi dasar authoring gold query, dengan status hukum tetap perlu dipantau sebagai snapshot.

## Evidence boundary

- Dataset Hugging Face dan hasil pencocokan P0.4 tetap merupakan kandidat penemuan.
- Evidence definisi bersumber dari PDF pada portal resmi Ditjen PP: <https://peraturan.go.id/>.
- Status current untuk tiga Permenhub dikonfirmasi melalui JDIH Kementerian Perhubungan; status Permenkominfo 11/2022 dikonfirmasi melalui JDIHN BPHN.
- 'verified' berarti source row telah melewati gate evidence project berdasarkan konfirmasi pengguna; status 'current_with_amendments' dan 'historical_applicable' tetap membawa batasan masing-masing.
- Aplikasi belum boleh menganggap definisi sebagai nasihat atau kesimpulan hukum.

## Review queue

- Source rows: 50
- Status counts: {'verified': 50}
- Evidence fields terisi: 50/50
- Definition comparison: 'exact' = 43, 'equivalent' = 7

## Gold-query authoring

- Slot total: 250 (250 siap diauthor, 0 masih blocked)
- Semua query slot berstatus 'pending_human_review'; 'query_text' tetap kosong.
- Author harus menulis parafrasa/deskripsi yang tidak menyebut target term dan tidak menyalin definisi sumber.
- Query 'approved' tetap memerlukan author dan reviewer manusia.

## Next action

1. Author 5 query per istilah untuk seluruh 50 istilah.
2. Review setiap query dan isi 'query_type', author, reviewer, dan timestamp.
3. Jalankan 'c5-model validate-p05'.
