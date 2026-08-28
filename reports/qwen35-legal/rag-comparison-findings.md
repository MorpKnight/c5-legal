# Findings: Qwen legal tanpa RAG vs dengan RAG

Tanggal run: 2026-08-28

## Ringkasan

Benchmark ini menjalankan final LoRA adapter Qwen yang sama dalam dua kondisi:

1. `adapter_no_rag`: model menjawab tanpa potongan sumber hukum saat inferensi.
2. `adapter_with_rag`: retriever mencocokkan identitas peraturan dan pasal, lalu memberikan kutipan sumber resmi kepada model.

Full run terdiri dari enam kasus: lima kasus yang memiliki sumber di fixture dan satu kasus pasal yang sengaja tidak tersedia. Decoding dibuat deterministic (`do_sample=false`, `num_beams=1`).

Fixture resmi demonstrasi menggunakan Database Peraturan BPK dan dokumen yang ditautkan untuk [PP Nomor 43 Tahun 2011](https://peraturan.bpk.go.id/Details/5176), [UU Nomor 8 Tahun 1999](https://peraturan.bpk.go.id/Details/45288/uu-no-8-tahun-1999.8Presiden), dan [UU Nomor 27 Tahun 2022](https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022?_thumbnail_id=6900). Fixture ini bukan corpus resmi lengkap.

## Hasil agregat

| Metrik | Tanpa RAG | Dengan RAG |
|---|---:|---:|
| Mean answer screening score | 17,28/100 | 74,61/100 |
| Mean in-scope answer score | 20,73/100 | 69,53/100 |
| Mean reference token-F1 (in-scope) | 0,3907 | 0,5009 |
| Mean anchor recall (in-scope) | 0,1086 | 0,8000 |
| Retrieval hit rate | — | 5/5 |
| Citation/source signal (in-scope) | — | 4/5 |
| Format `[S1]` persis | — | 1/5 |
| Abstention tepat untuk sumber yang tidak ada | 0/1 | 1/1 |
| Generation error atau jawaban kosong | 0 | 0 |

`answer screening score` adalah indikator otomatis untuk penyaringan awal, bukan skor kebenaran hukum. Untuk kasus in-scope, skor ini terdiri dari 65% anchor recall dan 35% reference token-F1. Untuk kasus out-of-scope, skor 100 berarti model melakukan abstention yang sesuai.

## Findings per kasus

| Kasus | Tanpa RAG | Dengan RAG | Temuan |
|---|---|---|---|
| Definisi Perseroan Terbatas, PP 43/2011 Pasal 1 angka 1 | Menjawab dengan definisi lain dan tidak lengkap | Retrieval benar, tetapi generasi berhenti terlalu dini | RAG belum cukup jika decoding berhenti sebelum kutipan selesai |
| Kewajiban informasi, UU 8/1999 Pasal 7 huruf b | Jawaban generik dan tidak lengkap | Menjawab sesuai kutipan | RAG memperbaiki substansi |
| Data spesifik, UU 27/2022 Pasal 4 ayat (2) | Jawaban terpotong | Menyebutkan kategori-kategori sesuai konteks | RAG memperbaiki kelengkapan |
| Pasal 999 UU 27/2022 | Mengarang isi pasal dan mencapai batas token | Menyatakan sumber yang cocok tidak ditemukan | RAG memperbaiki abstention dan mengurangi halusinasi |
| Kewajiban nondiskriminasi, UU 8/1999 Pasal 7 huruf c | Menjawab isi huruf b | Menjawab isi huruf c | Metadata/pasal membantu membedakan chunk yang mirip |
| Klasifikasi data pribadi, UU 27/2022 Pasal 4 ayat (1) | Menghasilkan klasifikasi yang berbeda | Menjawab sesuai dua kategori pada konteks | RAG memperbaiki grounding |

## Kesimpulan

Pada benchmark kecil ini, memasangkan model dengan RAG menghasilkan peningkatan yang nyata: empat dari lima pertanyaan in-scope membaik, jawaban lebih dekat ke kutipan sumber, dan kasus pasal yang tidak ada ditangani dengan abstention.

Format sitasi tidak perlu dijadikan gate utama. Yang penting adalah source signal tersebut menunjuk ke sumber dan pasal yang benar. Di sisi aplikasi, metadata sumber sebaiknya disimpan dan ditampilkan oleh layer RAG, sehingga model boleh menyebut `S1`, nama peraturan, atau tidak menulis marker tertentu tanpa kehilangan provenance.

Namun, hasil ini belum cukup untuk menyatakan model siap untuk penggunaan hukum produksi karena:

- fixture hanya terdiri dari enam chunk;
- satu jawaban RAG masih tidak lengkap;
- currentness, amandemen, dan konflik antarperaturan belum diuji;
- skor otomatis belum menggantikan review ahli hukum.

Rekomendasi berikutnya adalah memperluas corpus resmi, menambahkan validasi identitas pasal dan currentness, memakai fallback extractive ketika jawaban model tidak lengkap, lalu menjalankan evaluasi human-labeled minimal 100--300 pertanyaan.

## Reproduksi

```bash
QWEN_LEGAL_RAG_MODE=full \
  /home/tamaniga34/finetune-env/bin/python \
  notebooks/qwen35_legal_rag_comparison.py
```

Artefak benchmark lokal tidak disimpan ke Git karena berada di luar repository. Notebook, runner, fixture, dan konfigurasi ada di folder `notebooks/`, `data/samples/`, dan `configs/`.
