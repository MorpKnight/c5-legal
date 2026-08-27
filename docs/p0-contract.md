# P0 Experiment Contract

## Current CBL phase

Act — technical spike and evidence generation.

## Decision blocked

AMT belum dapat memilih lexical retrieval, semantic retrieval, atau hybrid retrieval untuk Dictionary dan Suggestion sampai kualitas pencarian istilah, ketepatan sumber, kemampuan abstain, dan kelayakan runtime lokal diukur pada corpus Indonesia yang sama.

## Given

- Tim memiliki kamus istilah dan pengertian hukum Indonesia sebagai seed data.
- AMT menargetkan Dictionary dan Suggestion, bukan chatbot.
- Suggestion harus tetap dikendalikan pengguna dan menyertakan sumber.
- Runtime aplikasi ditargetkan lokal pada Apple Silicon.

## Assumed

- Pilot 50 istilah cukup untuk membedakan kelemahan utama lexical dan semantic retrieval.
- Deskripsi tanpa nama istilah adalah bentuk query yang representatif untuk reverse dictionary.
- Satu corpus terkurasi dapat menjadi authority layer awal untuk Dictionary dan candidate generation pada Suggestion.

## Needs validation

- Kesesuaian setiap definisi dengan sumber resmi dan status regulasi terkini.
- Hak penggunaan dan distribusi setiap dataset turunan.
- Nilai tambah embedding dibandingkan exact, fuzzy, dan BM25.
- Kecocokan ranking antara model embedding referensi dan kandidat MLX quantized.
- Threshold aman untuk query ambigu dan no-answer.
- Kelayakan latency, memory, dan ukuran artefak pada target Apple Silicon.

## Hypothesis

Corpus legal-term yang bersih, query yang tidak membocorkan istilah, dan retrieval yang tepat dapat menempatkan istilah yang diharapkan dalam lima hasil teratas untuk sekurang-kurangnya 85% query pilot, dengan sumber terverifikasi yang tepat dan tanpa memaksakan jawaban pada query no-answer.

## Artifact

- corpus legal-term terstruktur;
- source/provenance manifest;
- official-source review queue dan registry sumber resmi;
- gold retrieval queries dan locked test split;
- baseline exact, fuzzy, BM25, embedding, dan hybrid bila dibutuhkan;
- laporan kualitas dan runtime;
- keputusan adopt, adapt, defer, atau stop.

## Success signals

- Recall@5 minimal 0,85.
- Mean Reciprocal Rank minimal 0,70.
- False positive pada query no-answer maksimal 0,10.
- Akurasi sumber untuk record berstatus `verified` adalah 1,00.
- Tidak ada source mismatch pada record yang ditampilkan sebagai `verified`.

Threshold ini adalah kriteria technical spike dan dapat direvisi dengan alasan yang dicatat. Threshold bukan bukti validitas atau ketepatan hukum.

## Revise signals

- Satu metode unggul hanya pada query yang membocorkan nama istilah.
- Query parafrasa gagal secara sistematis.
- Ambiguous query dipaksa menjadi satu jawaban.
- Model quantized mengubah ranking secara material.
- Provenance belum cukup untuk memeriksa sumber.

## Stop signals

- Record yang tidak terverifikasi tercampur sebagai sumber resmi.
- Pipeline tidak dapat direproduksi dari snapshot dan manifest yang dikunci.
- Lisensi atau provenance tidak mendukung penggunaan yang direncanakan.
- Retrieval menghasilkan kandidat tanpa sumber yang dapat ditelusuri.

## Deliberately excluded

- perubahan dokumen;
- accept/reject UI;
- LLM-generated legal conclusions;
- fine-tuning;
- full knowledge graph ingestion;
- telemetry dan dokumen pengguna;
- integrasi ke AMT sebelum decision gate.

## Traceability

```text
Evidence: kebutuhan glossary dengan sumber dan keputusan pengguna
  -> Requirement: kandidat istilah harus dapat ditelusuri
  -> Hypothesis: retrieval terukur dapat menemukan istilah dari deskripsi
  -> Artifact: curated corpus + gold queries + benchmark
  -> Test: lexical versus semantic pada pilot yang sama
  -> Decision: adopt, adapt, defer, atau stop
  -> Next question: apakah metode terpilih layak dikemas untuk AMT?
```
