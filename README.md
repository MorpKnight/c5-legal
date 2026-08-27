# c5-model

`c5-model` adalah workspace eksperimen data dan retrieval untuk fitur Dictionary dan Suggestion pada AMT. Workspace ini dipisahkan dari aplikasi agar data mentah, eksperimen model, dan artefak evaluasi tidak membebani repository aplikasi.

## Status

- P0.0 — kontrak eksperimen: **selesai**
- P0.1 — scaffold reproducible: **selesai**
- P0.2 — audit dan normalisasi kamus: **selesai**
- P0.3 — pemilihan pilot 50 istilah: **pipeline tersedia; lihat `c5-model status` untuk hasil run**
- P0.4 — source enrichment kandidat: **pipeline tersedia; lihat `c5-model status` untuk hasil run**

Tidak ada model, embedding, atau dataset Hugging Face yang diproses pada P0.2.

## Pertanyaan P0

> Jika pengguna memberikan deskripsi atau potongan kalimat hukum Indonesia, apakah sistem dapat menemukan istilah yang relevan beserta sumbernya secara konsisten, tanpa mengarang dan tanpa langsung mengubah dokumen?

P0 membandingkan exact match, fuzzy match, BM25, semantic embedding, dan—jika dibutuhkan—hybrid retrieval. Hasil P0 adalah bukti teknis dan keputusan pendekatan, bukan validasi hukum.

## Scope

P0 mencakup:

- corpus istilah hukum yang dapat diaudit;
- pemisahan teks sumber dan teks retrieval;
- pilot 50 istilah;
- gold evaluation queries;
- pencocokan kandidat sumber;
- benchmark kualitas dan runtime;
- decision gate sebelum integrasi AMT.

P0 tidak mencakup:

- penggantian otomatis pada dokumen;
- UI Dictionary atau Suggestion;
- integrasi ke AMT;
- analisis seluruh dokumen;
- typo detection;
- fine-tuning;
- klaim bahwa kandidat merupakan interpretasi hukum yang benar.

Kontrak lengkap tersedia di [`docs/p0-contract.md`](docs/p0-contract.md).

## Struktur

```text
configs/       konfigurasi eksperimen yang ditinjau manusia
data/raw/      salinan input immutable; tidak masuk Git
data/interim/  hasil antara; tidak masuk Git
data/curated/  corpus terkurasi; tidak masuk Git
data/evaluation/ gold queries dan split evaluasi; tidak masuk Git
data/samples/  sampel kecil yang aman untuk test
docs/          kontrak dan decision records
manifests/     provenance, revision, checksum, dan status sumber
reports/p0/    laporan audit dan benchmark yang boleh masuk Git
src/           kode pipeline
tests/         pemeriksaan otomatis
artifacts/     model/index lokal; tidak masuk Git
exports/       kandidat paket untuk AMT; tidak masuk Git
```

## Environment

Project menggunakan Python 3.12 dan `uv`.

```bash
uv sync
uv run c5-model status
uv run python -m unittest discover -s tests -v
```

Jalankan audit P0.2 pada input yang sudah ditempatkan di `data/raw/`:

```bash
uv run c5-model audit
```

Perintah tersebut memverifikasi input tidak berubah, membuang duplikat persis,
memisahkan record yang belum terverifikasi, membuat `retrieval_text`, menulis
CSV/Parquet hasil antara, memperbarui manifest, dan menghasilkan laporan audit.

Pilih pilot P0.3 setelah P0.2 selesai:

```bash
uv run c5-model select-pilot
```

Selector mengunci anchor dan istilah domain yang disepakati, mengecualikan
quarantine dan normalization warning, membatasi dominasi satu sumber, lalu
mengisi slot lain dari multi-sense, pasangan near-neighbor, alias, angka,
definisi panjang, dan kasus tipikal. Seluruh hasil masih `pending_review`.

Jalankan source enrichment P0.4 setelah snapshot yang dipin tersedia:

```bash
mkdir -p data/raw/huggingface/ID_REG_MD_RAG/ba099d603c1f4ce044795ecbb79a6e4fd172de2f
curl -fL --retry 5 --continue-at - \
  --output data/raw/huggingface/ID_REG_MD_RAG/ba099d603c1f4ce044795ecbb79a6e4fd172de2f/train.parquet \
  "https://huggingface.co/datasets/Azzindani/ID_REG_MD_RAG/resolve/ba099d603c1f4ce044795ecbb79a6e4fd172de2f/train.parquet?download=true"
printf '%s  %s\n' \
  e2411e85da1809e86694a477ab1f7e071e0fce7e95c35c12d12b38863974b367 \
  data/raw/huggingface/ID_REG_MD_RAG/ba099d603c1f4ce044795ecbb79a6e4fd172de2f/train.parquet \
  | sha256sum -c -
uv run c5-model enrich-sources
```

Pipeline mencocokkan jenis, nomor, dan tahun regulasi, lalu merangking paling
banyak tiga kandidat pasal per istilah berdasarkan keberadaan istilah,
kemiripan definisi, dan judul. Hasil Hugging Face hanya berstatus kandidat;
tidak ada jalur otomatis menjadi `verified`.

## Data handling

- Data mentah tidak diubah di tempat.
- File besar tidak dimasukkan ke Git.
- Setiap sumber harus memiliki revision atau snapshot identifier dan checksum sebelum diproses.
- `verified` hanya boleh diberikan setelah sumber resmi ditinjau.
- Data dari Hugging Face diperlakukan sebagai kandidat corpus, bukan otoritas hukum.
- Tidak ada dokumen pengguna AMT yang digunakan dalam P0.

## Tahap berikutnya

Setelah P0.4, P0.5 memeriksa kandidat terhadap sumber resmi dan menentukan
record yang layak dipakai untuk authoring gold queries.

Artefak P0.2 yang dihasilkan secara lokal:

```text
data/interim/legal_term_senses.csv
data/interim/legal_term_senses.parquet
data/interim/quarantined_records.csv
data/interim/quarantined_records.parquet
data/interim/duplicate_records.csv
reports/p0/csv-audit.md
reports/p0/p0-2-run.json
```

Artefak P0.3 yang dihasilkan secara lokal:

```text
data/curated/pilot_terms.csv
data/curated/pilot_terms.parquet
data/curated/pilot_review_queue.csv
manifests/pilot-selection.json
reports/p0/pilot-selection.md
```

Artefak P0.4 yang dihasilkan secara lokal:

```text
data/interim/source_candidates.csv
data/interim/source_candidates.parquet
data/curated/pilot_terms_enriched.csv
data/curated/pilot_terms_enriched.parquet
data/curated/source_review_queue.csv
manifests/source-enrichment.json
reports/p0/source-enrichment.md
```
