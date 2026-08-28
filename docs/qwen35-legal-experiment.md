# Qwen3.5 Indonesian legal experiment

This is a separate generative-model experiment alongside the repository's P0
retrieval work. It uses QLoRA/LoRA on `Qwen/Qwen3.5-4B-Base` in two stages:

1. DAPT on the `text` column of `morpknight/indonesian-legal-corpus`.
2. SFT on `prompt` and `completion`, rendered as user/assistant messages, from
   `morpknight/indonesian-legal-qa-sft`.

The exact revisions, mappings, hyperparameters, and row counts are recorded in
[`configs/qwen35-legal-training.json`](../configs/qwen35-legal-training.json)
and [`manifests/qwen35-legal-training.json`](../manifests/qwen35-legal-training.json).

## Local use

Open [`notebooks/qwen35_indonesian_legal_finetune.ipynb`](../notebooks/qwen35_indonesian_legal_finetune.ipynb)
for the training recipe and
[`notebooks/qwen35_legal_evaluation.ipynb`](../notebooks/qwen35_legal_evaluation.ipynb)
for smoke/full evaluation. The notebooks expect the pinned model and dataset
snapshots to exist in the local Hugging Face cache. Override paths with the
environment variables documented in the notebook/runner when using another
machine.

The evaluation runner is read-only with respect to model and datasets. It
writes only generated evaluation outputs and a blank manual-review queue under
the configured run root.

## RAG comparison

The no-RAG versus official-source RAG benchmark is implemented in
[`notebooks/qwen35_legal_rag_comparison.ipynb`](../notebooks/qwen35_legal_rag_comparison.ipynb)
and [`notebooks/qwen35_legal_rag_comparison.py`](../notebooks/qwen35_legal_rag_comparison.py).
Its results are recorded in
[`reports/qwen35-legal/rag-comparison-findings.md`](../reports/qwen35-legal/rag-comparison-findings.md).

In the six-case demonstration, RAG raised the mean in-scope screening score
from 20.73 to 69.53, improved four of five in-scope answers, and abstained on
the deliberately unavailable pasal. The exact citation marker is not a gate;
source identity, article match, grounding, completeness, and currentness are
more important. The fixture is intentionally small and is not a production
authoritative corpus.

### Benchmark diperluas

Untuk melihat perilaku pada skala yang lebih besar, runner
[`notebooks/qwen35_legal_large_candidate_rag.py`](../notebooks/qwen35_legal_large_candidate_rag.py)
menguji 100 kasus dengan pasangan regulasi/pasal yang ditemukan dan 25 kasus
tanpa pasangan pada candidate corpus. Laporan lengkap, manifest, output, dan
queue review tersedia di
[`reports/qwen35-legal/large-candidate-rag/findings.md`](../reports/qwen35-legal/large-candidate-rag/findings.md).

Pada 100 kasus covered, Candidate RAG meningkatkan mean token-F1 dari `0,378`
menjadi `0,539` dan menang pada `65/100` pasangan. Pada 25 kasus tanpa context,
model melakukan abstention pada `19/25` kasus, sedangkan no-RAG tidak melakukan
abstention. Candidate corpus memiliki coverage hanya `28,011%` terhadap
pasangan unik QA dan ditemukan tujuh pasangan dengan beberapa judul berbeda di
bawah key yang sama; hasil ini karena itu adalah evidence perilaku, bukan
validasi legal atau official-source retrieval.

## Distribution

The Git repository stores code, notebooks, configuration, manifests, and
reviewable outputs. The LoRA weights are not stored in Git. The public adapter
is published at
[`morpknight/qwen3.5-4b-indonesian-legal-lora`](https://huggingface.co/morpknight/qwen3.5-4b-indonesian-legal-lora)
and must be loaded together with the pinned base model.

## Readiness gate

The completed technical evaluation is documented in
[`reports/qwen35-legal/evaluation-summary.md`](../reports/qwen35-legal/evaluation-summary.md).
The current status is suitable for controlled internal evaluation only. Before
any user-facing legal workflow, reviewers must assess substance, citation,
completeness, currentness, grounding, and appropriate abstention against
authoritative sources. The model must not be treated as a substitute for legal
professionals or current official publications.
