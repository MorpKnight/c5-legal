# Qwen3.5 Indonesian legal evaluation summary

## Scope

The final evaluation sampled 200 cases from all seven QA test shards. It
scanned 638,610 test rows, collapsed duplicates by `answer_hash`, and generated
with the final SFT adapter using `enable_thinking=false` and `<|im_end|>` as a
stop token. The base model and dataset snapshots were not modified.

## Technical result

| Check | Result |
| --- | ---: |
| Cases generated | 200 / 200 |
| Inference errors | 0 |
| Empty answers | 0 |
| Artifact integrity | passed |
| Dataset-count integrity | passed |
| Generation technical check | passed |
| Mean latency | 3.4885 s |

Automatic diagnostics:

- 32/200 outputs (16%) reached the 256-token limit;
- 14/200 outputs (7%) exceeded the repetition diagnostic threshold;
- mean repeated 6-gram ratio: `0.036841`;
- mean token F1 diagnostic: `0.457898`;
- mean reference-marker recall diagnostic: `0.982729`.

Token overlap is not a legal correctness metric. The sampled QA references
also contain noisy or fragmentary wording, so these numbers are useful for
debugging generation behavior only.

## Qualitative and safety result

Several sampled outputs showed repetition or a regulation/title context that did
not match the reference. This is sufficient to keep the production gate closed.
The current result is:

```text
technical readiness: passed
human legal review: required
retrieval/citation evaluation: not run
production decision: not ready
```

The review queue is available in
[`human_review_queue.csv`](./human_review_queue.csv); reviewers should score
substance, citation identity, completeness, currentness, source grounding, and
appropriate abstention. The raw paired outputs are in
[`model_outputs.jsonl`](./model_outputs.jsonl).

## Required next evaluation

Create an expert-reviewed gold set with authoritative source URLs, regulation
number/year, article, effective-status context, and an answer or abstention
criterion. Compare the base model, adapter, and a source-grounded RAG system on
that same set. The corpus audit also found title collisions under some
`regulation_key` values, so citation identity must include stable source and
version metadata rather than the key alone.
