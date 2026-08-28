"""Compare the legal Qwen adapter with and without official-source RAG.

This is a small, auditable demonstration harness.  It deliberately uses a
curated official-source fixture instead of treating the large training corpus
as an authority.  Automatic scores are screening diagnostics only; legal
correctness, currentness, and citation quality still require human review.

Examples:
    python notebooks/qwen35_legal_rag_comparison.py
    QWEN_LEGAL_RAG_MODE=full python notebooks/qwen35_legal_rag_comparison.py

The harness loads the same local base model and LoRA adapter once, then sends
the same test questions through two prompt conditions:

* adapter_no_rag: no retrieved legal text is supplied;
* adapter_with_rag: metadata-filtered lexical retrieval supplies official
  excerpts and the model is instructed to cite ``[S1]`` or abstain.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import re
import statistics
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
HF_CACHE = HOME / '.cache' / 'huggingface' / 'hub'

MODE = os.environ.get('QWEN_LEGAL_RAG_MODE', 'smoke').strip().lower()
if MODE not in {'smoke', 'full'}:
    raise ValueError(f'QWEN_LEGAL_RAG_MODE harus smoke atau full, bukan {MODE!r}')

DEFAULT_MODEL = HF_CACHE / 'models--Qwen--Qwen3.5-4B-Base' / 'snapshots' / \
    '1001bb4d826a52d1f399e183466143f4da7b741b'
BASE_MODEL = Path(os.environ.get('QWEN_LEGAL_RAG_BASE_MODEL', str(DEFAULT_MODEL)))
ADAPTER = Path(os.environ.get(
    'QWEN_LEGAL_RAG_ADAPTER',
    '/home/tamaniga34/notebooks/qwen35_legal_runs/full/sft/final_adapter',
))
FIXTURE_PATH = Path(os.environ.get(
    'QWEN_LEGAL_RAG_FIXTURE',
    str(REPO_ROOT / 'data' / 'samples' / 'official_source_rag_fixture.jsonl'),
))
CASES_PATH = Path(os.environ.get(
    'QWEN_LEGAL_RAG_CASES',
    str(REPO_ROOT / 'data' / 'samples' / 'official_source_rag_test_cases.jsonl'),
))
RUN_ROOT = Path(os.environ.get(
    'QWEN_LEGAL_RAG_RUN_ROOT',
    '/home/tamaniga34/notebooks/qwen35_legal_rag_runs',
))
RUN_NAME = os.environ.get(
    'QWEN_LEGAL_RAG_RUN_NAME',
    datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'),
)
RUN_DIR = RUN_ROOT / MODE / RUN_NAME

LIMIT = int(os.environ.get('QWEN_LEGAL_RAG_LIMIT', '4' if MODE == 'smoke' else '0'))
TOP_K = int(os.environ.get('QWEN_LEGAL_RAG_TOP_K', '3'))
MAX_NEW_TOKENS = int(os.environ.get('QWEN_LEGAL_RAG_MAX_NEW_TOKENS', '256'))
MAX_INPUT_TOKENS = int(os.environ.get('QWEN_LEGAL_RAG_MAX_INPUT_TOKENS', '4096'))
ENABLE_THINKING = os.environ.get(
    'QWEN_LEGAL_RAG_ENABLE_THINKING', '0'
).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}

TOKEN_PATTERN = re.compile(r'[^\W_]+', flags=re.UNICODE)
REGULATION_PATTERN = re.compile(
    r'(?P<kind>undang-undang|uu|peraturan pemerintah|pp)\s*'
    r'(?:nomor|no\.?|#)?\s*(?P<number>\d+)\s+tahun\s+(?P<year>\d{4})',
    flags=re.IGNORECASE,
)
ARTICLE_PATTERN = re.compile(
    r'pasal\s+(?P<number>\d+[a-z]?)'
    r'(?:\s+ayat\s*\((?P<ayat>\d+)\))?'
    r'(?:\s+huruf\s+(?P<huruf>[a-z]))?'
    r'(?:\s+angka\s+(?P<angka>\d+))?',
    flags=re.IGNORECASE,
)

STOPWORDS = {
    'adalah', 'agar', 'atau', 'atas', 'apa', 'bagi', 'bahwa', 'dan', 'dari',
    'dengan', 'dalam', 'dan/atau', 'ini', 'itu', 'ke', 'kepada', 'menurut',
    'oleh', 'pada', 'sebagai', 'secara', 'tentang', 'terdiri', 'terhadap',
    'untuk', 'yang', 'serta', 'saja', 'sifat', 'bersifat', 'termasuk',
    'dimaksud', 'merupakan', 'tahun', 'nomor', 'no', 'pasal', 'ayat', 'huruf',
    'angka', 'undang', 'undangundang', 'peraturan', 'pemerintah',
}
ABSTENTION_PHRASES = (
    'tidak menemukan',
    'tidak tersedia',
    'tidak dapat memastikan',
    'tidak ada informasi',
    'tidak ada pasal',
    'tidak terdapat pasal',
    'tidak terdapat',
    'tidak memuat',
    'tidak ditemukan',
    'konteks tidak memuat',
)


def as_text(value: Any) -> str:
    return '' if value is None else str(value)


def normalized_text(value: Any) -> str:
    return ' '.join(
        unicodedata.normalize('NFKC', as_text(value)).casefold().split()
    )


def normalized_tokens(value: Any) -> list[str]:
    return TOKEN_PATTERN.findall(unicodedata.normalize('NFKC', as_text(value)).casefold())


def content_tokens(value: Any) -> list[str]:
    return [
        token for token in normalized_tokens(value)
        if token not in STOPWORDS and len(token) > 1
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f'JSONL tidak ditemukan: {path}')
    rows = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'JSONL invalid di {path}:{line_number}: {exc}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'Baris {path}:{line_number} bukan object JSON.')
        rows.append(row)
    if not rows:
        raise ValueError(f'JSONL kosong: {path}')
    return rows


def canonical_article(value: Any) -> str:
    text = normalized_text(value)
    text = text.replace('ayat (', 'ayat(').replace(' )', ')')
    return text


def canonical_kind(value: Any) -> str:
    text = normalized_text(value)
    if text in {'uu', 'undang-undang', 'undang undang'}:
        return 'undang-undang'
    if text in {'pp', 'peraturan pemerintah'}:
        return 'peraturan pemerintah'
    return text


def regulation_identity(row: dict[str, Any]) -> tuple[str, str, int]:
    return (
        canonical_kind(row.get('regulation_type')),
        as_text(row.get('regulation_number')).strip(),
        int(row.get('year')),
    )


def parse_regulation_identity(prompt: str) -> tuple[str, str, int] | None:
    match = REGULATION_PATTERN.search(prompt)
    if not match:
        return None
    kind = match.group('kind').casefold()
    if kind == 'uu':
        kind = 'undang-undang'
    elif kind == 'pp':
        kind = 'peraturan pemerintah'
    return kind, match.group('number'), int(match.group('year'))


def parse_article(prompt: str) -> str | None:
    match = ARTICLE_PATTERN.search(prompt)
    if not match:
        return None
    parts = [f"pasal {match.group('number')}"]
    if match.group('ayat'):
        parts.append(f"ayat({match.group('ayat')})")
    if match.group('huruf'):
        parts.append(f"huruf {match.group('huruf')}")
    if match.group('angka'):
        parts.append(f"angka {match.group('angka')}")
    return ' '.join(parts)


def validate_fixture(rows: list[dict[str, Any]]) -> None:
    required = {
        'source_id', 'authority', 'source_url', 'metadata_url',
        'regulation_type', 'regulation_number', 'year', 'title', 'article',
        'status_signal', 'source_version', 'retrieved_at', 'text',
    }
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(f'Fixture row {index} kehilangan kolom: {missing}')
        source_id = as_text(row['source_id'])
        if not source_id or source_id in seen:
            raise ValueError(f'source_id fixture tidak unik/kosong di row {index}')
        seen.add(source_id)
        regulation_identity(row)


def validate_cases(rows: list[dict[str, Any]]) -> None:
    required = {
        'case_id', 'prompt', 'reference_answer', 'expected_source_id',
        'expected_regulation_type', 'expected_regulation_number',
        'expected_year', 'expected_article', 'anchors', 'out_of_scope',
    }
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(f'Test case {index} kehilangan kolom: {missing}')
        case_id = as_text(row['case_id'])
        if not case_id or case_id in seen:
            raise ValueError(f'case_id tidak unik/kosong di row {index}')
        seen.add(case_id)
        if not isinstance(row['anchors'], list):
            raise ValueError(f'anchors harus list pada case {case_id}')


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


def anchor_recall(answer: str, anchors: list[str]) -> float:
    if not anchors:
        return math.nan
    answer_norm = normalized_text(answer)
    found = sum(normalized_text(anchor) in answer_norm for anchor in anchors)
    return round(found / len(anchors), 6)


def grounded_token_precision(answer: str, context: str) -> float | None:
    answer_tokens = content_tokens(answer)
    context_counter = Counter(normalized_tokens(context))
    if not answer_tokens or not context.strip():
        return None
    overlap = sum(min(1, context_counter[token]) for token in answer_tokens)
    return round(overlap / len(answer_tokens), 6)


def abstained_appropriately(answer: str, out_of_scope: bool) -> bool | None:
    if not out_of_scope:
        return None
    answer_norm = normalized_text(answer)
    return any(phrase in answer_norm for phrase in ABSTENTION_PHRASES)


def citation_present(answer: str) -> bool:
    # Accept the model's common ``S1``/``S1:`` variant as a traceability signal;
    # citation_format_exact records whether it followed the requested syntax.
    return bool(re.search(r'(?:\[\s*s1\s*\]|\bs1\b)', answer, flags=re.IGNORECASE))


def citation_format_exact(answer: str) -> bool:
    return bool(re.search(r'\[\s*s1\s*\]', answer, flags=re.IGNORECASE))


def answer_screening_score(
    *,
    reference_f1: float | None,
    anchors: float,
    appropriate_abstention: bool | None,
    out_of_scope: bool,
) -> float:
    """A comparable screening score, not a legal correctness score."""
    if out_of_scope:
        return 100.0 if appropriate_abstention else 0.0
    return round(100 * (0.65 * anchors + 0.35 * (reference_f1 or 0.0)), 2)


def rag_grounding_score(
    *,
    grounded_precision: float | None,
    retrieved_hit: bool,
    cited: bool,
    appropriate_abstention: bool | None,
    out_of_scope: bool,
) -> float:
    if out_of_scope:
        return 100.0 if (not retrieved_hit and appropriate_abstention) else 0.0
    return round(100 * (
        0.45 * (grounded_precision or 0.0)
        + 0.30 * float(retrieved_hit)
        + 0.25 * float(cited)
    ), 2)


def retrieve(case: dict[str, Any], fixture: list[dict[str, Any]]) -> dict[str, Any]:
    expected_identity = (
        canonical_kind(case['expected_regulation_type']),
        as_text(case['expected_regulation_number']).strip(),
        int(case['expected_year']),
    )
    expected_article = canonical_article(case['expected_article'])
    identity_candidates = [
        row for row in fixture if regulation_identity(row) == expected_identity
    ]

    # The strict article gate is intentional.  A similar-looking passage from
    # the same regulation must not be presented as evidence for another pasal.
    article_candidates = [
        row for row in identity_candidates
        if canonical_article(row['article']) == expected_article
    ]
    if not article_candidates:
        return {
            'status': 'not_found',
            'reason': 'requested regulation/article is absent from the fixture',
            'hits': [],
            'identity_candidates': len(identity_candidates),
            'requested_identity': expected_identity,
            'requested_article': expected_article,
        }

    query_tokens = set(content_tokens(case['prompt']))
    scored = []
    for row in article_candidates:
        row_tokens = set(content_tokens(
            f"{row['title']} {row['article']} {row['text']}"
        ))
        lexical_score = len(query_tokens & row_tokens)
        scored.append((lexical_score, row))
    scored.sort(key=lambda item: (-item[0], as_text(item[1]['source_id'])))
    hits = [row for _, row in scored[:TOP_K]]
    return {
        'status': 'found',
        'reason': 'strict metadata and article match',
        'hits': hits,
        'identity_candidates': len(identity_candidates),
        'requested_identity': expected_identity,
        'requested_article': expected_article,
    }


def render_context(retrieval: dict[str, Any]) -> str:
    hits = retrieval['hits']
    if not hits:
        return (
            '[NO_SOURCE_FOUND]\n'
            'Tidak ada potongan sumber resmi yang cocok untuk peraturan dan pasal '
            'yang diminta dalam indeks uji ini.'
        )
    blocks = []
    for index, row in enumerate(hits, 1):
        blocks.append(
            f"[S{index}]\n"
            f"Peraturan: {row['regulation_type']} Nomor {row['regulation_number']} "
            f"Tahun {row['year']} tentang {row['title']}\n"
            f"Ketentuan: {row['article']}\n"
            f"Status metadata: {row['status_signal']}\n"
            f"Versi sumber: {row['source_version']}\n"
            f"URL sumber: {row['source_url']}\n"
            f"Kutipan: {row['text']}"
        )
    return '\n\n'.join(blocks)


def make_no_rag_prompt(question: str) -> str:
    return (
        'Anda adalah asisten riset hukum Indonesia. Jawab pertanyaan pengguna '
        'secara ringkas dan hati-hati. Jangan mengarang nomor atau bunyi pasal.\n\n'
        f'Pertanyaan pengguna:\n{question}'
    )


def make_rag_prompt(question: str, context: str) -> str:
    return (
        'Anda adalah asisten riset hukum Indonesia. Gunakan HANYA konteks sumber '
        'resmi yang disediakan di bawah. Jika konteks tidak memuat pasal atau versi '
        'yang diminta, katakan bahwa Anda tidak menemukan sumber yang cocok dan '
        'jangan menebak. Jangan menyatakan suatu aturan masih berlaku hanya dari '
        'isi kutipan; gunakan metadata status bila relevan. Untuk jawaban yang '
        'didukung sumber, sertakan sitasi [S1].\n\n'
        f'KONTEKS SUMBER RESMI:\n{context}\n\n'
        f'PERTANYAAN PENGGUNA:\n{question}'
    )


def make_quantization_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )


def load_model() -> tuple[Any, Any]:
    if not BASE_MODEL.is_dir():
        raise FileNotFoundError(f'Base model tidak ditemukan: {BASE_MODEL}')
    if not ADAPTER.is_dir():
        raise FileNotFoundError(f'Adapter tidak ditemukan: {ADAPTER}')
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
    model = PeftModel.from_pretrained(model, str(ADAPTER), is_trainable=False)
    model.config.use_cache = True
    model.config.pad_token_id = tokenizer.pad_token_id
    if getattr(model, 'generation_config', None) is not None:
        model.generation_config.pad_token_id = tokenizer.pad_token_id
    model.eval()
    return model, tokenizer


def encode_prompt(tokenizer: Any, prompt: str) -> dict[str, torch.Tensor]:
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


def clean_generated_text(text: str) -> str:
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
    encoded = encode_prompt(tokenizer, prompt)
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
    return {
        'raw_answer': raw_answer,
        'answer': answer,
        'prompt_tokens': prompt_length,
        'generated_tokens': int(generated_ids.shape[-1]),
        'hit_max_new_tokens': int(generated_ids.shape[-1]) >= MAX_NEW_TOKENS,
        'protocol_marker_count': sum(
            raw_answer.count(marker)
            for marker in ('<|im_start|>', '<think>', '</think>')
        ) + sum(
            line.strip().casefold() in {'assistant', 'user'}
            for line in raw_answer.splitlines()
        ),
        'latency_seconds': round(elapsed, 4),
        'error': None,
    }


def score_output(
    output: dict[str, Any],
    case: dict[str, Any],
    context: str,
    retrieval: dict[str, Any],
    *,
    rag: bool,
) -> dict[str, Any]:
    answer = as_text(output.get('answer'))
    reference = as_text(case.get('reference_answer'))
    out_of_scope = bool(case.get('out_of_scope'))
    lexical = token_f1(reference, answer) if reference else None
    anchors = anchor_recall(answer, list(case.get('anchors') or []))
    abstention = abstained_appropriately(answer, out_of_scope)
    expected_source_id = as_text(case.get('expected_source_id'))
    retrieved_ids = [as_text(row.get('source_id')) for row in retrieval['hits']]
    retrieved_hit = bool(expected_source_id and expected_source_id in retrieved_ids)
    grounded = grounded_token_precision(answer, context) if rag else None
    cited = citation_present(answer) if rag else None
    score = answer_screening_score(
        reference_f1=lexical['f1'] if lexical else None,
        anchors=anchors if not math.isnan(anchors) else 0.0,
        appropriate_abstention=abstention,
        out_of_scope=out_of_scope,
    )
    rag_score = rag_grounding_score(
        grounded_precision=grounded,
        retrieved_hit=retrieved_hit,
        cited=bool(cited),
        appropriate_abstention=abstention,
        out_of_scope=out_of_scope,
    ) if rag else None
    return {
        **output,
        'reference_token_precision': lexical['precision'] if lexical else None,
        'reference_token_recall': lexical['recall'] if lexical else None,
        'reference_token_f1': lexical['f1'] if lexical else None,
        'anchor_recall': anchors,
        'grounded_token_precision': grounded,
        'citation_present': cited,
        'citation_format_exact': citation_format_exact(answer) if rag else None,
        'retrieved_source_ids': retrieved_ids,
        'retrieval_hit': retrieved_hit,
        'appropriate_abstention': abstention,
        'answer_screening_score': score,
        'rag_grounding_score': rag_score,
    }


def error_output(exc: Exception, *, rag: bool) -> dict[str, Any]:
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
        'anchor_recall': 0.0,
        'grounded_token_precision': None,
        'citation_present': False if rag else None,
        'citation_format_exact': False if rag else None,
        'retrieved_source_ids': [],
        'retrieval_hit': False,
        'appropriate_abstention': None,
        'answer_screening_score': 0.0,
        'rag_grounding_score': 0.0 if rag else None,
    }


def summarize(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    outputs = [row[label] for row in rows]
    successful = [item for item in outputs if not item.get('error')]
    in_scope = [
        item for row, item in zip(rows, outputs)
        if not row['out_of_scope'] and not item.get('error')
    ]
    out_scope = [
        item for row, item in zip(rows, outputs)
        if row['out_of_scope'] and not item.get('error')
    ]

    def mean_key(items: list[dict[str, Any]], key: str) -> float | None:
        values = [item[key] for item in items if item.get(key) is not None]
        return round(statistics.mean(values), 6) if values else None

    summary = {
        'label': label,
        'cases': len(rows),
        'errors': sum(bool(item.get('error')) for item in outputs),
        'empty_answers': sum(not as_text(item.get('answer')).strip() for item in outputs),
        'hit_max_new_tokens': sum(bool(item.get('hit_max_new_tokens')) for item in outputs),
        'mean_latency_seconds': mean_key(successful, 'latency_seconds'),
        'mean_answer_screening_score': mean_key(successful, 'answer_screening_score'),
        'mean_in_scope_answer_screening_score': mean_key(in_scope, 'answer_screening_score'),
        'mean_in_scope_reference_token_f1': mean_key(in_scope, 'reference_token_f1'),
        'mean_in_scope_anchor_recall': mean_key(in_scope, 'anchor_recall'),
        'appropriate_abstention_rate': (
            round(sum(bool(item.get('appropriate_abstention')) for item in out_scope) / len(out_scope), 6)
            if out_scope else None
        ),
        'mean_grounded_token_precision': mean_key(in_scope, 'grounded_token_precision'),
        'citation_rate': (
            round(sum(bool(item.get('citation_present')) for item in in_scope) / len(in_scope), 6)
            if label == 'adapter_with_rag' and in_scope else None
        ),
        'citation_exact_format_rate': (
            round(sum(bool(item.get('citation_format_exact')) for item in in_scope) / len(in_scope), 6)
            if label == 'adapter_with_rag' and in_scope else None
        ),
        'retrieval_hit_rate': (
            round(sum(bool(item.get('retrieval_hit')) for item in in_scope) / len(in_scope), 6)
            if label == 'adapter_with_rag' and in_scope else None
        ),
        'mean_rag_grounding_score': mean_key(successful, 'rag_grounding_score'),
    }
    return summary


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


def write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        'case_id', 'prompt', 'reference_answer', 'expected_source_id',
        'expected_article', 'source_url', 'retrieval_status',
        'retrieved_source_ids', 'adapter_no_rag_answer',
        'adapter_with_rag_answer', 'adapter_no_rag_answer_screening_score',
        'adapter_with_rag_answer_screening_score',
        'adapter_with_rag_rag_grounding_score',
        'adapter_with_rag_citation_present',
        'adapter_with_rag_citation_format_exact',
        'adapter_with_rag_grounded_token_precision',
        'adapter_with_rag_appropriate_abstention',
        'reviewer_no_rag_rating_1_to_5', 'reviewer_with_rag_rating_1_to_5',
        'reviewer_preferred_condition', 'reviewer_substance_correct',
        'reviewer_citation_correct', 'reviewer_current', 'reviewer_grounded',
        'reviewer_abstained_appropriately', 'reviewer_notes',
    ]
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({
                'case_id': row['case_id'],
                'prompt': row['prompt'],
                'reference_answer': row['reference_answer'],
                'expected_source_id': row['expected_source_id'],
                'expected_article': row['expected_article'],
                'source_url': row.get('expected_source_url', ''),
                'retrieval_status': row['retrieval']['status'],
                'retrieved_source_ids': ','.join(row['retrieval_source_ids']),
                'adapter_no_rag_answer': row['adapter_no_rag']['answer'],
                'adapter_with_rag_answer': row['adapter_with_rag']['answer'],
                'adapter_no_rag_answer_screening_score': row['adapter_no_rag']['answer_screening_score'],
                'adapter_with_rag_answer_screening_score': row['adapter_with_rag']['answer_screening_score'],
                'adapter_with_rag_rag_grounding_score': row['adapter_with_rag']['rag_grounding_score'],
                'adapter_with_rag_citation_present': row['adapter_with_rag']['citation_present'],
                'adapter_with_rag_citation_format_exact': row['adapter_with_rag']['citation_format_exact'],
                'adapter_with_rag_grounded_token_precision': row['adapter_with_rag']['grounded_token_precision'],
                'adapter_with_rag_appropriate_abstention': row['adapter_with_rag']['appropriate_abstention'],
                'reviewer_no_rag_rating_1_to_5': '',
                'reviewer_with_rag_rating_1_to_5': '',
                'reviewer_preferred_condition': '',
                'reviewer_substance_correct': '',
                'reviewer_citation_correct': '',
                'reviewer_current': '',
                'reviewer_grounded': '',
                'reviewer_abstained_appropriately': '',
                'reviewer_notes': '',
            })


def write_markdown_report(
    path: Path,
    rows: list[dict[str, Any]],
    summaries: dict[str, Any],
) -> None:
    lines = [
        '# Qwen legal: no-RAG vs official-source RAG',
        '',
        '> Automatic scores are screening diagnostics, not legal correctness judgments.',
        '',
        f'- Mode: `{MODE}`',
        f'- Cases: `{len(rows)}`',
        f'- Fixture: `{FIXTURE_PATH}`',
        '',
        '## Aggregate diagnostics',
        '',
        '| Condition | Mean answer score | In-scope F1 | Anchor recall | Abstention | Citation | Citation exact | Grounding |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for label, summary in summaries.items():
        lines.append(
            f"| {label} | {summary['mean_answer_screening_score']} "
            f"| {summary['mean_in_scope_reference_token_f1']} "
            f"| {summary['mean_in_scope_anchor_recall']} "
            f"| {summary['appropriate_abstention_rate']} "
            f"| {summary['citation_rate']} "
            f"| {summary['citation_exact_format_rate']} "
            f"| {summary['mean_grounded_token_precision']} |"
        )
    lines.extend(['', '## Per-case output', ''])
    for row in rows:
        lines.extend([
            f"### {row['case_id']}",
            '',
            f"**Pertanyaan:** {row['prompt']}",
            '',
            f"**No RAG** (score {row['adapter_no_rag']['answer_screening_score']}): "
            f"{row['adapter_no_rag']['answer']}",
            '',
            f"**Dengan RAG** (answer score {row['adapter_with_rag']['answer_screening_score']}; "
            f"grounding score {row['adapter_with_rag']['rag_grounding_score']}): "
            f"{row['adapter_with_rag']['answer']}",
            '',
            f"Retrieval: `{row['retrieval']['status']}`; "
            f"sources: `{', '.join(row['retrieval_source_ids']) or 'none'}`.",
            '',
        ])
    lines.extend([
        '## Interpretation',
        '',
        'A positive RAG result requires both answer quality and source grounding to improve. '
        'A high lexical score alone does not establish legal correctness, completeness, or currentness.',
        '',
        'Review `human_review_queue.csv` and fill the reviewer columns before drawing a deployment conclusion.',
        '',
    ])
    path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA tidak tersedia; benchmark ini membutuhkan GPU lokal.')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('GPU tidak melaporkan dukungan BF16.')
    if TOP_K <= 0 or MAX_NEW_TOKENS <= 0 or MAX_INPUT_TOKENS <= 0:
        raise ValueError('TOP_K dan batas token harus lebih besar dari nol.')

    fixture = load_jsonl(FIXTURE_PATH)
    cases = load_jsonl(CASES_PATH)
    validate_fixture(fixture)
    validate_cases(cases)
    if LIMIT > 0:
        cases = cases[:LIMIT]
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    print('=== Qwen legal: no-RAG vs official-source RAG ===')
    print({
        'mode': MODE,
        'cases': len(cases),
        'fixture_rows': len(fixture),
        'adapter': str(ADAPTER),
        'gpu': torch.cuda.get_device_name(0),
        'run_dir': str(RUN_DIR),
    })
    print('Fixture SHA256:', sha256_file(FIXTURE_PATH))

    model, tokenizer = load_model()
    rows: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases, 1):
            retrieval = retrieve(case, fixture)
            context = render_context(retrieval)
            retrieval_source_ids = [
                as_text(row.get('source_id')) for row in retrieval['hits']
            ]
            expected_source = next(
                (
                    row for row in fixture
                    if as_text(row.get('source_id')) == as_text(case.get('expected_source_id'))
                ),
                None,
            )
            row = {
                'case_id': case['case_id'],
                'prompt': case['prompt'],
                'reference_answer': case['reference_answer'],
                'expected_source_id': case['expected_source_id'],
                'expected_article': case['expected_article'],
                'expected_source_url': expected_source.get('source_url', '') if expected_source else '',
                'out_of_scope': bool(case['out_of_scope']),
                'anchors': case['anchors'],
                'retrieval': {
                    **{key: value for key, value in retrieval.items() if key != 'hits'},
                    'hits': [
                        {
                            'source_id': hit['source_id'],
                            'article': hit['article'],
                            'title': hit['title'],
                            'source_url': hit['source_url'],
                        }
                        for hit in retrieval['hits']
                    ],
                },
                'retrieval_source_ids': retrieval_source_ids,
                'context': context,
            }
            print(f'  case {index}/{len(cases)}: {case["case_id"]}; retrieval={retrieval["status"]}')
            try:
                no_rag = generate_one(model, tokenizer, make_no_rag_prompt(case['prompt']))
                row['adapter_no_rag'] = score_output(
                    no_rag, case, '', retrieval, rag=False
                )
            except Exception as exc:  # retain the other condition for review
                row['adapter_no_rag'] = error_output(exc, rag=False)
                print('    no-RAG error:', repr(exc))
            try:
                with_rag = generate_one(
                    model,
                    tokenizer,
                    make_rag_prompt(case['prompt'], context),
                )
                row['adapter_with_rag'] = score_output(
                    with_rag, case, context, retrieval, rag=True
                )
            except Exception as exc:
                row['adapter_with_rag'] = error_output(exc, rag=True)
                print('    RAG error:', repr(exc))
            rows.append(row)
    finally:
        del model, tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    summaries = {
        'adapter_no_rag': summarize(rows, 'adapter_no_rag'),
        'adapter_with_rag': summarize(rows, 'adapter_with_rag'),
    }
    outputs_path = RUN_DIR / 'comparison_outputs.jsonl'
    review_path = RUN_DIR / 'human_review_queue.csv'
    manifest_path = RUN_DIR / 'rag_comparison_manifest.json'
    report_path = RUN_DIR / 'comparison_report.md'
    write_jsonl(outputs_path, rows)
    write_review_csv(review_path, rows)
    write_markdown_report(report_path, rows, summaries)

    technical_pass = all(
        summaries[label]['errors'] == 0
        and summaries[label]['empty_answers'] == 0
        for label in summaries
    )
    manifest = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': MODE,
        'run_dir': str(RUN_DIR),
        'model': {
            'base_model': str(BASE_MODEL),
            'adapter': str(ADAPTER),
        },
        'inputs': {
            'fixture': str(FIXTURE_PATH),
            'fixture_sha256': sha256_file(FIXTURE_PATH),
            'cases': str(CASES_PATH),
            'case_count': len(cases),
        },
        'retrieval': {
            'method': 'strict regulation identity + exact article gate + lexical ordering',
            'top_k': TOP_K,
            'official_source_fixture_is_demo_only': True,
        },
        'generation': {
            'max_new_tokens': MAX_NEW_TOKENS,
            'max_input_tokens': MAX_INPUT_TOKENS,
            'enable_thinking': ENABLE_THINKING,
            'do_sample': False,
            'num_beams': 1,
        },
        'automatic_diagnostics': summaries,
        'gates': {
            'generation_technical_check': 'passed' if technical_pass else 'failed',
            'retrieval_fixture_integrity': 'passed',
            'human_legal_review': 'required',
            'production_decision': 'not_ready_without_authoritative_corpus_and_human_review',
        },
        'outputs': {
            'comparison_outputs_jsonl': str(outputs_path),
            'human_review_queue_csv': str(review_path),
            'comparison_report_md': str(report_path),
        },
        'warning': (
            'Fixture ini hanya untuk demonstrasi. Verifikasi ulang naskah resmi, '
            'status, perubahan, dan currentness sebelum pemakaian produksi.'
        ),
    }
    write_json(manifest_path, manifest)

    print('\n=== Automatic diagnostics ===')
    for label, summary in summaries.items():
        print(label, summary)
    print('\nArtifacts:')
    print('  report:', report_path)
    print('  outputs:', outputs_path)
    print('  review:', review_path)
    print('  manifest:', manifest_path)
    print('Technical gate:', 'PASSED' if technical_pass else 'FAILED')
    print('Legal correctness gate: HUMAN REVIEW REQUIRED')


if __name__ == '__main__':
    main()
