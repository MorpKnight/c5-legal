"""Local evaluation harness for the Indonesian legal Qwen adapter.

The evaluator is intentionally conservative: automatic metrics are diagnostics,
not a declaration that a model is legally correct.  It creates a review queue
for a human/legal reviewer and keeps the source datasets read-only.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


SEED = int(os.environ.get('QWEN_LEGAL_EVAL_SEED', '42'))
MODE = os.environ.get('QWEN_LEGAL_EVAL_MODE', 'smoke').strip().lower()
if MODE not in {'smoke', 'full'}:
    raise ValueError(f'QWEN_LEGAL_EVAL_MODE harus smoke atau full, bukan {MODE!r}')

DEFAULT_LIMIT = 8 if MODE == 'smoke' else 200
EVAL_LIMIT = int(os.environ.get('QWEN_LEGAL_EVAL_LIMIT', str(DEFAULT_LIMIT)))
MAX_NEW_TOKENS = int(os.environ.get('QWEN_LEGAL_EVAL_MAX_NEW_TOKENS', '256'))
MAX_INPUT_TOKENS = int(os.environ.get('QWEN_LEGAL_EVAL_MAX_INPUT_TOKENS', '4096'))
ENABLE_THINKING = os.environ.get(
    'QWEN_LEGAL_EVAL_ENABLE_THINKING', '0'
).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
COMPARE_BASELINE = os.environ.get(
    'QWEN_LEGAL_EVAL_COMPARE_BASELINE',
    '1' if MODE == 'smoke' else '0',
).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}

HOME = Path.home()
HF_CACHE = HOME / '.cache' / 'huggingface' / 'hub'
BASE_MODEL = Path(os.environ.get(
    'QWEN_LEGAL_EVAL_BASE_MODEL',
    str(HF_CACHE / 'models--Qwen--Qwen3.5-4B-Base' / 'snapshots' /
        '1001bb4d826a52d1f399e183466143f4da7b741b'),
))
ADAPTER = Path(os.environ.get(
    'QWEN_LEGAL_EVAL_ADAPTER',
    str(Path(__file__).resolve().parents[1] / 'artifacts' / 'local' / 'qwen35_legal_runs' / 'full' / 'sft' / 'final_adapter'),
))
QA_SNAPSHOT = Path(os.environ.get(
    'QWEN_LEGAL_EVAL_QA_SNAPSHOT',
    str(HF_CACHE / 'datasets--morpknight--indonesian-legal-qa-sft' / 'snapshots' /
        '0d25efe8bf09dad69c3544d9bf62036967508bda'),
))
CORPUS_SNAPSHOT = Path(os.environ.get(
    'QWEN_LEGAL_EVAL_CORPUS_SNAPSHOT',
    str(HF_CACHE / 'datasets--morpknight--indonesian-legal-corpus' / 'snapshots' /
        '814f32015b10bf376907aa26ce1c12fe8bef700b'),
))
EXPERT_SET = os.environ.get('QWEN_LEGAL_EVAL_EXPERT_SET', '').strip()
EVAL_ROOT = Path(os.environ.get(
    'QWEN_LEGAL_EVAL_RUN_ROOT',
    str(Path(__file__).resolve().parents[1] / 'artifacts' / 'local' / 'qwen35_legal_eval_runs'),
))
RUN_NAME = os.environ.get(
    'QWEN_LEGAL_EVAL_RUN_NAME',
    datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'),
)
RUN_DIR = EVAL_ROOT / MODE / RUN_NAME
RUN_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_COUNTS = {
    'qa': {'train': 10_576_428, 'validation': 626_393, 'test': 638_610},
    'corpus': {'train': 587_070, 'validation': 30_983, 'test': 23_932},
}
QA_COLUMNS = [
    'id', 'prompt', 'completion', 'regulation_key', 'answer_hash',
    'question_variant_rank', 'token_count', 'source_dataset',
    'source_revision', 'source_row_id',
]
CORPUS_REQUIRED_COLUMNS = [
    'id', 'text', 'regulation_key', 'regulation_type', 'enacting_body',
    'regulation_number', 'year', 'title', 'chapter', 'article', 'domain',
    'chunk_index', 'chunk_count', 'token_count', 'content_hash',
    'source_dataset', 'source_revision', 'source_row_id',
]
LORA_TARGETS = sorted([
    'q_proj', 'k_proj', 'v_proj', 'o_proj',
    'in_proj_qkv', 'in_proj_z', 'out_proj',
    'gate_proj', 'up_proj', 'down_proj',
])


def as_text(value: Any) -> str:
    return '' if value is None else str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding='utf-8',
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def parquet_files(snapshot: Path, split: str) -> list[Path]:
    paths = sorted((snapshot / 'data').glob(f'{split}-*.parquet'))
    if not paths:
        paths = sorted(snapshot.glob(f'**/{split}-*.parquet'))
    if not paths:
        raise FileNotFoundError(f'Tidak ada parquet {split} di {snapshot}')
    return paths


def parquet_count(paths: Iterable[Path]) -> int:
    return sum(pq.ParquetFile(path).metadata.num_rows for path in paths)


def validate_artifacts() -> dict[str, Any]:
    if not BASE_MODEL.is_dir():
        raise FileNotFoundError(f'Base model tidak ditemukan: {BASE_MODEL}')
    if not ADAPTER.is_dir():
        raise FileNotFoundError(f'Final adapter tidak ditemukan: {ADAPTER}')
    for path in (QA_SNAPSHOT, CORPUS_SNAPSHOT):
        if not path.is_dir():
            raise FileNotFoundError(f'Snapshot dataset tidak ditemukan: {path}')

    required_adapter_files = ['adapter_config.json', 'adapter_model.safetensors']
    missing = [name for name in required_adapter_files if not (ADAPTER / name).exists()]
    if missing:
        raise FileNotFoundError(f'File adapter hilang: {missing}')

    adapter_config = json.loads((ADAPTER / 'adapter_config.json').read_text(encoding='utf-8'))
    actual_targets = sorted(as_text(item) for item in adapter_config.get('target_modules', []))
    config_checks = {
        'peft_type': adapter_config.get('peft_type') == 'LORA',
        'task_type': adapter_config.get('task_type') == 'CAUSAL_LM',
        'r': adapter_config.get('r') == 16,
        'lora_alpha': adapter_config.get('lora_alpha') == 32,
        'lora_dropout': adapter_config.get('lora_dropout') == 0.05,
        'target_modules': actual_targets == LORA_TARGETS,
        'bias': adapter_config.get('bias') == 'none',
    }
    if not all(config_checks.values()):
        raise ValueError(f'Konfigurasi adapter tidak sesuai: {config_checks}')

    train_run_dir = ADAPTER.parent.parent
    train_manifest_path = train_run_dir / 'run_manifest.json'
    train_manifest = {}
    if train_manifest_path.exists():
        train_manifest = json.loads(train_manifest_path.read_text(encoding='utf-8'))

    checkpoint = train_run_dir / 'sft' / 'checkpoint-10000'
    artifact = {
        'base_model': str(BASE_MODEL),
        'adapter': str(ADAPTER),
        'adapter_size_bytes': (ADAPTER / 'adapter_model.safetensors').stat().st_size,
        'adapter_sha256': sha256_file(ADAPTER / 'adapter_model.safetensors'),
        'adapter_config_checks': config_checks,
        'last_checkpoint_exists': checkpoint.is_dir(),
        'training_manifest': str(train_manifest_path) if train_manifest else None,
        'training_run_mode': train_manifest.get('run_mode'),
        'training_stages': {
            stage: {
                'status': details.get('status'),
                'global_step': details.get('global_step'),
                'last_checkpoint': details.get('last_checkpoint'),
            }
            for stage, details in train_manifest.get('stages', {}).items()
        },
    }
    print('Artifact check: PASSED')
    print('  final adapter:', ADAPTER)
    print('  adapter size MiB:', round(artifact['adapter_size_bytes'] / 2**20, 2))
    print('  checkpoint-10000 exists:', artifact['last_checkpoint_exists'])
    print('  training manifest status:', artifact['training_stages'])
    return artifact


def reservoir_sample_rows(
    snapshot: Path,
    split: str,
    columns: list[str],
    limit: int,
    seed: int,
    unique_key: str | None = None,
    first_shard_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = parquet_files(snapshot, split)
    all_count = parquet_count(paths)
    selected_paths = paths[:1] if first_shard_only else paths
    rng = random.Random(seed)
    reservoir: list[dict[str, Any]] = []
    seen: set[str] = set()
    candidate_count = 0
    scanned = 0

    for path in selected_paths:
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=4096, columns=columns):
            for row in batch.to_pylist():
                scanned += 1
                if unique_key:
                    key = as_text(row.get(unique_key)) or as_text(row.get('id'))
                    if key in seen:
                        continue
                    seen.add(key)
                candidate_count += 1
                if len(reservoir) < limit:
                    reservoir.append(row)
                else:
                    position = rng.randrange(candidate_count)
                    if position < limit:
                        reservoir[position] = row

    reservoir.sort(key=lambda row: (as_text(row.get(unique_key or 'id')), as_text(row.get('id'))))
    return reservoir, {
        'all_rows': all_count,
        'selected_shards': len(selected_paths),
        'total_shards': len(paths),
        'scanned_rows': scanned,
        'candidate_rows': candidate_count,
        'unique_key': unique_key,
    }


def validate_dataset_counts() -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for name, snapshot in [('qa', QA_SNAPSHOT), ('corpus', CORPUS_SNAPSHOT)]:
        counts[name] = {}
        for split, expected in EXPECTED_COUNTS[name].items():
            actual = parquet_count(parquet_files(snapshot, split))
            if actual != expected:
                raise ValueError(f'{name}/{split}: {actual} rows, expected {expected}')
            counts[name][split] = actual
    print('Dataset count check: PASSED')
    print('  QA rows:', counts['qa'])
    print('  corpus rows:', counts['corpus'])
    return counts


def load_expert_cases(path_text: str) -> list[dict[str, Any]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f'Expert set tidak ditemukan: {path}')
    cases: list[dict[str, Any]] = []
    if path.suffix.lower() == '.jsonl':
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    elif path.suffix.lower() == '.json':
        rows = json.loads(path.read_text(encoding='utf-8'))
    else:
        with path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, 1):
        prompt = as_text(row.get('prompt') or row.get('question')).strip()
        reference = as_text(
            row.get('reference_answer') or row.get('completion') or row.get('answer')
        ).strip()
        if not prompt:
            raise ValueError(f'Expert case {index} tidak memiliki prompt/question')
        cases.append({
            'case_id': as_text(row.get('case_id') or f'expert-{index:05d}'),
            'source_kind': 'expert',
            'prompt': prompt,
            'reference_answer': reference,
            'reference_source': as_text(row.get('reference_source') or row.get('source')),
            'answer_hash': as_text(row.get('answer_hash')),
            'source_row_id': as_text(row.get('source_row_id')),
        })
    return cases


def build_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_shard_only = MODE == 'smoke'
    qa_rows, sampling = reservoir_sample_rows(
        QA_SNAPSHOT,
        'test',
        QA_COLUMNS,
        EVAL_LIMIT,
        SEED,
        unique_key='answer_hash',
        first_shard_only=first_shard_only,
    )
    cases = []
    for index, row in enumerate(qa_rows, 1):
        cases.append({
            'case_id': f'qa-test-{index:05d}',
            'source_kind': 'qa_test',
            'prompt': as_text(row.get('prompt')).strip(),
            'reference_answer': as_text(row.get('completion')).strip(),
            'reference_source': as_text(row.get('regulation_key')),
            'answer_hash': as_text(row.get('answer_hash')),
            'source_row_id': as_text(row.get('source_row_id')),
            'question_variant_rank': row.get('question_variant_rank'),
            'token_count_reference': row.get('token_count'),
            'source_dataset': as_text(row.get('source_dataset')),
            'source_revision': as_text(row.get('source_revision')),
        })

    expert_cases = load_expert_cases(EXPERT_SET)
    cases.extend(expert_cases)
    if not cases:
        raise RuntimeError('Tidak ada evaluation case yang tersedia.')

    print('Evaluation cases:', len(cases))
    print('  QA test cases:', len(qa_rows))
    print('  expert cases:', len(expert_cases))
    print('  QA sampling:', sampling)
    print('  duplicate answer variants collapsed by: answer_hash')
    print('  first prompt:', cases[0]['prompt'][:240])
    return cases, {
        'qa_sampling': sampling,
        'qa_cases': len(qa_rows),
        'expert_cases': len(expert_cases),
        'total_cases': len(cases),
        'deduplicated_by': 'answer_hash',
    }


def audit_corpus_metadata() -> dict[str, Any]:
    paths = parquet_files(CORPUS_SNAPSHOT, 'test')
    schema = set(pq.ParquetFile(paths[0]).schema_arrow.names)
    missing = sorted(set(CORPUS_REQUIRED_COLUMNS) - schema)
    if missing:
        raise ValueError(f'Corpus schema kehilangan kolom: {missing}')

    audit_columns = [
        'text', 'regulation_number', 'year', 'title', 'chapter', 'article',
        'source_dataset', 'source_revision', 'source_row_id',
    ]
    rows, sampling = reservoir_sample_rows(
        CORPUS_SNAPSHOT,
        'test',
        audit_columns,
        min(512, EXPECTED_COUNTS['corpus']['test']),
        SEED + 100,
        first_shard_only=True,
    )
    coverage = {}
    for column in audit_columns:
        nonempty = sum(bool(as_text(row.get(column)).strip()) for row in rows)
        coverage[column] = {
            'nonempty': nonempty,
            'sample_size': len(rows),
            'rate': round(nonempty / len(rows), 4) if rows else 0.0,
        }
    result = {
        'schema_columns': sorted(schema),
        'missing_columns': missing,
        'sample_coverage': coverage,
        'note': 'Ini audit metadata corpus, bukan evaluasi kualitas retrieval.',
    }
    print('Corpus metadata audit: PASSED')
    print('  citation fields sampled:', {
        field: values['rate'] for field, values in coverage.items()
        if field != 'text'
    })
    return result


TOKEN_PATTERN = re.compile(r'[^\W_]+', flags=re.UNICODE)
LEGAL_MARKER_PATTERNS = [
    re.compile(r'\bpasal\s+[0-9]+[a-z]?(?:\s+ayat\s+\([0-9]+\))?', flags=re.IGNORECASE),
    re.compile(r'\b(?:19|20)[0-9]{2}\b'),
]


def normalized_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize('NFKC', as_text(text)).casefold()
    return TOKEN_PATTERN.findall(normalized)


def token_f1(reference: str, prediction: str) -> dict[str, float]:
    reference_tokens = normalized_tokens(reference)
    prediction_tokens = normalized_tokens(prediction)
    if not reference_tokens or not prediction_tokens:
        return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
    overlap = sum((Counter(reference_tokens) & Counter(prediction_tokens)).values())
    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        'precision': round(precision, 6),
        'recall': round(recall, 6),
        'f1': round(f1, 6),
    }


def legal_markers(text: str) -> set[str]:
    normalized = unicodedata.normalize('NFKC', as_text(text)).casefold()
    markers = set()
    for pattern in LEGAL_MARKER_PATTERNS:
        markers.update(' '.join(item.split()) for item in pattern.findall(normalized))
    return markers


def marker_recall(reference: str, prediction: str) -> float:
    expected = legal_markers(reference)
    if not expected:
        return math.nan
    found = legal_markers(prediction)
    return round(len(expected & found) / len(expected), 6)


def repeated_ngram_ratio(text: str, n: int = 6) -> float:
    tokens = normalized_tokens(text)
    if len(tokens) < n * 2:
        return 0.0
    ngrams = [tuple(tokens[index:index + n]) for index in range(len(tokens) - n + 1)]
    repeated = len(ngrams) - len(set(ngrams))
    return round(repeated / len(ngrams), 6)


def generation_prompt(tokenizer: Any, prompt: str) -> dict[str, torch.Tensor]:
    messages = [{'role': 'user', 'content': prompt}]
    template_kwargs = {
        'tokenize': True,
        'add_generation_prompt': True,
        'return_tensors': 'pt',
        'return_dict': True,
        'truncation': True,
        'max_length': MAX_INPUT_TOKENS,
        'enable_thinking': ENABLE_THINKING,
    }
    try:
        encoded = tokenizer.apply_chat_template(messages, **template_kwargs)
    except TypeError:
        template_kwargs.pop('enable_thinking', None)
        template_kwargs.pop('truncation', None)
        template_kwargs.pop('max_length', None)
        encoded = tokenizer.apply_chat_template(messages, **template_kwargs)
    return {key: value.to('cuda:0') for key, value in encoded.items()}


def make_quantization_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )


def load_model(adapter_path: Path | None) -> tuple[Any, Any]:
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = 'right'
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=make_quantization_config(),
        dtype=torch.bfloat16,
        device_map={'': 'cuda:0'},
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    if adapter_path is not None:
        model = PeftModel.from_pretrained(model, str(adapter_path), is_trainable=False)
    model.config.use_cache = True
    model.config.pad_token_id = tokenizer.pad_token_id
    if getattr(model, 'generation_config', None) is not None:
        model.generation_config.pad_token_id = tokenizer.pad_token_id
    model.eval()
    return model, tokenizer


def clean_generated_text(text: str) -> str:
    """Remove protocol markers from the display answer, retaining raw output separately."""
    cleaned = as_text(text).replace('<|im_end|>', '').replace('<|endoftext|>', '')
    if '</think>' in cleaned:
        cleaned = cleaned.split('</think>', 1)[1]
    elif '<think>' in cleaned:
        cleaned = cleaned.split('<think>', 1)[0]
    lines = [
        line for line in cleaned.splitlines()
        if line.strip().casefold() not in {'assistant', 'user'}
    ]
    return '\n'.join(lines).strip()


def generate_one(model: Any, tokenizer: Any, prompt: str) -> dict[str, Any]:
    encoded = generation_prompt(tokenizer, prompt)
    prompt_length = int(encoded['input_ids'].shape[-1])
    eos_token_ids = [int(tokenizer.eos_token_id)] if tokenizer.eos_token_id is not None else []
    im_end_id = tokenizer.convert_tokens_to_ids('<|im_end|>')
    if isinstance(im_end_id, int) and im_end_id >= 0 and im_end_id not in eos_token_ids:
        eos_token_ids.append(im_end_id)
    started = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=eos_token_ids or None,
        )
    elapsed = time.perf_counter() - started
    generated_ids = generated[0][prompt_length:]
    raw_answer = tokenizer.decode(generated_ids, skip_special_tokens=False).strip()
    answer = clean_generated_text(raw_answer)
    generated_tokens = int(generated_ids.shape[-1])
    return {
        'raw_answer': raw_answer,
        'answer': answer,
        'prompt_tokens': prompt_length,
        'generated_tokens': generated_tokens,
        'hit_max_new_tokens': generated_tokens >= MAX_NEW_TOKENS,
        'protocol_marker_count': sum(
            raw_answer.count(marker)
            for marker in ('<|im_start|>', '<think>', '</think>')
        ) + sum(
            line.strip().casefold() in {'assistant', 'user'}
            for line in raw_answer.splitlines()
        ),
        'latency_seconds': round(elapsed, 4),
    }


def evaluate_label(label: str, adapter_path: Path | None, cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    print(f'\nLoading model: {label}')
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    model, tokenizer = load_model(adapter_path)
    outputs: dict[str, dict[str, Any]] = {}
    failures = 0
    try:
        for index, case in enumerate(cases, 1):
            try:
                generated = generate_one(model, tokenizer, case['prompt'])
                lexical = token_f1(case['reference_answer'], generated['answer'])
                generated['token_precision'] = lexical['precision']
                generated['token_recall'] = lexical['recall']
                generated['token_f1'] = lexical['f1']
                generated['reference_marker_recall'] = marker_recall(
                    case['reference_answer'], generated['answer']
                )
                generated['repeated_ngram_ratio'] = repeated_ngram_ratio(generated['answer'])
                generated['error'] = None
            except Exception as exc:  # keep the review queue useful after one bad case
                failures += 1
                generated = {
                    'answer': '',
                    'raw_answer': '',
                    'prompt_tokens': None,
                    'generated_tokens': None,
                    'hit_max_new_tokens': None,
                    'protocol_marker_count': None,
                    'latency_seconds': None,
                    'token_precision': 0.0,
                    'token_recall': 0.0,
                    'token_f1': 0.0,
                    'reference_marker_recall': math.nan,
                    'repeated_ngram_ratio': math.nan,
                    'error': repr(exc),
                }
            outputs[case['case_id']] = generated
            if index == 1 or index == len(cases) or index % 10 == 0:
                print(f'  {label}: {index}/{len(cases)}')
    finally:
        del model, tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    print(f'  {label} failures:', failures)
    return outputs


def summarize_outputs(label: str, outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = list(outputs.values())
    f1_values = [row['token_f1'] for row in rows if row.get('error') is None]
    marker_values = [
        row['reference_marker_recall'] for row in rows
        if row.get('error') is None and not math.isnan(row['reference_marker_recall'])
    ]
    latencies = [row['latency_seconds'] for row in rows if row.get('latency_seconds') is not None]
    summary = {
        'label': label,
        'cases': len(rows),
        'errors': sum(row.get('error') is not None for row in rows),
        'empty_answers': sum(not as_text(row.get('answer')).strip() for row in rows),
        'empty_rate': round(
            sum(not as_text(row.get('answer')).strip() for row in rows) / len(rows), 6
        ) if rows else 0.0,
        'hit_max_new_tokens': sum(bool(row.get('hit_max_new_tokens')) for row in rows),
        'protocol_marker_rows': sum(bool(row.get('protocol_marker_count')) for row in rows),
        'mean_protocol_marker_count': round(statistics.mean([
            row['protocol_marker_count'] for row in rows
            if row.get('protocol_marker_count') is not None
        ]), 4) if any(row.get('protocol_marker_count') is not None for row in rows) else None,
        'repetition_rows': sum(
            row.get('repeated_ngram_ratio', 0.0) >= 0.2 for row in rows
            if row.get('repeated_ngram_ratio') is not None and not math.isnan(row['repeated_ngram_ratio'])
        ),
        'mean_repeated_ngram_ratio': round(statistics.mean([
            row['repeated_ngram_ratio'] for row in rows
            if row.get('repeated_ngram_ratio') is not None and not math.isnan(row['repeated_ngram_ratio'])
        ]), 6) if any(
            row.get('repeated_ngram_ratio') is not None and not math.isnan(row['repeated_ngram_ratio'])
            for row in rows
        ) else None,
        'mean_token_f1_diagnostic': round(statistics.mean(f1_values), 6) if f1_values else 0.0,
        'median_token_f1_diagnostic': round(statistics.median(f1_values), 6) if f1_values else 0.0,
        'mean_reference_marker_recall_diagnostic': round(statistics.mean(marker_values), 6) if marker_values else None,
        'mean_latency_seconds': round(statistics.mean(latencies), 4) if latencies else None,
    }
    return summary


def combine_outputs(
    cases: list[dict[str, Any]],
    outputs_by_label: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    combined = []
    for case in cases:
        row = dict(case)
        for label, outputs in outputs_by_label.items():
            output = outputs[case['case_id']]
            for key, value in output.items():
                row[f'{label}_{key}'] = value
        row['reviewer_substance_correct'] = ''
        row['reviewer_citation_correct'] = ''
        row['reviewer_complete'] = ''
        row['reviewer_current'] = ''
        row['reviewer_grounded'] = ''
        row['reviewer_abstained_appropriately'] = ''
        row['reviewer_notes'] = ''
        combined.append(row)
    return combined


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')


def write_review_csv(path: Path, rows: list[dict[str, Any]], labels: list[str]) -> None:
    base_fields = [
        'case_id', 'source_kind', 'prompt', 'reference_answer', 'reference_source',
        'answer_hash', 'source_row_id', 'question_variant_rank',
        'token_count_reference', 'source_dataset', 'source_revision',
    ]
    generated_fields = []
    for label in labels:
        generated_fields.extend([
            f'{label}_raw_answer', f'{label}_answer', f'{label}_token_f1',
            f'{label}_reference_marker_recall', f'{label}_protocol_marker_count',
            f'{label}_repeated_ngram_ratio',
            f'{label}_generated_tokens', f'{label}_latency_seconds',
            f'{label}_hit_max_new_tokens', f'{label}_error',
        ])
    review_fields = [
        'reviewer_substance_correct', 'reviewer_citation_correct',
        'reviewer_complete', 'reviewer_current', 'reviewer_grounded',
        'reviewer_abstained_appropriately', 'reviewer_notes',
    ]
    fields = base_fields + generated_fields + review_fields
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if EVAL_LIMIT <= 0 or MAX_NEW_TOKENS <= 0:
        raise ValueError('EVAL_LIMIT dan MAX_NEW_TOKENS harus lebih besar dari nol.')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA tidak tersedia; evaluator ini membutuhkan GPU lokal.')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('GPU tidak melaporkan dukungan BF16.')

    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)

    print('=== Qwen Indonesian Legal Evaluation ===')
    print({
        'mode': MODE,
        'eval_limit': EVAL_LIMIT,
        'max_new_tokens': MAX_NEW_TOKENS,
        'compare_baseline': COMPARE_BASELINE,
        'run_dir': str(RUN_DIR),
        'gpu': torch.cuda.get_device_name(0),
    })

    artifact = validate_artifacts()
    dataset_counts = validate_dataset_counts()
    corpus_audit = audit_corpus_metadata()
    cases, sampling = build_cases()

    outputs_by_label: dict[str, dict[str, dict[str, Any]]] = {}
    if COMPARE_BASELINE:
        outputs_by_label['base'] = evaluate_label('base', None, cases)
    outputs_by_label['adapter'] = evaluate_label('adapter', ADAPTER, cases)
    labels = list(outputs_by_label)

    summaries = {
        label: summarize_outputs(label, outputs)
        for label, outputs in outputs_by_label.items()
    }
    combined = combine_outputs(cases, outputs_by_label)
    outputs_path = RUN_DIR / 'model_outputs.jsonl'
    review_path = RUN_DIR / 'human_review_queue.csv'
    write_jsonl(outputs_path, combined)
    write_review_csv(review_path, combined, labels)

    print('\n=== Automatic diagnostics ===')
    for label, summary in summaries.items():
        print(label, summary)
    print('\nThese lexical metrics are diagnostics only; they are not legal correctness scores.')

    technical_pass = all(
        summary['errors'] == 0 and summary['empty_answers'] == 0
        for summary in summaries.values()
    )
    evaluation_manifest = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': MODE,
        'run_dir': str(RUN_DIR),
        'configuration': {
            'seed': SEED,
            'eval_limit': EVAL_LIMIT,
            'max_new_tokens': MAX_NEW_TOKENS,
            'max_input_tokens': MAX_INPUT_TOKENS,
            'enable_thinking': ENABLE_THINKING,
            'compare_baseline': COMPARE_BASELINE,
            'expert_set': EXPERT_SET or None,
        },
        'artifacts': artifact,
        'dataset_counts': dataset_counts,
        'sampling': sampling,
        'corpus_metadata_audit': corpus_audit,
        'automatic_diagnostics': summaries,
        'gates': {
            'artifact_integrity': 'passed',
            'dataset_count_integrity': 'passed',
            'generation_technical_check': 'passed' if technical_pass else 'failed',
            'human_legal_review': 'required',
            'retrieval_quality': 'not_run',
            'production_decision': 'not_ready_without_human_and_RAG_evaluation',
        },
        'outputs': {
            'model_outputs_jsonl': str(outputs_path),
            'human_review_queue_csv': str(review_path),
        },
    }
    manifest_path = RUN_DIR / 'evaluation_manifest.json'
    write_json(manifest_path, evaluation_manifest)

    print('\n=== Evaluation artifacts ===')
    print('Model outputs:', outputs_path)
    print('Human review queue:', review_path)
    print('Evaluation manifest:', manifest_path)
    print('Technical gate:', 'PASSED' if technical_pass else 'FAILED')
    print('Deployment gate: MANUAL REVIEW REQUIRED')


if __name__ == '__main__':
    main()
