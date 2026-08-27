"""Deterministic P0.3 pilot-term selection."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from c5_model.audit import portable_path, sha256_file, write_json
from c5_model.normalize import normalize_key


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
ALIAS_RE = re.compile(r"\bselanjutnya\s+(?:disebut|disingkat)\b", re.IGNORECASE)
DIGIT_RE = re.compile(r"\d")
STOPWORDS = {
    "atas",
    "dan",
    "dari",
    "dalam",
    "di",
    "dengan",
    "ke",
    "pada",
    "atau",
    "untuk",
    "yang",
}

PILOT_COLUMNS = (
    "pilot_index",
    "term_id",
    "canonical_term",
    "selection_bucket",
    "selection_tags",
    "selection_reason",
    "related_terms",
    "sense_count",
    "sense_ids",
    "primary_regulation_type",
    "primary_regulation_label",
    "primary_regulation_title",
    "source_labels",
    "representative_source_definition",
    "representative_retrieval_text",
    "definition_length",
    "review_status",
    "review_notes",
)

REVIEW_QUEUE_COLUMNS = (
    "term_id",
    "canonical_term",
    "queue_reason",
    "verification_status",
    "regulation_label",
    "regulation_title",
    "review_status",
    "review_notes",
)

BUCKET_REASONS = {
    "anchor": "Istilah anchor yang ditetapkan untuk konteks produk dan contoh pengguna.",
    "multi_sense": "Istilah memiliki lebih dari satu sense atau sumber dan menguji disambiguasi.",
    "domain_focus": "Istilah terkait corporate, data, consumer, employment, finance, atau business drafting.",
    "near_neighbor": "Istilah memiliki tetangga leksikal dekat untuk menguji ranking kandidat serupa.",
    "alias": "Definisi memuat pola selanjutnya disebut atau disingkat.",
    "numeric": "Definisi memuat angka yang perlu dipertahankan secara tepat.",
    "long_definition": "Definisi berada pada kelompok panjang dan menguji retrieval dengan informasi padat.",
    "typical_fill": "Kasus tipikal dipilih untuk menjaga baseline tetap representatif.",
}


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if sum(config["quotas"].values()) != config["target_count"]:
        raise ValueError("Pilot quotas must add up to target_count")
    if config["quotas"].get("anchor") != len(config["anchors"]):
        raise ValueError("Anchor quota must match the number of anchors")
    if config["quotas"].get("domain_focus") != len(config["domain_focus_terms"]):
        raise ValueError("Domain-focus quota must match the number of configured terms")
    return config


def deterministic_rank(seed: str, bucket: str, term_id: str) -> str:
    return hashlib.sha256(f"{seed}\u001f{bucket}\u001f{term_id}".encode()).hexdigest()


def term_tokens(term: str) -> frozenset[str]:
    return frozenset(
        token
        for token in TOKEN_RE.findall(normalize_key(term))
        if token not in STOPWORDS and len(token) > 1
    )


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    return ordered[round((len(ordered) - 1) * fraction)]


def aggregate_terms(frame: pl.DataFrame, domain_focus_terms: list[str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in frame.sort(["canonical_term", "regulation_label", "sense_id"]).iter_rows(named=True):
        grouped[row["term_id"]].append(row)

    candidates: list[dict[str, Any]] = []
    normalized_domain_terms = {normalize_key(term) for term in domain_focus_terms}
    for term_id, rows in grouped.items():
        representative = rows[0]
        definitions = [row["source_definition"] for row in rows]
        source_labels = sorted({row["regulation_label"] for row in rows})
        regulation_types = sorted({row["regulation_type"] for row in rows})
        regulation_titles = sorted({row["regulation_title"] for row in rows})
        warnings = sorted(
            {row["normalization_warning"] for row in rows if row["normalization_warning"]}
        )
        candidates.append(
            {
                "term_id": term_id,
                "canonical_term": representative["canonical_term"],
                "normalized_term": representative["normalized_term"],
                "sense_count": len(rows),
                "sense_ids": sorted(row["sense_id"] for row in rows),
                "primary_regulation_type": representative["regulation_type"],
                "primary_regulation_label": representative["regulation_label"],
                "primary_regulation_title": representative["regulation_title"],
                "source_labels": source_labels,
                "regulation_types": regulation_types,
                "representative_source_definition": representative["source_definition"],
                "representative_retrieval_text": representative["retrieval_text"],
                "definition_length": len(representative["source_definition"]),
                "maximum_definition_length": max(map(len, definitions)),
                "has_alias": any(ALIAS_RE.search(definition) for definition in definitions),
                "has_digits": any(DIGIT_RE.search(definition) for definition in definitions),
                "domain_focus": representative["normalized_term"] in normalized_domain_terms,
                "normalization_warnings": warnings,
                "tokens": term_tokens(representative["canonical_term"]),
            }
        )
    return candidates


def near_neighbor_pairs(
    candidates: list[dict[str, Any]],
    minimum_jaccard: float,
    seed: str,
) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
    candidate_by_id = {candidate["term_id"]: candidate for candidate in candidates}
    token_index: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        for token in candidate["tokens"]:
            token_index[token].append(candidate["term_id"])

    shared_counts: Counter[tuple[str, str]] = Counter()
    for term_ids in token_index.values():
        for left, right in combinations(sorted(set(term_ids)), 2):
            shared_counts[(left, right)] += 1

    pairs: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for (left_id, right_id), shared in shared_counts.items():
        left = candidate_by_id[left_id]
        right = candidate_by_id[right_id]
        union_size = len(left["tokens"] | right["tokens"])
        if not union_size:
            continue
        score = shared / union_size
        if score >= minimum_jaccard:
            pairs.append((score, left, right))

    return sorted(
        pairs,
        key=lambda item: (
            -item[0],
            deterministic_rank(seed, "near_neighbor", item[1]["term_id"] + item[2]["term_id"]),
        ),
    )


def write_csv(path: Path, rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def render_report(summary: dict[str, Any], selected: list[dict[str, Any]]) -> str:
    bucket_lines = "\n".join(
        f"- `{bucket}`: {count}" for bucket, count in summary["bucket_counts"].items()
    )
    source_type_lines = "\n".join(
        f"- `{source_type}`: {count}"
        for source_type, count in summary["regulation_type_counts"].items()
    )
    selected_lines = "\n".join(
        f"{row['pilot_index']}. **{row['canonical_term']}** — `{row['selection_bucket']}` — {row['primary_regulation_label']}"
        for row in selected
    )

    return f"""# P0.3 Pilot Selection

