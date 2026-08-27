"""P0.5 source-review queue and gold-query authoring scaffold."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import polars as pl

from c5_model.audit import portable_path, sha256_file, write_json
from c5_model.normalize import normalize_display_text, normalize_key, stable_id


OFFICIAL_HOSTS = {"peraturan.go.id", "www.peraturan.go.id"}
SOURCE_REVIEW_STATUSES = {
    "pending_human_review",
    "needs_review",
    "verified",
    "rejected",
}
GOLD_REVIEW_STATUSES = {
    "blocked_unverified_source",
    "pending_human_review",
    "approved",
    "rejected",
}
SOURCE_STATUS_REVIEWS = {
    "current",
    "current_with_amendments",
    "historical_applicable",
}
DEFINITION_COMPARISONS = {"exact", "equivalent"}

SOURCE_REVIEW_COLUMNS = (
    "review_id",
    "pilot_index",
    "term_id",
    "canonical_term",
    "selection_bucket",
    "primary_regulation_label",
    "primary_regulation_title",
    "dataset_match_status",
    "dataset_candidate_id",
    "dataset_global_id",
    "dataset_article",
    "dataset_metadata_warnings",
    "official_source_id",
    "official_portal_url",
    "official_document_hint_url",
    "official_status_signal",
    "official_status_note",
    "source_review_status",
    "official_document_url",
    "official_document_sha256",
    "official_article",
    "official_definition",
    "definition_comparison",
    "source_status_review",
    "reviewer_id",
    "reviewed_at",
    "review_notes",
    "gold_eligibility",
    "attention_flags",
)

GOLD_QUERY_COLUMNS = (
    "query_id",
    "term_id",
    "canonical_term",
    "query_slot",
    "query_split",
    "query_text",
    "query_type",
    "expected_term_id",
    "source_review_id",
    "author_status",
    "review_status",
    "author_id",
    "reviewer_id",
    "reviewed_at",
    "notes",
)

REQUIRED_PILOT_COLUMNS = {
    "pilot_index",
    "term_id",
    "canonical_term",
    "selection_bucket",
    "primary_regulation_label",
    "primary_regulation_title",
}
REQUIRED_ENRICHED_COLUMNS = {
    "pilot_index",
    "term_id",
    "canonical_term",
    "primary_regulation_label",
    "match_status",
    "top_candidate_id",
    "top_dataset_global_id",
    "top_article",
    "top_metadata_warnings",
}


def _text(value: Any) -> str:
    return normalize_display_text("" if value is None else str(value))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = (
        pl.DataFrame(rows, strict=False)
        if rows
        else pl.DataFrame({column: [] for column in columns})
    )
    frame.select(columns).write_parquet(path, compression="zstd", statistics=True)


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = tuple(reader.fieldnames or ())
        if actual != columns:
            raise ValueError(
                f"Unexpected columns in {path}: {list(actual)!r}; expected {list(columns)!r}"
            )
        return [dict(row) for row in reader]


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "source_registry_path",
        "gold_query_slots_per_term",
        "locked_test_term_count",
        "locked_test_seed",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"Missing source-review fields: {missing}")
    slots = config["gold_query_slots_per_term"]
    locked_count = config["locked_test_term_count"]
    if not isinstance(slots, int) or slots < 1:
        raise ValueError("gold_query_slots_per_term must be a positive integer")
    if not isinstance(locked_count, int) or locked_count < 1:
        raise ValueError("locked_test_term_count must be a positive integer")
    if not _text(config["locked_test_seed"]):
        raise ValueError("locked_test_seed must not be empty")
    return config


def _official_url(url: str, *, field: str) -> str:
    clean_url = _text(url)
    parsed = urlparse(clean_url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError(
            f"{field} must be an HTTPS peraturan.go.id URL, got {clean_url!r}"
        )
    return clean_url


def load_registry(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported official-source-registry schema version")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Official source registry must contain sources")

    required = {
        "source_id",
        "regulation_label",
        "regulation_title",
        "official_portal_url",
        "status_signal",
        "status_note",
    }
    normalized: list[dict[str, str]] = []
    source_ids: set[str] = set()
    labels: set[str] = set()
    for index, raw in enumerate(sources, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Registry entry {index} must be an object")
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"Registry entry {index} is missing: {missing}")
        source = {key: _text(value) for key, value in raw.items()}
        if not source["source_id"] or source["source_id"] in source_ids:
            raise ValueError(f"Registry source_id is empty or duplicated at entry {index}")
        label_key = normalize_key(source["regulation_label"])
        if not label_key or label_key in labels:
            raise ValueError(
                f"Registry regulation_label is empty or duplicated at entry {index}"
            )
        source["official_portal_url"] = _official_url(
            source["official_portal_url"], field="official_portal_url"
        )
        if source.get("official_document_hint_url"):
            source["official_document_hint_url"] = _official_url(
                source["official_document_hint_url"],
                field="official_document_hint_url",
            )
        source_ids.add(source["source_id"])
        labels.add(label_key)
        normalized.append(source)
    return normalized


def _require_columns(frame: pl.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


def _locked_test_term_ids(
    rows: list[dict[str, Any]], *, count: int, seed: str
) -> set[str]:
    if count > len(rows):
        raise ValueError(
            f"locked_test_term_count {count} exceeds pilot term count {len(rows)}"
        )
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{seed}\u001f{row['term_id']}".encode("utf-8")
        ).hexdigest(),
    )
    return {row["term_id"] for row in ranked[:count]}


def _attention_flags(
    *, match_status: str, metadata_warnings: str, status_signal: str
) -> str:
    flags = ["official_document_and_definition_required"]
    if match_status == "regulation_not_found":
        flags.append("dataset_regulation_unresolved")
    elif match_status == "term_not_found_in_regulation":
        flags.append("dataset_term_unresolved")
    if metadata_warnings:
        flags.append("dataset_metadata_warning")
    if status_signal != "status_not_reviewed":
        flags.append("official_status_signal_requires_review")
    return "|".join(flags)


def _registry_by_label(registry: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {normalize_key(source["regulation_label"]): source for source in registry}


def prepare_source_review(
    *,
    pilot_path: Path,
    enriched_path: Path,
    registry_path: Path,
    config_path: Path,
    evaluation_dir: Path,
    manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Prepare a human source-review queue and empty, non-leaking gold slots."""

    config = load_config(config_path)
    registry = load_registry(registry_path)
    pilot = pl.read_parquet(pilot_path)
    enriched = pl.read_parquet(enriched_path)
    _require_columns(pilot, REQUIRED_PILOT_COLUMNS, "pilot terms")
    _require_columns(enriched, REQUIRED_ENRICHED_COLUMNS, "enriched pilot terms")
    if pilot.height == 0:
        raise ValueError("pilot terms must not be empty")

    pilot_rows = sorted(pilot.iter_rows(named=True), key=lambda row: row["pilot_index"])
    enriched_by_term: dict[str, dict[str, Any]] = {}
    for row in enriched.iter_rows(named=True):
        term_id = _text(row["term_id"])
        if not term_id or term_id in enriched_by_term:
            raise ValueError(f"Enriched rows contain an empty or duplicate term_id: {term_id!r}")
        enriched_by_term[term_id] = row
    pilot_term_ids = {_text(row["term_id"]) for row in pilot_rows}
    if len(pilot_term_ids) != len(pilot_rows):
        raise ValueError("Pilot rows contain duplicate or empty term_id values")
    if pilot_term_ids != set(enriched_by_term):
        raise ValueError("Pilot and enriched term IDs do not match")

    registry_by_label = _registry_by_label(registry)
    missing_sources = sorted(
        {
            _text(row["primary_regulation_label"])
            for row in pilot_rows
            if normalize_key(row["primary_regulation_label"]) not in registry_by_label
        }
    )
    if missing_sources:
        raise ValueError(
            "Official source registry is missing pilot regulations: "
            + "; ".join(missing_sources)
        )

    source_rows: list[dict[str, Any]] = []
    for pilot_row in pilot_rows:
        term_id = _text(pilot_row["term_id"])
        enriched_row = enriched_by_term[term_id]
        source = registry_by_label[normalize_key(pilot_row["primary_regulation_label"])]
        match_status = _text(enriched_row["match_status"])
        metadata_warnings = _text(enriched_row["top_metadata_warnings"])
        source_rows.append(
            {
                "review_id": stable_id("source_review", term_id, source["source_id"]),
                "pilot_index": pilot_row["pilot_index"],
                "term_id": term_id,
                "canonical_term": _text(pilot_row["canonical_term"]),
                "selection_bucket": _text(pilot_row["selection_bucket"]),
                "primary_regulation_label": _text(
                    pilot_row["primary_regulation_label"]
                ),
                "primary_regulation_title": _text(
                    pilot_row["primary_regulation_title"]
                ),
                "dataset_match_status": match_status,
                "dataset_candidate_id": _text(enriched_row["top_candidate_id"]),
                "dataset_global_id": _text(enriched_row["top_dataset_global_id"]),
                "dataset_article": _text(enriched_row["top_article"]),
                "dataset_metadata_warnings": metadata_warnings,
                "official_source_id": source["source_id"],
                "official_portal_url": source["official_portal_url"],
                "official_document_hint_url": source.get(
                    "official_document_hint_url", ""
                ),
                "official_status_signal": source["status_signal"],
                "official_status_note": source["status_note"],
                "source_review_status": "pending_human_review",
                "official_document_url": "",
                "official_document_sha256": "",
                "official_article": "",
                "official_definition": "",
                "definition_comparison": "not_reviewed",
                "source_status_review": "not_reviewed",
                "reviewer_id": "",
                "reviewed_at": "",
                "review_notes": "",
                "gold_eligibility": "blocked_unverified_source",
                "attention_flags": _attention_flags(
                    match_status=match_status,
                    metadata_warnings=metadata_warnings,
                    status_signal=source["status_signal"],
                ),
            }
        )

    locked_test_ids = _locked_test_term_ids(
        source_rows,
        count=config["locked_test_term_count"],
        seed=config["locked_test_seed"],
    )
    gold_rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        query_split = "locked_test" if source_row["term_id"] in locked_test_ids else "development"
        for query_slot in range(1, config["gold_query_slots_per_term"] + 1):
            gold_rows.append(
                {
                    "query_id": stable_id(
                        "gold_query", source_row["term_id"], str(query_slot)
                    ),
                    "term_id": source_row["term_id"],
                    "canonical_term": source_row["canonical_term"],
                    "query_slot": query_slot,
                    "query_split": query_split,
                    "query_text": "",
                    "query_type": "",
                    "expected_term_id": source_row["term_id"],
                    "source_review_id": source_row["review_id"],
                    "author_status": "pending_authoring",
                    "review_status": "blocked_unverified_source",
                    "author_id": "",
                    "reviewer_id": "",
                    "reviewed_at": "",
                    "notes": "Author manual query; do not include the target term or copy its source definition.",
                }
            )

    evaluation_dir.mkdir(parents=True, exist_ok=True)
    source_csv = evaluation_dir / "source_review_queue.csv"
    source_parquet = evaluation_dir / "source_review_queue.parquet"
    gold_csv = evaluation_dir / "gold_queries.csv"
    gold_parquet = evaluation_dir / "gold_queries.parquet"
    write_csv(source_csv, source_rows, SOURCE_REVIEW_COLUMNS)
    write_parquet(source_parquet, source_rows, SOURCE_REVIEW_COLUMNS)
    write_csv(gold_csv, gold_rows, GOLD_QUERY_COLUMNS)
    write_parquet(gold_parquet, gold_rows, GOLD_QUERY_COLUMNS)

    project_root = report_path.resolve().parents[2]
    output_paths = (source_csv, source_parquet, gold_csv, gold_parquet)
    output_hashes = {
        portable_path(path, project_root): sha256_file(path) for path in output_paths
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "p0_5_ready_for_human_review",
        "generated_at": generated_at,
        "pilot_path": portable_path(pilot_path, project_root),
        "pilot_sha256": sha256_file(pilot_path),
        "enriched_path": portable_path(enriched_path, project_root),
        "enriched_sha256": sha256_file(enriched_path),
        "config_path": portable_path(config_path, project_root),
        "config_sha256": sha256_file(config_path),
        "registry_path": portable_path(registry_path, project_root),
        "registry_sha256": sha256_file(registry_path),
        "official_authority": "Direktorat Jenderal Peraturan Perundang-undangan",
        "official_portal": "https://peraturan.go.id/",
        "pilot_term_count": len(source_rows),
        "registry_source_count": len(registry),
        "source_review_count": len(source_rows),
        "source_review_status_counts": dict(
            sorted(Counter(row["source_review_status"] for row in source_rows).items())
        ),
        "gold_query_slot_count": len(gold_rows),
        "gold_query_slots_per_term": config["gold_query_slots_per_term"],
        "locked_test_term_count": len(locked_test_ids),
        "locked_test_seed": config["locked_test_seed"],
        "locked_test_term_ids": [
            row["term_id"] for row in source_rows if row["term_id"] in locked_test_ids
        ],
        "gold_review_status_counts": dict(
            sorted(Counter(row["review_status"] for row in gold_rows).items())
        ),
        "verified_source_count": 0,
        "gold_approved_count": 0,
        "output_hashes": output_hashes,
    }
    write_json(manifest_path, summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary, registry), encoding="utf-8")
    return summary


