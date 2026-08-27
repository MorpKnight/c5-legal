"""P0.2 audit and conservative normalization pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from c5_model.normalize import (
    normalize_display_text,
    normalize_key,
    parse_regulation_label,
    source_host,
    stable_id,
    strip_term_prefix,
)


RAW_COLUMNS = (
    "istilah",
    "pengertian",
    "undang_undang",
    "uu",
    "url",
    "status",
)

OUTPUT_COLUMNS = (
    "term_id",
    "sense_id",
    "source_id",
    "raw_row_number",
    "duplicate_count",
    "canonical_term",
    "normalized_term",
    "source_definition",
    "retrieval_text",
    "retrieval_prefix_removed",
    "normalization_warning",
    "regulation_label",
    "regulation_type",
    "regulation_number",
    "regulation_year",
    "regulation_title",
    "source_url",
    "source_host",
    "source_status",
    "verification_status",
    "quarantine_reason",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_source(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != RAW_COLUMNS:
            raise ValueError(
                f"Unexpected CSV columns: {reader.fieldnames!r}; expected {list(RAW_COLUMNS)!r}"
            )

        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Malformed CSV row {index}: extra values detected")
            normalized_row = {column: row.get(column, "") for column in RAW_COLUMNS}
            normalized_row["_raw_row_number"] = str(index)
            rows.append(normalized_row)
        return rows


def exact_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(normalize_key(row[column]) for column in RAW_COLUMNS)


def quarantine_reason(row: dict[str, str], regulation: dict[str, str]) -> str:
    missing = [column for column in ("istilah", "pengertian", "undang_undang") if not normalize_key(row[column])]
    if missing:
        return "missing_required:" + ",".join(missing)
    if normalize_key(row["status"]) != "ok":
        return "source_unverified"
    if not normalize_key(row["uu"]):
        return "missing_regulation_title"
    if not regulation["regulation_number"] or not regulation["regulation_year"]:
        return "unparseable_regulation_identity"
    return ""


def build_record(row: dict[str, str], duplicate_count: int) -> dict[str, Any]:
    canonical_term = normalize_display_text(row["istilah"])
    source_definition = normalize_display_text(row["pengertian"])
    regulation_title = normalize_display_text(row["uu"])
    source_url = normalize_display_text(row["url"])
    source_status = normalize_display_text(row["status"])
    regulation = parse_regulation_label(row["undang_undang"])
    retrieval_text, prefix_removed = strip_term_prefix(canonical_term, source_definition)
    reason = quarantine_reason(row, regulation)

    term_id = stable_id("term", canonical_term)
    source_id = stable_id(
        "source",
        regulation["regulation_label"],
        regulation_title,
        source_url,
    )
    sense_id = stable_id(
        "sense",
        canonical_term,
        source_definition,
        regulation["regulation_label"],
        regulation_title,
    )

    return {
        "term_id": term_id,
        "sense_id": sense_id,
        "source_id": source_id,
        "raw_row_number": int(row["_raw_row_number"]),
        "duplicate_count": duplicate_count,
        "canonical_term": canonical_term,
        "normalized_term": normalize_key(canonical_term),
        "source_definition": source_definition,
        "retrieval_text": retrieval_text,
        "retrieval_prefix_removed": prefix_removed,
        "normalization_warning": "" if prefix_removed else "term_prefix_not_found",
        **regulation,
        "regulation_title": regulation_title,
        "source_url": source_url,
        "source_host": source_host(source_url),
        "source_status": source_status,
        "verification_status": "quarantined" if reason else "candidate_secondary_source",
        "quarantine_reason": reason,
    }


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, strict=False)
    frame.select(OUTPUT_COLUMNS).write_parquet(path, compression="zstd", statistics=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def portable_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return path.name


def render_report(stats: dict[str, Any], multi_sense_terms: list[str]) -> str:
    missing_lines = "\n".join(
        f"- `{column}`: {count}" for column, count in stats["missing_fields"].items()
    )
    status_lines = "\n".join(
        f"- `{status}`: {count}" for status, count in stats["status_counts"].items()
    )
    host_lines = "\n".join(
        f"- `{host or '(missing)'}`: {count}" for host, count in stats["source_hosts"].items()
    )
    quarantine_lines = "\n".join(
        f"- `{reason}`: {count}" for reason, count in stats["quarantine_reason_counts"].items()
    )
    sense_lines = "\n".join(f"- {term}" for term in multi_sense_terms) or "- Tidak ada"

    return f"""# P0.2 CSV Audit

## Outcome

Input berhasil dibaca tanpa mengubah file sumber. Duplikat persis dipisahkan secara deterministik, record yang belum terverifikasi dikarantina, dan teks retrieval dibuat terpisah dari definisi sumber.

Hasil ini adalah audit teknis. Status `candidate_secondary_source` bukan verifikasi hukum karena URL sumber saat ini masih merupakan aggregator sekunder.

## Input integrity

