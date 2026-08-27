# ADR 0001: Bound P0 to corpus and retrieval validation

- Status: Accepted
- Date: 2026-08-27

## Context

AMT membutuhkan Dictionary dan source-grounded Suggestion. Technical spike Qwen generatif telah membuktikan jalur runtime awal, tetapi belum membuktikan bahwa istilah dan sumber hukum dapat ditemukan secara konsisten.

## Decision

P0 dibatasi pada fondasi data dan evaluasi retrieval. P0 akan membandingkan solusi lexical dan semantic pada corpus serta gold set yang sama sebelum ada integrasi produk.

P0.0 menetapkan kontrak eksperimen. P0.1 menyiapkan repository yang reproducible. Audit dan transformasi dataset dimulai pada P0.2.

## Consequences

- AMT tidak menerima corpus atau model baru selama P0.
- Fine-tuning ditunda.
- Raw data dan artefak model tidak masuk Git.
- Setiap sumber harus memiliki provenance dan snapshot yang dikunci.
- Hasil yang baik membuktikan retrieval pada pilot, bukan validitas hukum atau dampak produk.

