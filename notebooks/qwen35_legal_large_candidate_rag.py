"""Larger paired evaluation: Qwen legal with and without candidate-corpus RAG.

This benchmark deliberately does *not* call the Hugging Face legal corpus an
official authority.  The earlier six-case official-source fixture is still the
right provenance test.  This runner scales the behavioral comparison using the
QA test split and the locally cached legal corpus as a candidate retrieval
corpus, then reports coverage and missing-context abstention separately.

Defaults:
    smoke: 8 candidate-corpus-covered cases + 4 missing-context cases
    full: 100 covered cases + 25 missing-context cases

Examples:
    python notebooks/qwen35_legal_large_candidate_rag.py
    QWEN_LEGAL_LARGE_MODE=full python notebooks/qwen35_legal_large_candidate_rag.py
    QWEN_LEGAL_LARGE_MODE=full QWEN_LEGAL_LARGE_COVERED_LIMIT=200 \
        QWEN_LEGAL_LARGE_MISSING_LIMIT=50 \
        python notebooks/qwen35_legal_large_candidate_rag.py
"""

from __future__ import annotations

import csv
import gc
import hashlib
import heapq
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq
import torch


# Reuse the tested local Transformers/QLoRA loader and generation protocol from
# the small official-source benchmark.  Environment variables are set before
# import so the shared generation limits can still be overridden.
os.environ.setdefault(
    'QWEN_LEGAL_EVAL_BASE_MODEL',
    os.environ.get(
        'QWEN_LEGAL_LARGE_BASE_MODEL',
        '/home/tamaniga34/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B-Base/snapshots/1001bb4d826a52d1f399e183466143f4da7b741b',
    ),
)
os.environ.setdefault(
    'QWEN_LEGAL_EVAL_ADAPTER',
    os.environ.get(
        'QWEN_LEGAL_LARGE_ADAPTER',
        '/home/tamaniga34/notebooks/qwen35_legal_runs/full/sft/final_adapter',
    ),
)
os.environ.setdefault(
    'QWEN_LEGAL_EVAL_MAX_NEW_TOKENS',
    os.environ.get('QWEN_LEGAL_LARGE_MAX_NEW_TOKENS', '256'),
)
os.environ.setdefault(
    'QWEN_LEGAL_EVAL_MAX_INPUT_TOKENS',
    os.environ.get('QWEN_LEGAL_LARGE_MAX_INPUT_TOKENS', '4096'),
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qwen35_legal_rag_comparison import (  # noqa: E402
    abstained_appropriately,
    content_tokens,
    generate_one,
    grounded_token_precision,
    load_model,
    normalized_text,
    normalized_tokens,
    token_f1,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODE = os.environ.get('QWEN_LEGAL_LARGE_MODE', 'smoke').strip().lower()
if MODE not in {'smoke', 'full'}:
    raise ValueError(f'MODE harus smoke atau full, bukan {MODE!r}')

HOME = Path.home()
HF_CACHE = HOME / '.cache' / 'huggingface' / 'hub'
QA_SNAPSHOT = Path(os.environ.get(
    'QWEN_LEGAL_LARGE_QA_SNAPSHOT',
    str(HF_CACHE / 'datasets--morpknight--indonesian-legal-qa-sft' / 'snapshots' /
        '0d25efe8bf09dad69c3544d9bf62036967508bda'),
))
CORPUS_SNAPSHOT = Path(os.environ.get(
    'QWEN_LEGAL_LARGE_CORPUS_SNAPSHOT',
    str(HF_CACHE / 'datasets--morpknight--indonesian-legal-corpus' / 'snapshots' /
        '814f32015b10bf376907aa26ce1c12fe8bef700b'),
))
RUN_ROOT = Path(os.environ.get(
    'QWEN_LEGAL_LARGE_RUN_ROOT',
    '/home/tamaniga34/notebooks/qwen35_legal_large_rag_runs',
))
RUN_NAME = os.environ.get(
    'QWEN_LEGAL_LARGE_RUN_NAME',
    datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'),
)
RUN_DIR = RUN_ROOT / MODE / RUN_NAME
SEED = int(os.environ.get('QWEN_LEGAL_LARGE_SEED', '42'))
TOP_K = int(os.environ.get('QWEN_LEGAL_LARGE_TOP_K', '4'))
CONTEXT_MAX_CHARS = int(os.environ.get('QWEN_LEGAL_LARGE_CONTEXT_MAX_CHARS', '14000'))
PREPARE_ONLY = os.environ.get(
    'QWEN_LEGAL_LARGE_PREPARE_ONLY', '0'
).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
if MODE == 'smoke':
    DEFAULT_COVERED = 8
    DEFAULT_MISSING = 4
else:
    DEFAULT_COVERED = 100
    DEFAULT_MISSING = 25
COVERED_LIMIT = int(os.environ.get('QWEN_LEGAL_LARGE_COVERED_LIMIT', str(DEFAULT_COVERED)))
MISSING_LIMIT = int(os.environ.get('QWEN_LEGAL_LARGE_MISSING_LIMIT', str(DEFAULT_MISSING)))

ARTICLE_BASE_PATTERN = re.compile(r'pasal\s+(\d+[a-z]?)', flags=re.IGNORECASE)
REGULATION_KEY_PATTERN = re.compile(
    r'^(?P<kind>[^|]+)\|(?P<number>[^|]+)\|(?P<year>\d{4})$'
)
CITATION_PATTERN = re.compile(r'(?:\[\s*c1\s*\]|\bc1\b)', flags=re.IGNORECASE)
LEGAL_MARKER_PATTERNS = [
    re.compile(r'\bpasal\s+[0-9]+[a-z]?(?:\s+ayat\s+\([0-9]+\))?', flags=re.IGNORECASE),
    re.compile(r'\b(?:19|20)[0-9]{2}\b'),
]


def as_text(value: Any) -> str:
    return '' if value is None else str(value)


def norm(value: Any) -> str:
    return normalized_text(value)


def article_base(value: Any) -> str | None:
    match = ARTICLE_BASE_PATTERN.search(norm(value))
    return match.group(1) if match else None


def parse_regulation_key(value: Any) -> tuple[str, str, int] | None:
    text = norm(value)
    match = REGULATION_KEY_PATTERN.match(text)
    if not match or text.startswith('answer:'):
        return None
    return match.group('kind'), match.group('number'), int(match.group('year'))


def legal_markers(text: str) -> set[str]:
    normalized = norm(text)
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


def parquet_files(snapshot: Path, splits: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for split in splits:
        paths.extend(sorted((snapshot / 'data').glob(f'{split}-*.parquet')))
    if not paths:
        raise FileNotFoundError(f'Tidak ada parquet di {snapshot}')
    return paths


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding='utf-8',
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')


def push_priority_sample(
    heap: list[tuple[int, int, dict[str, Any]]],
    limit: int,
    priority: int,
    serial: int,
    row: dict[str, Any],
) -> None:
    # The heap root is the currently worst (largest) priority because the
    # stored value is negative.  This gives a deterministic random sample
    # without retaining hundreds of thousands of QA rows in memory.
    item = (-priority, serial, row)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif priority < -heap[0][0]:
        heapq.heapreplace(heap, item)


def select_qa_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    corpus_pairs, corpus_stats = scan_corpus_pairs()
    covered_heap: list[tuple[int, int, dict[str, Any]]] = []
    missing_heap: list[tuple[int, int, dict[str, Any]]] = []
    seen_pairs = {'covered': set(), 'missing': set()}
    unique_pair_counts = Counter()
    total_rows = 0
    parseable_key_rows = 0
    parseable_article_rows = 0
    serial = 0
    for path in parquet_files(QA_SNAPSHOT, ['test']):
        parquet = pq.ParquetFile(path)
        columns = [
            'id', 'prompt', 'completion', 'regulation_key', 'answer_hash',
            'question_variant_rank', 'token_count', 'source_dataset',
            'source_revision', 'source_row_id',
        ]
        for batch in parquet.iter_batches(batch_size=8192, columns=columns):
            for raw in batch.to_pylist():
                total_rows += 1
                prompt = as_text(raw.get('prompt')).strip()
                completion = as_text(raw.get('completion')).strip()
                parsed_key = parse_regulation_key(raw.get('regulation_key'))
                if parsed_key:
                    parseable_key_rows += 1
                query_article = article_base(prompt)
                if query_article:
                    parseable_article_rows += 1
                if not prompt or len(completion) < 20 or not parsed_key or not query_article:
                    continue
                pair = (norm(raw['regulation_key']), query_article)
                available = pair in corpus_pairs
                bucket = 'covered' if available else 'missing'
                if pair in seen_pairs[bucket]:
                    continue
                seen_pairs[bucket].add(pair)
                unique_pair_counts[bucket] += 1
                serial += 1
                candidate = {
                    'case_id': '',
                    'prompt': prompt,
                    'reference_answer': completion,
                    'regulation_key': norm(raw['regulation_key']),
                    'answer_hash': as_text(raw.get('answer_hash')),
                    'question_variant_rank': raw.get('question_variant_rank'),
                    'token_count_reference': raw.get('token_count'),
                    'source_dataset': as_text(raw.get('source_dataset')),
                    'source_revision': as_text(raw.get('source_revision')),
                    'source_row_id': as_text(raw.get('source_row_id')),
                    'query_article': f'Pasal {query_article}',
                    'article_base': query_article,
                    'source_available_in_candidate_corpus': available,
                    'candidate_pair': [pair[0], pair[1]],
                }
                digest = hashlib.sha256(
                    f'{SEED}:{bucket}:{pair[0]}:{pair[1]}'.encode('utf-8')
                ).digest()
                priority = int.from_bytes(digest[:8], 'big')
                if available:
                    push_priority_sample(covered_heap, COVERED_LIMIT, priority, serial, candidate)
                else:
                    push_priority_sample(missing_heap, MISSING_LIMIT, priority, serial, candidate)

    covered = [item[2] for item in sorted(covered_heap, key=lambda item: (item[0], item[1]))]
    missing = [item[2] for item in sorted(missing_heap, key=lambda item: (item[0], item[1]))]
    cases = []
    for index, case in enumerate(covered, 1):
        case['case_id'] = f'qa-covered-{index:04d}'
        cases.append(case)
    for index, case in enumerate(missing, 1):
        case['case_id'] = f'qa-missing-{index:04d}'
        cases.append(case)
    if len(covered) < COVERED_LIMIT:
        raise RuntimeError(
            f'Hanya menemukan {len(covered)} covered pair, diminta {COVERED_LIMIT}.'
        )
    if len(missing) < MISSING_LIMIT:
        raise RuntimeError(
            f'Hanya menemukan {len(missing)} missing pair, diminta {MISSING_LIMIT}.'
        )
    selection = {
        'qa_split': 'test',
        'qa_total_rows_scanned': total_rows,
        'qa_parseable_regulation_key_rows': parseable_key_rows,
        'qa_parseable_article_rows': parseable_article_rows,
        'unique_pair_counts': dict(unique_pair_counts),
        'selected_counts': {'covered': len(covered), 'missing': len(missing)},
        'candidate_corpus_pair_count': len(corpus_pairs),
        'candidate_corpus_scan': corpus_stats,
        'candidate_pair_coverage_over_unique_qa_pairs': round(
            unique_pair_counts['covered'] /
            max(1, unique_pair_counts['covered'] + unique_pair_counts['missing']),
            6,
        ),
    }
    return cases, selection


def scan_corpus_pairs() -> tuple[set[tuple[str, str]], dict[str, Any]]:
    pairs: set[tuple[str, str]] = set()
    rows = 0
    for path in parquet_files(CORPUS_SNAPSHOT, ['train', 'validation', 'test']):
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(
            batch_size=8192,
            columns=['regulation_key', 'article'],
        ):
            for raw in batch.to_pylist():
                rows += 1
                key = parse_regulation_key(raw.get('regulation_key'))
                art = article_base(raw.get('article'))
                if key and art:
                    pairs.add((norm(raw['regulation_key']), art))
    return pairs, {
        'corpus_rows_scanned': rows,
        'corpus_unique_regulation_article_pairs': len(pairs),
    }


def load_corpus_index(cases: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any]]:
    target_pairs = {tuple(case['candidate_pair']) for case in cases if case['source_available_in_candidate_corpus']}
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    rows_scanned = 0
    rows_kept = 0
    columns = [
        'id', 'text', 'regulation_key', 'regulation_type', 'enacting_body',
        'regulation_number', 'year', 'title', 'chapter', 'article', 'domain',
        'chunk_index', 'chunk_count', 'token_count', 'content_hash',
        'source_dataset', 'source_revision', 'source_row_id',
    ]
    for path in parquet_files(CORPUS_SNAPSHOT, ['train', 'validation', 'test']):
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=4096, columns=columns):
            for raw in batch.to_pylist():
                rows_scanned += 1
                key = parse_regulation_key(raw.get('regulation_key'))
                art = article_base(raw.get('article'))
                if not key or not art:
                    continue
                pair = (norm(raw['regulation_key']), art)
                if pair not in target_pairs:
                    continue
                source_id = as_text(raw.get('id')) or as_text(raw.get('content_hash'))
                index[pair].append({
                    'source_id': source_id,
                    'text': as_text(raw.get('text')),
                    'regulation_key': norm(raw.get('regulation_key')),
                    'regulation_type': as_text(raw.get('regulation_type')),
                    'regulation_number': as_text(raw.get('regulation_number')),
                    'year': as_text(raw.get('year')),
                    'title': as_text(raw.get('title')),
                    'chapter': as_text(raw.get('chapter')),
                    'article': as_text(raw.get('article')),
                    'domain': as_text(raw.get('domain')),
                    'chunk_index': raw.get('chunk_index'),
                    'chunk_count': raw.get('chunk_count'),
                    'token_count': raw.get('token_count'),
                    'source_dataset': as_text(raw.get('source_dataset')),
                    'source_revision': as_text(raw.get('source_revision')),
                    'source_row_id': as_text(raw.get('source_row_id')),
                })
                rows_kept += 1
    for pair, rows in index.items():
        deduped = {row['source_id']: row for row in rows}
        index[pair] = sorted(
            deduped.values(),
            key=lambda row: (
                int(row['chunk_index']) if as_text(row['chunk_index']).isdigit() else 0,
                row['source_id'],
            ),
        )
    title_collision_examples = []
    pairs_with_multiple_titles = 0
    for pair, rows in sorted(index.items()):
        titles_by_normalized = {}
        for row in rows:
            title = as_text(row.get('title')).strip()
            if title:
                titles_by_normalized.setdefault(norm(title), title)
        if len(titles_by_normalized) > 1:
            pairs_with_multiple_titles += 1
            if len(title_collision_examples) < 10:
                title_collision_examples.append({
                    'regulation_key': pair[0],
                    'article_base': pair[1],
                    'titles': sorted(titles_by_normalized.values())[:10],
                    'chunk_count': len(rows),
                })
    return dict(index), {
        'target_pairs': len(target_pairs),
        'corpus_rows_scanned': rows_scanned,
        'corpus_rows_kept_for_selected_pairs': rows_kept,
        'indexed_pairs': len(index),
        'indexed_chunks': sum(len(rows) for rows in index.values()),
        'pairs_with_multiple_titles': pairs_with_multiple_titles,
        'title_collision_examples': title_collision_examples,
    }


def retrieve(case: dict[str, Any], index: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    pair = tuple(case['candidate_pair'])
    candidates = list(index.get(pair, []))
    if not candidates:
        return {
            'status': 'not_found',
            'hits': [],
            'candidate_chunks': 0,
            'retrieval_coverage': 0.0,
        }
    query_terms = set(content_tokens(case['prompt']))
    scored = []
    for row in candidates:
        row_terms = set(content_tokens(
            f"{row['title']} {row['article']} {row['text']}"
        ))
        overlap = len(query_terms & row_terms)
        chunk_index = int(row['chunk_index']) if as_text(row['chunk_index']).isdigit() else 0
        scored.append((overlap, chunk_index, row))
    # Query identity is exact; lexical overlap only orders chunks within the
    # matched article.  The article match itself is the important gate.
    scored.sort(key=lambda item: (-item[0], item[1], item[2]['source_id']))
    hits = [item[2] for item in scored[:TOP_K]]
    return {
        'status': 'found',
        'hits': hits,
        'candidate_chunks': len(candidates),
        'retrieval_coverage': round(len(hits) / len(candidates), 6),
    }


def render_context(case: dict[str, Any], retrieval: dict[str, Any]) -> tuple[str, bool]:
    if not retrieval['hits']:
        return (
            '[NO_CONTEXT]\n'
            'Tidak ada chunk dari candidate corpus untuk identitas peraturan dan pasal ini. '
            'Jangan menebak isi pasal.',
            False,
        )
    blocks = []
    remaining = CONTEXT_MAX_CHARS
    truncated = False
    for index, row in enumerate(retrieval['hits'], 1):
        prefix = (
            f"[C{index}]\n"
            f"Candidate corpus record: {row['regulation_type']} Nomor {row['regulation_number']} "
            f"Tahun {row['year']}\n"
            f"Judul: {row['title']}\n"
            f"Ketentuan: {row['article']}\n"
            f"Chunk: {row['chunk_index']} dari {row['chunk_count']}\n"
            'Teks: '
        )
        if remaining <= len(prefix) + 20:
            truncated = True
            break
        text_budget = min(5000, remaining - len(prefix) - 2)
        text = row['text'][:text_budget]
        if len(text) < len(row['text']):
            truncated = True
        blocks.append(prefix + text)
        remaining -= len(prefix) + len(text) + 2
    if truncated:
        blocks.append('[CONTEXT_TRUNCATED]')
    return '\n\n'.join(blocks), truncated


def make_no_rag_prompt(question: str) -> str:
    return (
        'Jawab pertanyaan hukum Indonesia berikut berdasarkan pengetahuan model. '
        'Jawab langsung. Jika tidak yakin, nyatakan keterbatasan dan jangan mengarang bunyi pasal.\n\n'
        f'Pertanyaan:\n{question}'
    )


def make_candidate_rag_prompt(question: str, context: str) -> str:
    return (
        'Jawab pertanyaan hukum Indonesia berikut HANYA berdasarkan konteks candidate corpus '
        'yang diberikan. Candidate corpus ini bukan jaminan sumber resmi terkini. Jika konteks '
        'tidak memuat ketentuan yang diminta atau bertanda [NO_CONTEXT], katakan bahwa sumber '
        'yang cocok tidak ditemukan dan jangan menebak. Jika menjawab dari konteks, boleh '
        'menyebut C1 atau nama peraturan; format sitasi tidak harus khusus.\n\n'
        f'KONTEKS:\n{context}\n\n'
        f'PERTANYAAN:\n{question}'
    )


def candidate_citation_present(answer: str) -> bool:
    return bool(CITATION_PATTERN.search(answer))


def candidate_abstained_appropriately(answer: str) -> bool:
    # The model may copy the explicit control token supplied in the prompt.
    # Treat it as a safe abstention signal, while keeping the human-readable
    # phrase checks from the official-source runner as valid alternatives.
    return '[no_context]' in norm(answer) or bool(abstained_appropriately(answer, True))


def score_output(
    output: dict[str, Any],
    case: dict[str, Any],
    context: str,
    retrieval: dict[str, Any],
    *,
    rag: bool,
) -> dict[str, Any]:
    answer = as_text(output.get('answer'))
    reference = as_text(case['reference_answer'])
    lexical = token_f1(reference, answer)
    marker = marker_recall(reference, answer)
    source_available = bool(case['source_available_in_candidate_corpus'])
    abstention = (
        candidate_abstained_appropriately(answer)
        if not source_available else None
    )
    grounded = grounded_token_precision(answer, context) if rag and retrieval['hits'] else None
    citation = candidate_citation_present(answer) if rag else None
    return {
        **output,
        'reference_token_precision': lexical['precision'],
        'reference_token_recall': lexical['recall'],
        'reference_token_f1': lexical['f1'],
        'reference_marker_recall': marker if not math.isnan(marker) else None,
        'grounded_token_precision': grounded,
        'citation_signal_present': citation,
        'retrieval_hit': bool(retrieval['hits']),
        'appropriate_abstention_when_candidate_source_missing': abstention,
        'repeated_ngram_ratio': repeated_ngram_ratio(answer),
        'lexical_screening_score': round(100 * lexical['f1'], 2),
    }


def error_output(exc: Exception, *, rag: bool, source_available: bool) -> dict[str, Any]:
    return {
        'raw_answer': '',
        'answer': '',
        'prompt_tokens': None,
        'generated_tokens': None,
        'hit_max_new_tokens': None,
        'protocol_marker_count': None,
        'latency_seconds': None,
        'error': repr(exc),
        'reference_token_precision': 0.0,
        'reference_token_recall': 0.0,
        'reference_token_f1': 0.0,
        'reference_marker_recall': None,
        'grounded_token_precision': None,
        'citation_signal_present': False if rag else None,
        'retrieval_hit': False,
        'appropriate_abstention_when_candidate_source_missing': None if source_available else False,
        'repeated_ngram_ratio': None,
        'lexical_screening_score': 0.0,
    }


def mean_value(items: list[dict[str, Any]], key: str) -> float | None:
    values = [item[key] for item in items if item.get(key) is not None]
    return round(statistics.mean(values), 6) if values else None


def summarize(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    outputs = [row[label] for row in rows]
    successful = [item for item in outputs if not item.get('error')]
    covered = [
        item for row, item in zip(rows, outputs)
        if row['source_available_in_candidate_corpus'] and not item.get('error')
    ]
    missing = [
        item for row, item in zip(rows, outputs)
        if not row['source_available_in_candidate_corpus'] and not item.get('error')
    ]
    result = {
        'label': label,
        'cases': len(rows),
        'covered_cases': len(covered),
        'missing_context_cases': len(missing),
        'errors': sum(bool(item.get('error')) for item in outputs),
        'empty_answers': sum(not as_text(item.get('answer')).strip() for item in outputs),
        'hit_max_new_tokens': sum(bool(item.get('hit_max_new_tokens')) for item in outputs),
        'mean_latency_seconds': mean_value(successful, 'latency_seconds'),
        'mean_reference_token_f1_all': mean_value(successful, 'reference_token_f1'),
        'mean_reference_token_f1_covered': mean_value(covered, 'reference_token_f1'),
        'mean_reference_token_f1_missing_context': mean_value(missing, 'reference_token_f1'),
        'mean_lexical_screening_score_covered': mean_value(covered, 'lexical_screening_score'),
        'mean_reference_marker_recall_covered': mean_value(covered, 'reference_marker_recall'),
        'mean_grounded_token_precision_covered': mean_value(covered, 'grounded_token_precision'),
        'mean_repeated_ngram_ratio': mean_value(successful, 'repeated_ngram_ratio'),
        'retrieval_hit_rate_covered': (
            round(sum(bool(item.get('retrieval_hit')) for item in covered) / len(covered), 6)
            if label == 'adapter_with_candidate_rag' and covered else None
        ),
        'citation_signal_rate_covered': (
            round(sum(bool(item.get('citation_signal_present')) for item in covered) / len(covered), 6)
            if label == 'adapter_with_candidate_rag' and covered else None
        ),
        'appropriate_abstention_rate_missing_context': (
            round(
                sum(bool(item.get('appropriate_abstention_when_candidate_source_missing')) for item in missing)
                / len(missing),
                6,
            ) if missing else None
        ),
    }
    return result


def compare_paired(rows: list[dict[str, Any]]) -> dict[str, Any]:
    covered = [row for row in rows if row['source_available_in_candidate_corpus']]
    deltas = []
    wins = losses = ties = 0
    for row in covered:
        no_rag = row['adapter_no_rag']
        rag = row['adapter_with_candidate_rag']
        if no_rag.get('error') or rag.get('error'):
            continue
        delta = rag['reference_token_f1'] - no_rag['reference_token_f1']
        deltas.append(delta)
        if delta > 1e-9:
            wins += 1
        elif delta < -1e-9:
            losses += 1
        else:
            ties += 1
    return {
        'covered_pairs_compared': len(deltas),
        'rag_f1_wins': wins,
        'no_rag_f1_wins': losses,
        'ties': ties,
        'rag_win_rate': round(wins / len(deltas), 6) if deltas else None,
        'mean_rag_minus_no_rag_f1': round(statistics.mean(deltas), 6) if deltas else None,
        'median_rag_minus_no_rag_f1': round(statistics.median(deltas), 6) if deltas else None,
    }


def write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        'case_id', 'source_available_in_candidate_corpus', 'regulation_key',
        'query_article', 'prompt', 'reference_answer', 'retrieval_status',
        'candidate_chunk_count', 'retrieved_source_ids', 'adapter_no_rag_answer',
        'adapter_with_candidate_rag_answer', 'no_rag_reference_token_f1',
        'rag_reference_token_f1', 'rag_grounded_token_precision',
        'rag_citation_signal_present',
        'rag_appropriate_abstention_when_source_missing',
        'reviewer_no_rag_rating_1_to_5', 'reviewer_rag_rating_1_to_5',
        'reviewer_preferred_condition', 'reviewer_substance_correct',
        'reviewer_grounded', 'reviewer_current', 'reviewer_notes',
    ]
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({
                'case_id': row['case_id'],
                'source_available_in_candidate_corpus': row['source_available_in_candidate_corpus'],
                'regulation_key': row['regulation_key'],
                'query_article': row['query_article'],
                'prompt': row['prompt'],
                'reference_answer': row['reference_answer'],
                'retrieval_status': row['retrieval']['status'],
                'candidate_chunk_count': row['retrieval']['candidate_chunks'],
                'retrieved_source_ids': ','.join(row['retrieved_source_ids']),
                'adapter_no_rag_answer': row['adapter_no_rag']['answer'],
                'adapter_with_candidate_rag_answer': row['adapter_with_candidate_rag']['answer'],
                'no_rag_reference_token_f1': row['adapter_no_rag']['reference_token_f1'],
                'rag_reference_token_f1': row['adapter_with_candidate_rag']['reference_token_f1'],
                'rag_grounded_token_precision': row['adapter_with_candidate_rag']['grounded_token_precision'],
                'rag_citation_signal_present': row['adapter_with_candidate_rag']['citation_signal_present'],
                'rag_appropriate_abstention_when_source_missing': row['adapter_with_candidate_rag']['appropriate_abstention_when_candidate_source_missing'],
                'reviewer_no_rag_rating_1_to_5': '',
                'reviewer_rag_rating_1_to_5': '',
                'reviewer_preferred_condition': '',
                'reviewer_substance_correct': '',
                'reviewer_grounded': '',
                'reviewer_current': '',
                'reviewer_notes': '',
            })


def write_report(
    path: Path,
    rows: list[dict[str, Any]],
    summaries: dict[str, Any],
    paired: dict[str, Any],
    selection: dict[str, Any],
    corpus_index_stats: dict[str, Any],
) -> None:
    lines = [
        '# Larger candidate-corpus RAG benchmark',
        '',
        '> This benchmark is a behavioral comparison. The local legal corpus is a candidate retrieval corpus, not a verified official authority.',
        '',
        f'- Mode: `{MODE}`',
        f'- Cases: `{len(rows)}` ({selection["selected_counts"]["covered"]} covered + {selection["selected_counts"]["missing"]} missing-context)',
        f'- Candidate pair coverage in QA test: `{selection["candidate_pair_coverage_over_unique_qa_pairs"]}`',
        f'- Indexed chunks for selected covered pairs: `{corpus_index_stats["indexed_chunks"]}`',
        f'- Selected pairs with multiple distinct titles: `{corpus_index_stats.get("pairs_with_multiple_titles", 0)}`',
        '',
        '## Aggregate diagnostics',
        '',
        '| Condition | F1 all | F1 covered | F1 missing | Grounded precision | Missing-context abstention |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for label, summary in summaries.items():
        lines.append(
            f"| {label} | {summary['mean_reference_token_f1_all']} "
            f"| {summary['mean_reference_token_f1_covered']} "
            f"| {summary['mean_reference_token_f1_missing_context']} "
            f"| {summary['mean_grounded_token_precision_covered']} "
            f"| {summary['appropriate_abstention_rate_missing_context']} |"
        )
    lines.extend([
        '',
        '## Paired covered-case comparison',
        '',
        f"- RAG F1 wins: `{paired['rag_f1_wins']}`",
        f"- No-RAG F1 wins: `{paired['no_rag_f1_wins']}`",
        f"- Ties: `{paired['ties']}`",
        f"- Mean RAG minus no-RAG F1: `{paired['mean_rag_minus_no_rag_f1']}`",
        '',
        '## Selected examples',
        '',
    ])
    deltas = []
    for row in rows:
        if not row['source_available_in_candidate_corpus']:
            continue
        no_rag = row['adapter_no_rag']
        rag = row['adapter_with_candidate_rag']
        if no_rag.get('error') or rag.get('error'):
            continue
        deltas.append((rag['reference_token_f1'] - no_rag['reference_token_f1'], row))
    deltas.sort(key=lambda item: item[0], reverse=True)
    for delta, row in (deltas[:5] + deltas[-5:]):
        lines.extend([
            f"### {row['case_id']} (delta F1 `{round(delta, 6)}`)",
            '',
            f"**Pertanyaan:** {row['prompt']}",
            '',
            f"**No RAG:** {row['adapter_no_rag']['answer']}",
            '',
            f"**Candidate RAG:** {row['adapter_with_candidate_rag']['answer']}",
            '',
        ])
    lines.extend([
        '## Limitations',
        '',
        '- QA completions and the candidate corpus may have truncation, OCR noise, or dataset-level overlap.',
        '- A retrieval hit in this benchmark means an exact local regulation/article metadata match; it does not establish official provenance or legal currentness.',
        '- Multiple titles under one regulation/article key indicate that the current key is not sufficient for production retrieval; issuer, canonical title, source URL, or another document identity must also be indexed.',
        '- Token-F1, grounding precision, and abstention heuristics are diagnostics. Human legal review remains required.',
        '',
    ])
    path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    if COVERED_LIMIT <= 0 or MISSING_LIMIT <= 0 or TOP_K <= 0:
        raise ValueError('Batas sampel dan TOP_K harus lebih besar dari nol.')
    if not QA_SNAPSHOT.is_dir() or not CORPUS_SNAPSHOT.is_dir():
        raise FileNotFoundError('Snapshot QA/corpus tidak ditemukan.')
    print('=== Larger Qwen legal candidate-corpus RAG benchmark ===')
    print({
        'mode': MODE,
        'covered_limit': COVERED_LIMIT,
        'missing_limit': MISSING_LIMIT,
        'top_k': TOP_K,
        'prepare_only': PREPARE_ONLY,
        'qa_snapshot': str(QA_SNAPSHOT),
        'corpus_snapshot': str(CORPUS_SNAPSHOT),
        'run_dir': str(RUN_DIR),
    })
    cases, selection = select_qa_cases()
    corpus_index, corpus_index_stats = load_corpus_index(cases)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RUN_DIR / 'sampled_cases.jsonl', cases)
    write_json(RUN_DIR / 'sampling_manifest.json', selection)
    write_json(RUN_DIR / 'corpus_index_manifest.json', corpus_index_stats)
    print('Selected cases:', len(cases), selection['selected_counts'])
    print('Candidate pair coverage:', selection['candidate_pair_coverage_over_unique_qa_pairs'])
    print('Index stats:', corpus_index_stats)
    if PREPARE_ONLY:
        print('Prepare-only gate: PASSED')
        return
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA tidak tersedia; benchmark ini membutuhkan GPU lokal.')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('GPU tidak melaporkan dukungan BF16.')

    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    model, tokenizer = load_model()
    rows: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases, 1):
            retrieval = retrieve(case, corpus_index)
            context, context_truncated = render_context(case, retrieval)
            row = {
                **case,
                'retrieval': {
                    'status': retrieval['status'],
                    'candidate_chunks': retrieval['candidate_chunks'],
                    'retrieval_coverage': retrieval['retrieval_coverage'],
                    'hits': [
                        {
                            'source_id': hit['source_id'],
                            'article': hit['article'],
                            'title': hit['title'],
                            'chunk_index': hit['chunk_index'],
                        }
                        for hit in retrieval['hits']
                    ],
                },
                'retrieved_source_ids': [hit['source_id'] for hit in retrieval['hits']],
                'context': context,
                'context_truncated': context_truncated,
            }
            print(
                f"  case {index}/{len(cases)}: {case['case_id']} "
                f"({('covered' if case['source_available_in_candidate_corpus'] else 'missing')}, "
                f"retrieval={retrieval['status']})"
            )
            try:
                generated = generate_one(model, tokenizer, make_no_rag_prompt(case['prompt']))
                row['adapter_no_rag'] = score_output(
                    generated, case, '', retrieval, rag=False
                )
            except Exception as exc:
                row['adapter_no_rag'] = error_output(
                    exc, rag=False,
                    source_available=case['source_available_in_candidate_corpus'],
                )
                print('    no-RAG error:', repr(exc))
            try:
                generated = generate_one(
                    model,
                    tokenizer,
                    make_candidate_rag_prompt(case['prompt'], context),
                )
                row['adapter_with_candidate_rag'] = score_output(
                    generated, case, context, retrieval, rag=True
                )
            except Exception as exc:
                row['adapter_with_candidate_rag'] = error_output(
                    exc, rag=True,
                    source_available=case['source_available_in_candidate_corpus'],
                )
                print('    candidate-RAG error:', repr(exc))
            rows.append(row)
    finally:
        del model, tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    summaries = {
        'adapter_no_rag': summarize(rows, 'adapter_no_rag'),
        'adapter_with_candidate_rag': summarize(rows, 'adapter_with_candidate_rag'),
    }
    paired = compare_paired(rows)
    outputs_path = RUN_DIR / 'comparison_outputs.jsonl'
    review_path = RUN_DIR / 'human_review_queue.csv'
    report_path = RUN_DIR / 'comparison_report.md'
    manifest_path = RUN_DIR / 'large_rag_comparison_manifest.json'
    write_jsonl(outputs_path, rows)
    write_review_csv(review_path, rows)
    write_report(report_path, rows, summaries, paired, selection, corpus_index_stats)
    technical_pass = all(
        summary['errors'] == 0 and summary['empty_answers'] == 0
        for summary in summaries.values()
    )
    manifest = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': MODE,
        'run_dir': str(RUN_DIR),
        'model': {
            'base_model': os.environ['QWEN_LEGAL_EVAL_BASE_MODEL'],
            'adapter': os.environ['QWEN_LEGAL_EVAL_ADAPTER'],
        },
        'evaluation_scope': 'candidate-corpus RAG, not verified official-source RAG',
        'configuration': {
            'seed': SEED,
            'covered_limit': COVERED_LIMIT,
            'missing_limit': MISSING_LIMIT,
            'top_k': TOP_K,
            'context_max_chars': CONTEXT_MAX_CHARS,
            'max_new_tokens': int(os.environ['QWEN_LEGAL_EVAL_MAX_NEW_TOKENS']),
            'max_input_tokens': int(os.environ['QWEN_LEGAL_EVAL_MAX_INPUT_TOKENS']),
            'do_sample': False,
            'num_beams': 1,
        },
        'selection': selection,
        'corpus_index': corpus_index_stats,
        'automatic_diagnostics': summaries,
        'paired_comparison': paired,
        'gates': {
            'sampling_and_index_integrity': 'passed',
            'generation_technical_check': 'passed' if technical_pass else 'failed',
            'official_provenance': 'not_established_for_candidate_corpus',
            'human_legal_review': 'required',
            'production_decision': 'not_ready',
        },
        'outputs': {
            'sampled_cases': str(RUN_DIR / 'sampled_cases.jsonl'),
            'comparison_outputs_jsonl': str(outputs_path),
            'human_review_queue_csv': str(review_path),
            'comparison_report_md': str(report_path),
        },
        'warning': (
            'Candidate corpus ini dipakai untuk memperbesar uji perilaku, bukan '
            'sebagai bukti bahwa sumbernya resmi, berlaku, atau terkini.'
        ),
    }
    write_json(manifest_path, manifest)
    print('\n=== Automatic diagnostics ===')
    for label, summary in summaries.items():
        print(label, summary)
    print('paired', paired)
    print('\nArtifacts:')
    print('  report:', report_path)
    print('  outputs:', outputs_path)
    print('  review:', review_path)
    print('  manifest:', manifest_path)
    print('Technical gate:', 'PASSED' if technical_pass else 'FAILED')
    print('Provenance gate: CANDIDATE CORPUS ONLY')
    print('Legal correctness gate: HUMAN REVIEW REQUIRED')


if __name__ == '__main__':
    main()