- Path VM: `{stats['input_path']}`
- SHA-256: `{stats['input_sha256']}`
- Size: {stats['input_size_bytes']:,} byte
- Raw records: {stats['raw_records']:,}
- Raw input unchanged after processing: `{str(stats['raw_input_unchanged']).lower()}`

## Deduplication and senses

- Exact duplicate rows removed: {stats['exact_duplicate_rows_removed']:,}
- Unique records after exact dedupe: {stats['unique_records']:,}
- Unique normalized terms: {stats['unique_terms']:,}
- Duplicate term groups in raw input: {stats['duplicate_term_groups']:,}
- Raw records participating in duplicate term groups: {stats['records_in_duplicate_term_groups']:,}
- Terms with more than one distinct sense/source record: {stats['multi_sense_term_groups']:,}
- Curated candidate records: {stats['curated_records']:,}
- Quarantined unique records: {stats['quarantined_records']:,}
- Raw rows represented by quarantine: {stats['quarantined_raw_records']:,}

## Retrieval text

- Prefix containing the answer term removed: {stats['retrieval_prefix_removed_records']:,}
- Prefix not removed: {stats['retrieval_prefix_retained_records']:,}
- Definition length minimum: {stats['definition_length']['min']:,} characters
- Definition length median: {stats['definition_length']['median']:,} characters
- Definition length p90: {stats['definition_length']['p90']:,} characters
- Definition length maximum: {stats['definition_length']['max']:,} characters

## Missing fields

{missing_lines}

## Source status

{status_lines}

## Source hosts

{host_lines}

## Quarantine reasons

{quarantine_lines}

## Terms with multiple distinct sense/source records

{sense_lines}

## Data boundary

