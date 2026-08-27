# P0.5 Source Review Preparation

## Outcome

P0.5 menghasilkan antrean verifikasi untuk 50 istilah pilot dan 250 slot gold query. Tidak ada sumber yang otomatis dinaikkan menjadi `verified`, dan tidak ada teks query yang dibuat dari definisi dataset.

## Evidence boundary

- Dataset Hugging Face dan hasil pencocokan P0.4 tetap merupakan kandidat penemuan.
- Registry ini hanya menunjuk halaman/berkas awal pada portal resmi Ditjen PP: <https://peraturan.go.id/>.
- `official_status_signal` adalah sinyal untuk reviewer, bukan keputusan status hukum.
- `verified` memerlukan pemeriksaan manusia atas identitas regulasi, rantai perubahan/status, dokumen resmi, checksum dokumen, pasal, dan definisi.

## Locked inputs

- Pilot: `data/curated/pilot_terms.parquet` (`a78b26903b9b4b499e7a950487d8622c3426693d7e5e8615d14b3db128eec2f1`)
- P0.4 enrichment: `data/curated/pilot_terms_enriched.parquet` (`12c61920e8ec0699710188298a15eba13a74ecf01519e23f3eeb83567b99169c`)
- Registry: `configs/official-source-registry.json` (`f763e47d6c76cd3129be8d0a0d5d2fbe4492e5abd19f7275244c33034c292acb`)
- Registry sources: 39

## Review queue

- Source rows: 50
- Status counts: `{'pending_human_review': 50}`
- Semua row awalnya `pending_human_review` dan `blocked_unverified_source`.
- Status-signal registry:

- `amendment_chain_review_required`: 7
- `portal_not_in_force_observed`: 3
- `status_not_reviewed`: 29

## Gold-query authoring

- Slot: 250 (5 per istilah)
- Locked test terms: 20
- Locked-test seed: `p0.5-locked-test-v1`
- `query_text` sengaja kosong. Author harus membuat parafrasa/deskripsi yang tidak menyebut target term dan tidak menyalin definisi sumber.
- Query baru boleh `approved` setelah source row terkait berstatus `verified` dan query ditinjau manusia.

## Manual next action

1. Buka `official_portal_url` atau `official_document_hint_url`.
2. Pastikan nomor, tahun, judul, status, dan peraturan perubahan/pengganti cocok.
3. Simpan URL dokumen resmi yang benar dan SHA-256 berkas yang ditinjau.
4. Salin pasal serta definisi resmi yang relevan; bandingkan dengan seed tanpa mengubah seed.
5. Isi reviewer, timestamp, dan keputusan. Jalankan `c5-model validate-p05`.
6. Setelah source verified, author dan reviewer mengisi gold queries lalu validasi ulang.

Artefak ini membuat pekerjaan P0.5 reproducible, tetapi P0.5 belum selesai secara evidensial sampai review manual tersebut dilakukan.