## Outcome

Selector deterministik menghasilkan {summary['selected_count']} istilah untuk review. Pilot ini belum merupakan gold set: seluruh record masih berstatus `pending_review`, dan tidak ada label retrieval yang dibuat pada P0.3.

## Input boundary

- Input corpus: `{summary['input_path']}`
- Input SHA-256: `{summary['input_sha256']}`
- Eligible terms after excluding normalization warnings: {summary['eligible_term_count']:,}
- Normalization-warning terms routed to review queue: {summary['normalization_warning_count']:,}
- Quarantined terms routed to review queue: {summary['quarantine_count']:,}
- Target pilot: {summary['target_count']}
- Maximum selected terms per primary source: {summary['max_per_primary_source']}

## Selection buckets

{bucket_lines}

## Primary regulation types

{source_type_lines}

## Diversity checks

- Unique selected term IDs: {summary['unique_selected_term_ids']}
- Unique primary sources: {summary['unique_primary_sources']}
- Maximum observed terms from one primary source: {summary['maximum_observed_per_primary_source']}
- Terms with multiple senses: {summary['selected_multi_sense_terms']}
- Terms containing aliases: {summary['selected_alias_terms']}
- Terms containing digits: {summary['selected_numeric_terms']}
- Near-neighbor terms: {summary['selected_near_neighbor_terms']}
- Selection seed: `{summary['selection_seed']}`

