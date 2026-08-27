# c5-model

`c5-model` adalah workspace eksperimen data dan retrieval untuk fitur Dictionary dan Suggestion pada AMT. Workspace ini dipisahkan dari aplikasi agar data mentah, eksperimen model, dan artefak evaluasi tidak membebani repository aplikasi.

## Status

- P0.0 — kontrak eksperimen: **selesai**
- P0.1 — scaffold reproducible: **selesai**
- P0.2 — audit dan normalisasi kamus: **belum dimulai**

Tidak ada dataset yang diunduh, dinormalisasi, atau di-embed pada P0.0–P0.1.

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

## Data handling

- Data mentah tidak diubah di tempat.
- File besar tidak dimasukkan ke Git.
- Setiap sumber harus memiliki revision atau snapshot identifier dan checksum sebelum diproses.
- `verified` hanya boleh diberikan setelah sumber resmi ditinjau.
- Data dari Hugging Face diperlakukan sebagai kandidat corpus, bukan otoritas hukum.
- Tidak ada dokumen pengguna AMT yang digunakan dalam P0.

## Tahap berikutnya

P0.2 akan mengaudit dan menormalisasi `kamus_hukum.csv`. Tahap tersebut baru dimulai setelah review scaffold ini.

