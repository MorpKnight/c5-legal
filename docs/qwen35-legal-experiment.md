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
