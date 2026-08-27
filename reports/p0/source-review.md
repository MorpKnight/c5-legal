# P0.5 Source Review and Gold Query Authoring

## Outcome

Evidence teknis sudah dikumpulkan untuk 50 source row dari 39 sumber resmi. Berdasarkan konfirmasi manual pengguna dan pengecekan status portal/JDIH, seluruh 50 row telah berstatus 'verified'. Seluruh 250 gold-query slot sudah diisi dengan query hasil authoring teknis; approval gold set masih menunggu review manusia.

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

- Slot total: 250 (5 per istilah); query text terisi 250/250.
- Author status: 'authored' = 250.
- Review status: 'pending_human_review' = 250.
- Target-term leakage check: passed.
- Source-definition copy check: passed.
- Locked test split: 20 istilah / 100 query.
- Query 'approved' tetap memerlukan reviewer manusia yang mengisi 'reviewer_id' dan 'reviewed_at'.

## Next action

1. Review query per istilah untuk relevansi, ketidakambiguannya, dan kecocokan dengan definisi resmi.
2. Jika sesuai, isi 'reviewer_id', 'reviewed_at', dan ubah 'review_status' menjadi 'approved'.
3. Jalankan 'c5-model validate-p05'.
4. Setelah gold set disetujui, lanjutkan benchmark retrieval.
