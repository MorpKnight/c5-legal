---
base_model: Qwen/Qwen3.5-4B-Base
base_model_revision: 1001bb4d826a52d1f399e183466143f4da7b741b
library_name: peft
pipeline_tag: text-generation
tags:
- lora
- qlora
- indonesian
- legal
- qwen
language:
- id
---

# Qwen3.5 4B Indonesian Legal LoRA

Experimental PEFT LoRA adapter for Indonesian legal-language research. This
repository contains adapter weights only; it is not a standalone model. Load
the adapter together with the pinned `Qwen/Qwen3.5-4B-Base` base model.

## Intended use

Use this adapter for controlled research, evaluation, and prototyping of
Indonesian legal language workflows. A production workflow should retrieve and
show current authoritative sources, preserve source identity and version, and
allow a qualified human to review the result.

## Out of scope

Do not use this adapter as an autonomous legal adviser, as a source of current
law without verification, or for automated legal decisions. The adapter may
hallucinate, repeat text, select the wrong regulation, or reproduce noisy
training references.

## Training

The adapter was trained in two stages with QLoRA:

1. DAPT on the `text` column of
   [`morpknight/indonesian-legal-corpus`](https://huggingface.co/datasets/morpknight/indonesian-legal-corpus),
   revision `814f32015b10bf376907aa26ce1c12fe8bef700b`.
2. SFT on `prompt` and `completion` from
   [`morpknight/indonesian-legal-qa-sft`](https://huggingface.co/datasets/morpknight/indonesian-legal-qa-sft),
   revision `0d25efe8bf09dad69c3544d9bf62036967508bda`.

The complete snapshots were validated, while the run used 80,000 selected
training examples per stage and 10,000 steps per stage. It used 4-bit NF4
double quantization, BF16 computation, LoRA rank 16, alpha 32, dropout 0.05,
maximum sequence length 2,048, and effective batch size 8.

## Evaluation status

The final technical evaluation generated 200/200 sampled test cases without
inference errors. However, 16% of outputs reached the generation limit and 7%
triggered a repetition diagnostic. Qualitative inspection found examples with
wrong regulation/title context. Automatic token overlap is only a diagnostic;
it is not a legal correctness score. Human legal review and source-grounded RAG
evaluation are still required.

## Usage

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

base_id = "Qwen/Qwen3.5-4B-Base"
adapter_id = "morpknight/qwen3.5-4b-indonesian-legal-lora"

tokenizer = AutoTokenizer.from_pretrained(base_id)
quantization = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)
base = AutoModelForCausalLM.from_pretrained(
    base_id,
    quantization_config=quantization,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
model = PeftModel.from_pretrained(base, adapter_id)
model.eval()
```

For legal answers, add a retrieval layer backed by verified, current official
sources and require the model to abstain when the source or version cannot be
established.

## Reproducibility

The training and evaluation records are maintained in the
[`MorpKnight/c5-legal`](https://github.com/MorpKnight/c5-legal) repository:

- [`qwen35-legal-training.json`](https://github.com/MorpKnight/c5-legal/blob/main/manifests/qwen35-legal-training.json)
- [`qwen35-legal-evaluation.json`](https://github.com/MorpKnight/c5-legal/blob/main/manifests/qwen35-legal-evaluation.json)
- [`evaluation-summary.md`](https://github.com/MorpKnight/c5-legal/blob/main/reports/qwen35-legal/evaluation-summary.md)

## License and attribution

This adapter is a derivative of the base model and training datasets. Review
the base-model license and both dataset cards before redistribution or
commercial use. No additional license claim is made here.
