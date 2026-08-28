# Qwen3.5 Indonesian legal training summary

## Result

The full run completed successfully with two LoRA stages:

- DAPT: 10,000 steps, 80,000 selected corpus examples, final loss
  `0.9620845905`.
- SFT: 10,000 steps, 80,000 selected QA examples, final loss
  `1.0267998192`.

The complete pinned dataset snapshots were validated before training. The
training run deliberately used bounded 80,000-example subsets per stage; it did
not train over all 10.5 million QA rows.

## Configuration

Training used QLoRA with 4-bit NF4 double quantization, BF16 computation, LoRA
rank 16, alpha 32, dropout 0.05, effective batch size 8, maximum sequence
length 2,048, cosine scheduling, 3% warmup, and checkpoints every 500 steps
with a retention limit of three checkpoints.

The reproducible configuration is in
[`configs/qwen35-legal-training.json`](../../configs/qwen35-legal-training.json).

## Artifact policy

The final SFT adapter is approximately 61 MB and is distributed through the
public Hugging Face model repository. Git contains no base model, dataset,
optimizer state, or checkpoint files. The sanitized provenance record is in
[`manifests/qwen35-legal-training.json`](../../manifests/qwen35-legal-training.json).

Successful training and a non-empty generation are acceptance checks only;
they do not prove legal correctness or currentness.
