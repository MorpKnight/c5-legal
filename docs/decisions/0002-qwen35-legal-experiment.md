# ADR 0002: Keep Qwen legal fine-tuning as a separate experimental track

- Status: Accepted
- Date: 2026-08-28

## Context

The local workspace contains a completed Qwen3.5 4B Base LoRA experiment using
an Indonesian legal corpus and an Indonesian regulation QA dataset. The main
repository is currently scoped to the P0 retrieval and source-verification
spike for AMT. The two tracks answer different questions and have different
safety requirements.

## Decision

Store the Qwen experiment in this repository as a reproducibility and review
record, without changing the P0 retrieval contract:

- notebooks and the evaluation runner live under `notebooks/`;
- stable configurations live under `configs/`;
- sanitized run metadata lives under `manifests/`;
- training/evaluation results and the manual review queue live under
  `reports/qwen35-legal/`;
- raw datasets, base-model files, optimizer states, and checkpoints stay out of
  Git;
- the final SFT LoRA adapter is distributed from the public Hugging Face model
  repository documented in the manifests;
- the adapter is an experimental language model, not an authority layer and
  not a legal-advice system.

## Evidence boundary

The full run completed DAPT and SFT at 10,000 steps per stage. The adapter
loaded successfully and generated all 200 sampled evaluation cases without
runtime errors. These checks establish technical reproducibility only. They do
not establish that an answer is legally correct, current, complete, or tied to
the correct regulation.

The QA references contain noisy or fragmentary examples, so automatic token
overlap is retained only as a diagnostic. Legal acceptance requires a separate
expert gold set, source verification, and a retrieval/citation evaluation.

## Consequences

- The repository can be cloned without downloading multi-gigabyte datasets or
  checkpoints.
- The fine-tuned adapter can be evaluated independently from the retrieval
  pipeline.
- A future production path must compare base model, adapter-only, and
  source-grounded RAG on the same expert-reviewed cases.
- A `regulation_key` alone is insufficient as a citation identity when corpus
  rows contain title collisions; stable source identity and version metadata
  are required.
