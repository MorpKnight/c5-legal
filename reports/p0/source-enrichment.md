# P0.4 Source Enrichment

## Outcome

Snapshot `Azzindani/ID_REG_MD_RAG` diproses sebagai corpus kandidat, bukan sumber hukum terverifikasi. Pencocokan identitas regulasi ditemukan untuk 4 dari 50 istilah pilot; kandidat yang juga memuat istilah ditemukan untuk 4 istilah.

Tidak ada record yang dinaikkan menjadi `verified`. Hasil ini menunjukkan dataset eksternal dapat membantu sebagian enrichment, tetapi tidak cukup menjadi authority layer untuk pilot AMT tanpa pemeriksaan sumber resmi.

## Locked inputs

- Pilot: `data/curated/pilot_terms.parquet`
- Pilot SHA-256: `a78b26903b9b4b499e7a950487d8622c3426693d7e5e8615d14b3db128eec2f1`
- Corpus: `Azzindani/ID_REG_MD_RAG`
- Revision: `ba099d603c1f4ce044795ecbb79a6e4fd172de2f`
- Local snapshot: `data/raw/huggingface/ID_REG_MD_RAG/ba099d603c1f4ce044795ecbb79a6e4fd172de2f/train.parquet`
- Snapshot SHA-256: `e2411e85da1809e86694a477ab1f7e071e0fce7e95c35c12d12b38863974b367`
- Snapshot size: 1,321,055,102 byte
- Corpus rows: 199,994
- Claimed dataset license: `CC-BY-4.0`; attribution and upstream rights still require review

## Match statuses

- `candidate_exact_definition`: 3
- `candidate_high_coverage`: 1
- `regulation_not_found`: 46

## Coverage and safety checks

- Identity coverage: 8.0%
- Term-in-regulation coverage: 8.0%
- Exact source-definition matches: 3
- High token-coverage candidates: 4
- Terms with candidate metadata warnings: 2
- Officially verified records: 0
- Every enriched term remains `pending_review`: `true`
- KG source decision: `deferred_after_probe`

## Matched candidates

- Jaminan Fidusia — `candidate_exact_definition` — `Pasal 1` — warning: `low_title_similarity`
- Konsumen — `candidate_exact_definition` — `Pasal 1` — warning: `none`
- Nasabah Debitur — `candidate_exact_definition` — `Preamble` — warning: `definition_found_in_non_article_metadata`
- Penyelenggaraan Telekomunikasi — `candidate_high_coverage` — `Pasal 1` — warning: `none`

## Unresolved terms