## Selected terms

{selected_lines}

## Review contract

- `pending_review` berarti istilah hanya dipilih untuk eksperimen.
- Reviewer boleh memilih `approve`, `reject`, atau `needs_review`.
- Reviewer tidak mengubah definisi sumber di dalam file pilot.
- Quarantine dan normalization warning tidak masuk 50 istilah utama.
- Source verification, query authoring, dan locked test split adalah tahap terpisah.
"""


def select_pilot(
    *,
    input_path: Path,
    quarantine_path: Path,
    config_path: Path,
    output_dir: Path,
    manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    config = load_config(config_path)
    input_frame = pl.read_parquet(input_path)
    quarantine_frame = pl.read_parquet(quarantine_path)
    all_candidates = aggregate_terms(input_frame, config["domain_focus_terms"])
    eligible = [candidate for candidate in all_candidates if not candidate["normalization_warnings"]]
    warning_candidates = [candidate for candidate in all_candidates if candidate["normalization_warnings"]]
    candidate_by_term = {candidate["normalized_term"]: candidate for candidate in eligible}
    long_threshold = _percentile(
        [candidate["maximum_definition_length"] for candidate in eligible], 0.90
    )

    selected: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    related_terms: dict[str, set[str]] = defaultdict(set)
    bucket_order = list(config["quotas"])

    def can_add(candidate: dict[str, Any], *, force: bool = False) -> bool:
        if candidate["term_id"] in selected:
            return False
        source = candidate["primary_regulation_label"]
        return force or source_counts[source] < config["max_per_primary_source"]

    def add(candidate: dict[str, Any], bucket: str, *, force: bool = False) -> bool:
        if not can_add(candidate, force=force):
            return False
        chosen = dict(candidate)
        chosen["selection_bucket"] = bucket
        selected[candidate["term_id"]] = chosen
        source_counts[candidate["primary_regulation_label"]] += 1
        return True

    def ranked(bucket: str, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            candidates,
            key=lambda candidate: deterministic_rank(
                config["seed"], bucket, candidate["term_id"]
            ),
        )

    for anchor in config["anchors"]:
        candidate = candidate_by_term.get(normalize_key(anchor))
        if candidate is None:
            raise ValueError(f"Configured anchor is unavailable or excluded: {anchor}")
        add(candidate, "anchor", force=True)

    bucket_filters = {
        "multi_sense": lambda candidate: candidate["sense_count"] > 1,
        "domain_focus": lambda candidate: candidate["domain_focus"],
        "alias": lambda candidate: candidate["has_alias"],
        "numeric": lambda candidate: candidate["has_digits"],
        "long_definition": lambda candidate: candidate["maximum_definition_length"] >= long_threshold,
        "typical_fill": lambda candidate: True,
    }

    needed = config["quotas"]["multi_sense"]
    for candidate in ranked("multi_sense", filter(bucket_filters["multi_sense"], eligible)):
        if sum(row["selection_bucket"] == "multi_sense" for row in selected.values()) >= needed:
            break
        add(candidate, "multi_sense")

    for configured_term in config["domain_focus_terms"]:
        candidate = candidate_by_term.get(normalize_key(configured_term))
        if candidate is None:
            raise ValueError(
                f"Configured domain-focus term is unavailable or excluded: {configured_term}"
            )
        if not add(candidate, "domain_focus"):
            raise ValueError(
                f"Configured domain-focus term conflicts with selection constraints: {configured_term}"
            )

    near_needed = config["quotas"]["near_neighbor"]
    pairs = near_neighbor_pairs(
        eligible,
        config["near_neighbor_min_jaccard"],
        config["seed"],
    )
    for _, left, right in pairs:
        if sum(row["selection_bucket"] == "near_neighbor" for row in selected.values()) >= near_needed:
            break
        if left["term_id"] in selected or right["term_id"] in selected:
            continue
        left_source = left["primary_regulation_label"]
        right_source = right["primary_regulation_label"]
        additions_by_source = Counter((left_source, right_source))
        if any(
            source_counts[source] + additions > config["max_per_primary_source"]
            for source, additions in additions_by_source.items()
        ):
            continue
        if add(left, "near_neighbor") and add(right, "near_neighbor"):
            related_terms[left["term_id"]].add(right["canonical_term"])
            related_terms[right["term_id"]].add(left["canonical_term"])

    for bucket in ("alias", "numeric", "long_definition", "typical_fill"):
        needed = config["quotas"][bucket]
        for candidate in ranked(bucket, filter(bucket_filters[bucket], eligible)):
            if sum(row["selection_bucket"] == bucket for row in selected.values()) >= needed:
                break
            add(candidate, bucket)

    if len(selected) < config["target_count"]:
        for candidate in ranked("fallback", eligible):
            if len(selected) >= config["target_count"]:
                break
            add(candidate, "typical_fill")

    if len(selected) != config["target_count"]:
        raise RuntimeError(
            f"Unable to select target count: selected {len(selected)}, expected {config['target_count']}"
        )

    anchor_keys = {normalize_key(anchor) for anchor in config["anchors"]}
    output_rows: list[dict[str, Any]] = []
    for candidate in selected.values():
        tags: list[str] = []
        if candidate["normalized_term"] in anchor_keys:
            tags.append("anchor")
        if candidate["sense_count"] > 1:
            tags.append("multi_sense")
        if candidate["domain_focus"]:
            tags.append("domain_focus")
        if candidate["has_alias"]:
            tags.append("alias")
        if candidate["has_digits"]:
            tags.append("numeric")
        if candidate["maximum_definition_length"] >= long_threshold:
            tags.append("long_definition")
        if related_terms[candidate["term_id"]]:
            tags.append("near_neighbor")
        output_rows.append(
            {
                "term_id": candidate["term_id"],
                "canonical_term": candidate["canonical_term"],
                "selection_bucket": candidate["selection_bucket"],
                "selection_tags": "|".join(tags),
                "selection_reason": BUCKET_REASONS[candidate["selection_bucket"]],
                "related_terms": "|".join(sorted(related_terms[candidate["term_id"]])),
                "sense_count": candidate["sense_count"],
                "sense_ids": "|".join(candidate["sense_ids"]),
                "primary_regulation_type": candidate["primary_regulation_type"],
                "primary_regulation_label": candidate["primary_regulation_label"],
                "primary_regulation_title": candidate["primary_regulation_title"],
                "source_labels": "|".join(candidate["source_labels"]),
                "representative_source_definition": candidate["representative_source_definition"],
                "representative_retrieval_text": candidate["representative_retrieval_text"],
                "definition_length": candidate["definition_length"],
                "review_status": "pending_review",
                "review_notes": "",
            }
        )

    bucket_index = {bucket: index for index, bucket in enumerate(bucket_order)}
    output_rows.sort(
        key=lambda row: (bucket_index[row["selection_bucket"]], row["canonical_term"].casefold())
    )
    for index, row in enumerate(output_rows, start=1):
        row["pilot_index"] = index

    output_dir.mkdir(parents=True, exist_ok=True)
    pilot_csv = output_dir / "pilot_terms.csv"
    pilot_parquet = output_dir / "pilot_terms.parquet"
    review_queue_csv = output_dir / "pilot_review_queue.csv"
    write_csv(pilot_csv, output_rows, PILOT_COLUMNS)
    pl.DataFrame(output_rows, strict=False).select(PILOT_COLUMNS).write_parquet(
        pilot_parquet, compression="zstd", statistics=True
    )

    review_queue: list[dict[str, Any]] = []
    for candidate in warning_candidates:
        review_queue.append(
            {
                "term_id": candidate["term_id"],
                "canonical_term": candidate["canonical_term"],
                "queue_reason": "normalization_warning:" + "|".join(candidate["normalization_warnings"]),
                "verification_status": "candidate_secondary_source",
                "regulation_label": candidate["primary_regulation_label"],
                "regulation_title": candidate["primary_regulation_title"],
                "review_status": "pending_review",
                "review_notes": "",
            }
        )
    for row in quarantine_frame.iter_rows(named=True):
        review_queue.append(
            {
                "term_id": row["term_id"],
                "canonical_term": row["canonical_term"],
                "queue_reason": "quarantine:" + row["quarantine_reason"],
                "verification_status": row["verification_status"],
                "regulation_label": row["regulation_label"],
                "regulation_title": row["regulation_title"],
                "review_status": "pending_review",
                "review_notes": "",
            }
        )
    review_queue.sort(key=lambda row: (row["queue_reason"], row["canonical_term"].casefold()))
    write_csv(review_queue_csv, review_queue, REVIEW_QUEUE_COLUMNS)

    project_root = report_path.resolve().parents[2]
    output_hashes = {
        portable_path(path, project_root): sha256_file(path)
        for path in (pilot_csv, pilot_parquet, review_queue_csv)
    }
    bucket_counts = dict(
        (bucket, sum(row["selection_bucket"] == bucket for row in output_rows))
        for bucket in bucket_order
    )
    source_count_values = Counter(row["primary_regulation_label"] for row in output_rows)
    regulation_type_counts = dict(
        sorted(
            Counter(row["primary_regulation_type"] for row in output_rows).items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "p0_3_complete",
        "generated_at": generated_at,
        "input_path": portable_path(input_path, project_root),
        "input_sha256": sha256_file(input_path),
        "quarantine_path": portable_path(quarantine_path, project_root),
        "quarantine_sha256": sha256_file(quarantine_path),
        "config_path": portable_path(config_path, project_root),
        "config_sha256": sha256_file(config_path),
        "target_count": config["target_count"],
        "selected_count": len(output_rows),
        "eligible_term_count": len(eligible),
        "normalization_warning_count": len(warning_candidates),
        "quarantine_count": quarantine_frame.height,
        "long_definition_threshold": long_threshold,
        "max_per_primary_source": config["max_per_primary_source"],
        "bucket_counts": bucket_counts,
        "regulation_type_counts": regulation_type_counts,
        "unique_selected_term_ids": len({row["term_id"] for row in output_rows}),
        "unique_primary_sources": len(source_count_values),
        "maximum_observed_per_primary_source": max(source_count_values.values()),
        "selected_multi_sense_terms": sum(row["sense_count"] > 1 for row in output_rows),
        "selected_alias_terms": sum("alias" in row["selection_tags"].split("|") for row in output_rows),
        "selected_numeric_terms": sum("numeric" in row["selection_tags"].split("|") for row in output_rows),
        "selected_near_neighbor_terms": sum("near_neighbor" in row["selection_tags"].split("|") for row in output_rows),
        "selection_seed": config["seed"],
        "selected_terms": [
            {
                "pilot_index": row["pilot_index"],
                "term_id": row["term_id"],
                "canonical_term": row["canonical_term"],
                "selection_bucket": row["selection_bucket"],
                "primary_regulation_label": row["primary_regulation_label"],
                "review_status": row["review_status"],
            }
            for row in output_rows
        ],
        "output_hashes": output_hashes,
    }
    write_json(manifest_path, summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary, output_rows), encoding="utf-8")
    return summary


def default_paths(project_root: Path) -> dict[str, Path]:
    return {
        "input_path": project_root / "data/interim/legal_term_senses.parquet",
        "quarantine_path": project_root / "data/interim/quarantined_records.parquet",
        "config_path": project_root / "configs/pilot-selection.json",
        "output_dir": project_root / "data/curated",
        "manifest_path": project_root / "manifests/pilot-selection.json",
        "report_path": project_root / "reports/p0/pilot-selection.md",
    }