def _is_valid_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _verified_source_errors(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    document_url = _text(row["official_document_url"])
    if not document_url:
        errors.append("official_document_url_missing")
    else:
        try:
            _official_url(document_url, field="official_document_url")
        except ValueError:
            errors.append("official_document_url_not_official_https")
    if not re.fullmatch(r"[0-9a-f]{64}", _text(row["official_document_sha256"])):
        errors.append("official_document_sha256_missing_or_invalid")
    if not _text(row["official_article"]):
        errors.append("official_article_missing")
    if not _text(row["official_definition"]):
        errors.append("official_definition_missing")
    if _text(row["definition_comparison"]) not in DEFINITION_COMPARISONS:
        errors.append("definition_comparison_not_accepted")
    if _text(row["source_status_review"]) not in SOURCE_STATUS_REVIEWS:
        errors.append("source_status_review_not_accepted")
    if not _text(row["reviewer_id"]):
        errors.append("reviewer_id_missing")
    if not _is_valid_timestamp(_text(row["reviewed_at"])):
        errors.append("reviewed_at_missing_or_invalid")
    if _text(row["gold_eligibility"]) != "eligible":
        errors.append("gold_eligibility_not_eligible")
    return errors


def validate_source_review(
    *, source_review_path: Path, gold_queries_path: Path
) -> dict[str, Any]:
    """Validate manual evidence without automatically changing review statuses."""

    source_rows = _read_csv(source_review_path, SOURCE_REVIEW_COLUMNS)
    gold_rows = _read_csv(gold_queries_path, GOLD_QUERY_COLUMNS)
    errors: list[str] = []
    source_by_review: dict[str, dict[str, str]] = {}
    source_by_term: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(source_rows, start=2):
        review_id = _text(row["review_id"])
        term_id = _text(row["term_id"])
        if not review_id or review_id in source_by_review:
            errors.append(f"source row {row_number}: duplicate or empty review_id")
        if not term_id or term_id in source_by_term:
            errors.append(f"source row {row_number}: duplicate or empty term_id")
        source_by_review[review_id] = row
        source_by_term[term_id] = row
        status = _text(row["source_review_status"])
        if status not in SOURCE_REVIEW_STATUSES:
            errors.append(f"source row {row_number}: unknown source_review_status {status!r}")
        if status == "verified":
            errors.extend(
                f"source row {row_number}: {reason}"
                for reason in _verified_source_errors(row)
            )

    query_ids: set[str] = set()
    query_term_counts: Counter[str] = Counter()
    approved_queries = 0
    for row_number, row in enumerate(gold_rows, start=2):
        query_id = _text(row["query_id"])
        term_id = _text(row["term_id"])
        if not query_id or query_id in query_ids:
            errors.append(f"gold row {row_number}: duplicate or empty query_id")
        query_ids.add(query_id)
        query_term_counts[term_id] += 1
        if term_id not in source_by_term:
            errors.append(f"gold row {row_number}: term_id is not in source review queue")
        if _text(row["expected_term_id"]) != term_id:
            errors.append(f"gold row {row_number}: expected_term_id mismatch")
        review_status = _text(row["review_status"])
        if review_status not in GOLD_REVIEW_STATUSES:
            errors.append(f"gold row {row_number}: unknown review_status {review_status!r}")
        if review_status == "approved":
            approved_queries += 1
            linked_source = source_by_review.get(_text(row["source_review_id"]))
            if linked_source is None:
                errors.append(f"gold row {row_number}: source_review_id is unknown")
            elif _text(linked_source["source_review_status"]) != "verified":
                errors.append(
                    f"gold row {row_number}: query approved before source verification"
                )
            if not _text(row["query_text"]):
                errors.append(f"gold row {row_number}: approved query_text is empty")
            if not _text(row["query_type"]):
                errors.append(f"gold row {row_number}: approved query_type is empty")
            canonical_term = _text(row["canonical_term"])
            if canonical_term and normalize_key(canonical_term) in normalize_key(
                row["query_text"]
            ):
                errors.append(
                    f"gold row {row_number}: approved query contains canonical target term"
                )
            if not _text(row["author_id"]):
                errors.append(f"gold row {row_number}: approved query author_id is empty")
            if not _text(row["reviewer_id"]):
                errors.append(f"gold row {row_number}: approved query reviewer_id is empty")
            if not _is_valid_timestamp(_text(row["reviewed_at"])):
                errors.append(f"gold row {row_number}: approved query reviewed_at is invalid")

    if errors:
        raise ValueError("P0.5 validation failed: " + "; ".join(errors))

    return {
        "status": "valid",
        "source_review_count": len(source_rows),
        "verified_source_count": sum(
            _text(row["source_review_status"]) == "verified" for row in source_rows
        ),
        "pending_source_review_count": sum(
            _text(row["source_review_status"]) == "pending_human_review"
            for row in source_rows
        ),
        "gold_query_slot_count": len(gold_rows),
        "gold_query_terms": len(query_term_counts),
        "gold_approved_count": approved_queries,
    }


def render_report(summary: dict[str, Any], registry: list[dict[str, str]]) -> str:
    signal_lines = "\n".join(
        f"- `{signal}`: {sum(source['status_signal'] == signal for source in registry)}"
        for signal in sorted({source["status_signal"] for source in registry})
    )
    return f"""# P0.5 Source Review Preparation

## Outcome

P0.5 menghasilkan antrean verifikasi untuk {summary['source_review_count']} istilah pilot dan {summary['gold_query_slot_count']} slot gold query. Tidak ada sumber yang otomatis dinaikkan menjadi `verified`, dan tidak ada teks query yang dibuat dari definisi dataset.

## Evidence boundary

- Dataset Hugging Face dan hasil pencocokan P0.4 tetap merupakan kandidat penemuan.
- Registry ini hanya menunjuk halaman/berkas awal pada portal resmi Ditjen PP: <https://peraturan.go.id/>.
- `official_status_signal` adalah sinyal untuk reviewer, bukan keputusan status hukum.
- `verified` memerlukan pemeriksaan manusia atas identitas regulasi, rantai perubahan/status, dokumen resmi, checksum dokumen, pasal, dan definisi.

## Locked inputs

- Pilot: `{summary['pilot_path']}` (`{summary['pilot_sha256']}`)
- P0.4 enrichment: `{summary['enriched_path']}` (`{summary['enriched_sha256']}`)
- Registry: `{summary['registry_path']}` (`{summary['registry_sha256']}`)
- Registry sources: {summary['registry_source_count']}

## Review queue

- Source rows: {summary['source_review_count']}
- Status counts: `{summary['source_review_status_counts']}`
- Semua row awalnya `pending_human_review` dan `blocked_unverified_source`.
- Status-signal registry:

{signal_lines}

## Gold-query authoring

- Slot: {summary['gold_query_slot_count']} ({summary['gold_query_slots_per_term']} per istilah)
- Locked test terms: {summary['locked_test_term_count']}
- Locked-test seed: `{summary['locked_test_seed']}`
- `query_text` sengaja kosong. Author harus membuat parafrasa/deskripsi yang tidak menyebut target term dan tidak menyalin definisi sumber.
- Query baru boleh `approved` setelah source row terkait berstatus `verified` dan query ditinjau manusia.

## Manual next action

1. Buka `official_portal_url` atau `official_document_hint_url`.
2. Pastikan nomor, tahun, judul, status, dan peraturan perubahan/pengganti cocok.
3. Simpan URL dokumen resmi yang benar dan SHA-256 berkas yang ditinjau.
4. Salin pasal serta definisi resmi yang relevan; bandingkan dengan seed tanpa mengubah seed.
5. Isi reviewer, timestamp, dan keputusan. Jalankan `c5-model validate-p05`.
6. Setelah source verified, author dan reviewer mengisi gold queries lalu validasi ulang.

Artefak ini membuat pekerjaan P0.5 reproducible, tetapi P0.5 belum selesai secara evidensial sampai review manual tersebut dilakukan.
"""


def default_paths(project_root: Path) -> dict[str, Path]:
    config_path = project_root / "configs/source-review.json"
    config = load_config(config_path)
    registry_path = project_root / config["source_registry_path"]
    evaluation_dir = project_root / "data/evaluation"
    return {
        "pilot_path": project_root / "data/curated/pilot_terms.parquet",
        "enriched_path": project_root / "data/curated/pilot_terms_enriched.parquet",
        "registry_path": registry_path,
        "config_path": config_path,
        "evaluation_dir": evaluation_dir,
        "manifest_path": project_root / "manifests/source-review.json",
        "report_path": project_root / "reports/p0/source-review.md",
        "source_review_path": evaluation_dir / "source_review_queue.csv",
        "gold_queries_path": evaluation_dir / "gold_queries.csv",
    }