- Badan Usaha — `regulation_not_found` — Undang-Undang Nomor 11 Tahun 2020
- Data Pribadi — `regulation_not_found` — Undang-Undang Nomor 27 Tahun 2022
- Dewan Komisaris — `regulation_not_found` — Undang-Undang Nomor 40 Tahun 2007
- Direksi — `regulation_not_found` — Undang-Undang Nomor 40 Tahun 2007
- Hukum Adat — `regulation_not_found` — Undang-Undang Nomor 21 Tahun 2001
- Masyarakat Hukum Adat — `regulation_not_found` — Undang-Undang Nomor 32 Tahun 2009
- Pengendali Data Pribadi — `regulation_not_found` — Undang-Undang Nomor 27 Tahun 2022
- Perseroan Terbatas — `regulation_not_found` — Undang-Undang Nomor 40 Tahun 2007
- Kode Etik Jurnalistik — `regulation_not_found` — Peraturan Presiden Nomor 32 Tahun 2024
- Lembaga Penyedia Layanan Peningkatan Kualitas Keluarga — `regulation_not_found` — Peraturan Menteri Pemberdayaan Perempuan dan Perlindungan Anak Nomor 3 Tahun 2023
- Dokumen Elektronik — `regulation_not_found` — Undang-Undang Nomor 19 Tahun 2016
- Informasi Elektronik — `regulation_not_found` — Undang-Undang Nomor 19 Tahun 2016
- Kesejahteraan Pekerja/Buruh — `regulation_not_found` — Undang-Undang Nomor 13 Tahun 2003
- Kontrak Kerja Konstruksi — `regulation_not_found` — Undang-Undang Nomor 2 Tahun 2017
- Korporasi — `regulation_not_found` — Undang-Undang Nomor 9 Tahun 2013
- Pelaku Usaha Sektor Keuangan — `regulation_not_found` — Undang-Undang Nomor 4 Tahun 2023
- Perjanjian Internasional — `regulation_not_found` — Undang-Undang Nomor 24 Tahun 2000
- Prosesor Data Pribadi — `regulation_not_found` — Undang-Undang Nomor 27 Tahun 2022
- Tanda Tangan Elektronik — `regulation_not_found` — Undang-Undang Nomor 19 Tahun 2016
- Bahan Kimia Daftar 1 — `regulation_not_found` — Undang-Undang Nomor 9 Tahun 2008
- Bahan Kimia Daftar 3 — `regulation_not_found` — Undang-Undang Nomor 9 Tahun 2008
- Bank dalam Likuidasi — `regulation_not_found` — Peraturan Lembaga Penjamin Simpanan Nomor 1 Tahun 2022
- Bebas dari Tera dan Tera Ulang — `regulation_not_found` — Peraturan Menteri Perdagangan Nomor 24 Tahun 2024
- Bebas dari Tera Ulang — `regulation_not_found` — Peraturan Menteri Perdagangan Nomor 24 Tahun 2024
- Kapal Penumpang di Bawah Permukaan Air (Passenger Submersible Craft) — `regulation_not_found` — Peraturan Menteri Perhubungan Nomor PM 6 Tahun 2022
- Kelaiklautan Kapal Penumpang di Bawah Permukaan Air (Passenger Submersible Craft) — `regulation_not_found` — Peraturan Menteri Perhubungan Nomor PM 6 Tahun 2022
- Likuidasi Bank — `regulation_not_found` — Peraturan Lembaga Penjamin Simpanan Nomor 1 Tahun 2022
- Benih Bening Lobster (puerulus) — `regulation_not_found` — Peraturan Menteri Kelautan dan Perikanan Nomor 7 Tahun 2024
- Dana Reboisasi — `regulation_not_found` — Peraturan Pemerintah Nomor 23 Tahun 2021
- Factoring With Recourse — `regulation_not_found` — Peraturan Otoritas Jasa Keuangan Nomor 35/POJK.05/2018
- Klien Pemasyarakatan — `regulation_not_found` — Undang-Undang Nomor 22 Tahun 2022
- Manual Operasi Penyelenggara Perancangan Prosedur Penerbangan — `regulation_not_found` — Peraturan Menteri Perhubungan Nomor PM 11 Tahun 2022
- Pernyataan Standar Akuntansi Pemerintahan — `regulation_not_found` — Peraturan Pemerintah Nomor 71 Tahun 2010
- Air Minum pH Tinggi — `regulation_not_found` — Peraturan Menteri Perindustrian Nomor 62 Tahun 2024
- Entitas Induk yang Dimiliki Sebagian (Partially-Owned Parent Entity) — `regulation_not_found` — Peraturan Menteri Keuangan Nomor 136 Tahun 2024
- Nomor UN (UN Number) — `regulation_not_found` — Peraturan Menteri Perhubungan Nomor PM 32 Tahun 2022
- Pengakhiran Transaksi Keuangan melalui Perjumpaan Utang — `regulation_not_found` — Peraturan Bank Indonesia Nomor 12 Tahun 2023
- Gender — `regulation_not_found` — Peraturan Menteri Pemberdayaan Perempuan dan Perlindungan Anak Nomor 13 Tahun 2021
- Kosmetik — `regulation_not_found` — Peraturan Pemerintah Nomor 28 Tahun 2024
- Layanan Pengiriman Elektronik Tercatat — `regulation_not_found` — Peraturan Menteri Komunikasi dan Informatika Nomor 11 Tahun 2022
- Musyawarah Penetapan Ganti Kerugian — `regulation_not_found` — Peraturan Mahkamah Agung Nomor 2 Tahun 2021
- Perselisihan Hubungan Industrial — `regulation_not_found` — Undang-Undang Nomor 2 Tahun 2004
- Arsitektur — `regulation_not_found` — Undang-Undang Nomor 6 Tahun 2017
- Badan Amil Zakat Nasional — `regulation_not_found` — Undang-Undang Nomor 23 Tahun 2011
- Efek Bersifat Utang Terkait Keberlanjutan (sustainability-linked bond) dan/atau Sukuk Terkait Keberlanjutan (sustainability-linked sukuk) — `regulation_not_found` — Peraturan Otoritas Jasa Keuangan Nomor 18 Tahun 2023
- Lingkungan Hidup — `regulation_not_found` — Undang-Undang Nomor 32 Tahun 2009

## Decision boundary

- Dataset rows may propose a candidate article and text span.
- Dataset metadata, generated scores, embeddings, and knowledge-graph fields are not legal authority.
- `verified` requires an official regulation URL, identity check, text comparison, and human review.
- Query authoring and retrieval benchmarking must not treat unresolved records as gold labels.
