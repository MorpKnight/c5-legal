# Findings: benchmark Qwen legal dengan candidate-corpus RAG

Tanggal run: 2026-08-28

## Ringkasan

Benchmark ini membandingkan final LoRA adapter yang sama dalam dua kondisi:

1. `adapter_no_rag`: model menjawab tanpa konteks regulasi saat inferensi.
2. `adapter_with_candidate_rag`: retriever mencocokkan `regulation_key` dan
   pasal, lalu memberikan chunk corpus kepada model.

Corpus lokal pada benchmark ini hanya **candidate corpus**. Ia belum diverifikasi
sebagai sumber resmi, belum menjadi bukti currentness, dan tidak boleh dianggap
sebagai authority hukum.

## Cakupan dan protokol

- QA test yang dipindai: `638.610` baris.
- Corpus yang dipindai: `641.985` baris.
- Cakupan pasangan regulasi/pasal candidate corpus terhadap pasangan unik QA:
  `28,011%`.
- Sampel evaluasi: `100` kasus dengan pasangan tersedia dan `25` kasus tanpa
  pasangan tersedia.
- Total generasi: `250`.
- Decoding deterministic: `do_sample=false`, `num_beams=1`.
- Batas generasi: `256` token; `top_k=4`.
- Error teknis: `0`; jawaban kosong: `0`.

Kasus covered dipakai untuk membandingkan substansi jawaban. Kasus missing
context dipakai terutama untuk menguji perilaku abstention, sehingga nilai F1
missing tidak boleh dibaca sebagai skor kualitas jawaban biasa.

## Hasil otomatis

| Metrik | Tanpa RAG | Candidate RAG |
|---|---:|---:|
| Mean reference token-F1, covered | 0,378115 | **0,539240** |
| Mean reference token-F1, semua kasus | 0,397040 | 0,456790 |
| RAG menang pada kasus covered | — | **65/100** |
| Mean delta RAG - no-RAG, covered | — | **+0,161125** |
| Mean grounded token precision, covered | — | 0,741647 |
| Abstention tepat saat konteks missing | 0/25 | **19/25** |
| Hit batas 256 token, covered | 20/100 | 14/100 |

Bootstrap 95% untuk mean delta covered berada sekitar `+0,0886` sampai
`+0,2301`. Pada 93 kasus dengan satu judul unik per kunci yang dipakai,
Candidate RAG tetap menang `60/93` dengan mean delta `+0,160075`.

Grounding Candidate RAG juga cukup baik sebagai sinyal diagnostik:

- `85/100` jawaban covered memiliki grounded precision minimal `0,5`.
- `67/100` memiliki grounded precision minimal `0,75`.
- Median grounded precision adalah `0,872984`.

## Temuan perilaku

RAG mengurangi keluaran yang tidak relevan atau berulang ketika chunk yang
benar tersedia. Contoh yang menonjol adalah PP 72/2009 Pasal 26: tanpa RAG
model menghasilkan daftar huruf yang tidak relevan, sedangkan Candidate RAG
menghasilkan ketentuan tentang pengumuman jadwal kereta api yang sesuai dengan
chunk yang diambil.

RAG juga lebih aman untuk sumber yang tidak tersedia: 19 dari 25 kasus
melakukan abstention eksplisit. Namun 6 kasus masih menghasilkan jawaban
hukum walaupun tidak ada context, sehingga guardrail di luar model tetap
diperlukan.

Ada 4 dari 100 kasus covered yang justru menghasilkan `[NO_CONTEXT]` walaupun
retrieval menemukan chunk. Ini menunjukkan model belum selalu menggunakan
konteks yang tersedia.

## Isu kualitas corpus

Pada 7 dari 100 pasangan covered, satu kunci `jenis|nomor|tahun + pasal`
memiliki beberapa judul regulasi berbeda. Contohnya `peraturan gubernur|24|2016`
memiliki beberapa judul dari provinsi dan substansi berbeda. Akibatnya,
retrieval berbasis kunci tersebut dapat mengambil dokumen yang salah meskipun
secara format nomor, tahun, dan pasal cocok.

Karena itu, `regulation_key` saat ini belum cukup untuk production retrieval.
Document identity perlu mencakup issuer/daerah, judul kanonik, URL sumber,
versi atau tanggal, dan hash dokumen.

## Kesimpulan dan keputusan

Hasil ini mendukung penggunaan model bersama RAG: pada kasus dengan sumber,
jawaban lebih dekat ke reference dan lebih grounded; pada kasus tanpa sumber,
model lebih sering melakukan abstention. Sinyal ini tetap terlihat setelah
kasus metadata ambigu dipisahkan.

Namun benchmark ini **belum** menyatakan sistem siap untuk penggunaan hukum
produksi. Candidate corpus bukan sumber resmi, F1 bukan penilaian legal,
beberapa jawaban masih terpotong, dan currentness/amandemen belum diuji.

Prioritas berikutnya:

1. Bangun corpus dari sumber resmi dan simpan provenance lengkap.
2. Perbaiki document identity agar issuer/judul tidak bertabrakan.
3. Tambahkan hard guardrail: tanpa context wajib abstain; context ada tetapi
   model abstain dapat masuk ke fallback extractive atau retry.
4. Jalankan evaluasi human-labeled minimal 100--300 pertanyaan dengan penilaian
   substansi, identitas sumber, kelengkapan, currentness, dan grounding.
5. Biarkan application layer menampilkan metadata sumber; format marker sitasi
   dari model tidak dijadikan satu-satunya sumber provenance.

## Artefak dan reproduksi

- Runner: [`qwen35_legal_large_candidate_rag.py`](../../../notebooks/qwen35_legal_large_candidate_rag.py)
- Laporan kasus: [`comparison-report.md`](./comparison-report.md)
- Manifest: [`manifest.json`](./manifest.json)
- Manifest sampling: [`sampling-manifest.json`](./sampling-manifest.json)
- Audit indeks corpus: [`corpus-index-manifest.json`](./corpus-index-manifest.json)
- Output lengkap: [`outputs.jsonl`](./outputs.jsonl)
- Queue review: [`human-review-queue.csv`](./human-review-queue.csv)

Jalankan ulang pada mesin dengan snapshot model dan dataset yang sesuai:

```bash
QWEN_LEGAL_LARGE_MODE=full \
  python notebooks/qwen35_legal_large_candidate_rag.py
```

Artefak model weights dan dataset besar tidak disimpan di repository.