- `source_definition` mempertahankan teks sumber setelah normalisasi Unicode dan whitespace konservatif.
- `retrieval_text` hanya menghapus awalan istilah yang membocorkan jawaban.
- Record non-`OK` atau tanpa judul regulasi dipisahkan dari kandidat utama.
- Tidak ada record yang diberi status `verified` pada P0.2.
- Pencocokan ke sumber resmi dan status keberlakuan regulasi adalah tahap berikutnya.
"""


def update_manifests(
    *,
    sources_manifest_path: Path,
    dataset_lock_path: Path,
    input_path_label: str,
    input_sha256: str,
    input_size_bytes: int,
    raw_records: int,
    generated_at: str,
    output_hashes: dict[str, str],
) -> None:
    sources = json.loads(sources_manifest_path.read_text(encoding="utf-8"))
    for source in sources["sources"]:
        if source["source_id"] == "local_kamus_hukum":
            source.update(
                {
                    "revision": f"sha256:{input_sha256}",
                    "sha256": input_sha256,
                    "size_bytes": input_size_bytes,
                    "row_count": raw_records,
                    "location": input_path_label,
                    "retrieved_at": generated_at,
                    "processing_status": "processed",
                    "verification_status": "secondary_source_needs_official_review",
                    "outputs": output_hashes,
                }
            )
            source.pop("vm_location", None)
    sources["status"] = "p0_2_complete"
    write_json(sources_manifest_path, sources)

    dataset_lock = {
        "schema_version": 1,
        "status": "seed_locked",
        "created_at": generated_at,
        "datasets": [
            {
                "dataset_id": "local_kamus_hukum",
                "revision": f"sha256:{input_sha256}",
                "sha256": input_sha256,
                "size_bytes": input_size_bytes,
                "row_count": raw_records,
                "input_path": input_path_label,
                "outputs": output_hashes,
            }
        ],
        "note": "Only the local seed glossary is locked. Hugging Face sources remain pending/deferred.",
    }
    write_json(dataset_lock_path, dataset_lock)


def run_audit(
    *,
    input_path: Path,
    output_dir: Path,
    report_path: Path,
    run_manifest_path: Path,
    sources_manifest_path: Path | None = None,
    dataset_lock_path: Path | None = None,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    project_root = report_path.resolve().parents[2]
    input_path_label = portable_path(input_path, project_root)
    input_sha_before = sha256_file(input_path)
    input_size_bytes = input_path.stat().st_size
    raw_rows = read_source(input_path)

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    term_counts: Counter[str] = Counter()
    for row in raw_rows:
        grouped[exact_key(row)].append(row)
        term_counts[normalize_key(row["istilah"])] += 1

    unique_entries = sorted(grouped.values(), key=lambda rows: int(rows[0]["_raw_row_number"]))
    records = [build_record(rows[0], len(rows)) for rows in unique_entries]
    curated = [record for record in records if not record["quarantine_reason"]]
    quarantined = [record for record in records if record["quarantine_reason"]]

    duplicate_rows: list[dict[str, Any]] = []
    for rows in unique_entries:
        kept_row = int(rows[0]["_raw_row_number"])
        for duplicate in rows[1:]:
            duplicate_rows.append(
                {
                    "raw_row_number": int(duplicate["_raw_row_number"]),
                    "duplicate_of_row_number": kept_row,
                    "canonical_term": normalize_display_text(duplicate["istilah"]),
                    "regulation_label": normalize_display_text(duplicate["undang_undang"]),
                    "source_url": normalize_display_text(duplicate["url"]),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    curated_csv = output_dir / "legal_term_senses.csv"
    curated_parquet = output_dir / "legal_term_senses.parquet"
    quarantine_csv = output_dir / "quarantined_records.csv"
    quarantine_parquet = output_dir / "quarantined_records.parquet"
    duplicates_csv = output_dir / "duplicate_records.csv"

    write_csv(curated_csv, curated, OUTPUT_COLUMNS)
    write_parquet(curated_parquet, curated)
    write_csv(quarantine_csv, quarantined, OUTPUT_COLUMNS)
    write_parquet(quarantine_parquet, quarantined)
    write_csv(
        duplicates_csv,
        duplicate_rows,
        (
            "raw_row_number",
            "duplicate_of_row_number",
            "canonical_term",
            "regulation_label",
            "source_url",
        ),
    )

    input_sha_after = sha256_file(input_path)
    if input_sha_before != input_sha_after:
        raise RuntimeError("Raw input changed during processing")

    sense_ids_by_term: dict[str, set[str]] = defaultdict(set)
    display_term_by_id: dict[str, str] = {}
    for record in records:
        sense_ids_by_term[record["term_id"]].add(record["sense_id"])
        display_term_by_id[record["term_id"]] = record["canonical_term"]
    multi_sense_terms = sorted(
        display_term_by_id[term_id]
        for term_id, sense_ids in sense_ids_by_term.items()
        if len(sense_ids) > 1
    )

    definition_lengths = [len(record["source_definition"]) for record in records]
    missing_fields = {
        column: sum(not normalize_key(row[column]) for row in raw_rows) for column in RAW_COLUMNS
    }
    status_counts = dict(sorted(Counter(normalize_display_text(row["status"]) for row in raw_rows).items()))
    source_hosts = dict(sorted(Counter(record["source_host"] for record in records).items()))
    quarantine_reason_counts = dict(
        sorted(Counter(record["quarantine_reason"] for record in quarantined).items())
    )

    output_hashes = {
        portable_path(path, project_root): sha256_file(path)
        for path in (
            curated_csv,
            curated_parquet,
            quarantine_csv,
            quarantine_parquet,
            duplicates_csv,
        )
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    stats: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "input_path": input_path_label,
        "input_sha256": input_sha_before,
        "input_size_bytes": input_size_bytes,
        "raw_input_unchanged": input_sha_before == input_sha_after,
        "raw_records": len(raw_rows),
        "exact_duplicate_rows_removed": len(raw_rows) - len(records),
        "unique_records": len(records),
        "unique_terms": len(term_counts),
        "duplicate_term_groups": sum(count > 1 for count in term_counts.values()),
        "records_in_duplicate_term_groups": sum(count for count in term_counts.values() if count > 1),
        "multi_sense_term_groups": len(multi_sense_terms),
        "curated_records": len(curated),
        "quarantined_records": len(quarantined),
        "quarantined_raw_records": sum(record["duplicate_count"] for record in quarantined),
        "retrieval_prefix_removed_records": sum(record["retrieval_prefix_removed"] for record in records),
        "retrieval_prefix_retained_records": sum(not record["retrieval_prefix_removed"] for record in records),
        "definition_length": {
            "min": min(definition_lengths, default=0),
            "median": percentile(definition_lengths, 0.50),
            "p90": percentile(definition_lengths, 0.90),
            "max": max(definition_lengths, default=0),
        },
        "missing_fields": missing_fields,
        "status_counts": status_counts,
        "source_hosts": source_hosts,
        "quarantine_reason_counts": quarantine_reason_counts,
        "multi_sense_terms": multi_sense_terms,
        "output_hashes": output_hashes,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "polars": pl.__version__,
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(stats, multi_sense_terms), encoding="utf-8")
    stats["report_sha256"] = sha256_file(report_path)
    write_json(run_manifest_path, stats)

    if sources_manifest_path is not None and dataset_lock_path is not None:
        update_manifests(
            sources_manifest_path=sources_manifest_path,
            dataset_lock_path=dataset_lock_path,
            input_path_label=input_path_label,
            input_sha256=input_sha_before,
            input_size_bytes=input_size_bytes,
            raw_records=len(raw_rows),
            generated_at=generated_at,
            output_hashes=output_hashes,
        )

    return stats


def default_paths(project_root: Path) -> dict[str, Path]:
    return {
        "input_path": project_root / "data/raw/kamus_hukum.csv",
        "output_dir": project_root / "data/interim",
        "report_path": project_root / "reports/p0/csv-audit.md",
        "run_manifest_path": project_root / "reports/p0/p0-2-run.json",
        "sources_manifest_path": project_root / "manifests/sources.json",
        "dataset_lock_path": project_root / "manifests/dataset-lock.json",
    }
