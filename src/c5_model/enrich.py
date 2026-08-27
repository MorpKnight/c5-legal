"""P0.4 source-candidate enrichment without legal verification claims."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from c5_model.audit import portable_path, sha256_file, write_json
from c5_model.normalize import normalize_display_text, normalize_key, parse_regulation_label, stable_id


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
ARTICLE_ONE_RE = re.compile(r"^pasal\s+1(?:\D|$)", re.IGNORECASE)

CORPUS_COLUMNS = (
    "global_id",
    "chunk_id",
    "regulation_type",
    "enacting_body",
    "regulation_number",
    "year",
    "about",
    "effective_date",
    "chapter",
    "article",
    "content",
)

CANDIDATE_COLUMNS = (
    "candidate_id",
    "term_id",
    "canonical_term",
    "candidate_rank",
    "dataset_repository",
    "dataset_revision",
    "dataset_global_id",
    "dataset_chunk_id",
    "regulation_type",
    "regulation_number",
    "regulation_year",
    "regulation_title",
    "enacting_body",
    "effective_date",
    "chapter",
    "article",
    "content",
    "term_present",
    "exact_definition_match",
    "definition_token_coverage",
    "title_similarity",
    "metadata_warnings",
    "candidate_status",
)

ENRICHED_COLUMNS = (
    "pilot_index",
    "term_id",
    "canonical_term",
    "primary_regulation_label",
    "primary_regulation_title",
    "source_definition",
    "match_status",
    "identity_row_count",
    "term_candidate_count",
    "top_candidate_id",
    "top_dataset_global_id",
    "top_article",
    "top_content",
    "top_exact_definition_match",
    "top_definition_token_coverage",
    "top_title_similarity",
    "top_metadata_warnings",
    "dataset_repository",
    "dataset_revision",
    "verification_status",
    "official_source_url",
    "review_status",
    "review_notes",
)

REVIEW_COLUMNS = (
    "pilot_index",
    "term_id",
    "canonical_term",
    "primary_regulation_label",
    "match_status",
    "identity_row_count",
    "term_candidate_count",
    "top_dataset_global_id",
    "top_article",
    "top_definition_token_coverage",
    "top_metadata_warnings",
    "verification_status",
    "official_source_url",
    "review_status",
    "review_notes",
)

TYPE_ALIASES = {
    "uu": "undangundang",
    "undangundang": "undangundang",
    "pp": "peraturanpemerintah",
    "perpu": "peraturanpemerintahpenggantiundangundang",
}


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    source = config["source"]
    required = {
        "source_id",
        "repository",
        "revision",
        "relative_path",
        "expected_size_bytes",
        "expected_sha256",
        "authority_role",
    }
    missing = sorted(required - set(source))
    if missing:
        raise ValueError(f"Missing source-enrichment fields: {missing}")
    if source["authority_role"] != "candidate_enrichment_only":
        raise ValueError("P0.4 source must remain candidate enrichment only")
    if config["maximum_candidates_per_term"] < 1:
        raise ValueError("maximum_candidates_per_term must be positive")
    if not 0 <= config["minimum_title_similarity"] <= 1:
        raise ValueError("minimum_title_similarity must be between zero and one")
    return config


def normalize_regulation_type(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", normalize_key(value))
    return TYPE_ALIASES.get(key, key)


def normalize_regulation_number(value: str) -> str:
    match = re.search(r"\d+", normalize_display_text(value))
    if not match:
        return ""
    return str(int(match.group(0)))


def text_tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(normalize_key(value)))


def token_coverage(source_definition: str, candidate_content: str) -> float:
    source_tokens = text_tokens(source_definition)
    if not source_tokens:
        return 0.0
    return len(source_tokens & text_tokens(candidate_content)) / len(source_tokens)


def title_similarity(source_title: str, candidate_title: str) -> float:
    return SequenceMatcher(
        None,
        normalize_key(source_title),
        normalize_key(candidate_title),
    ).ratio()


def metadata_warnings(
    *,
    exact_definition_match: bool,
    article: str,
    title_score: float,
    minimum_title_similarity: float,
) -> str:
    warnings: list[str] = []
    if title_score < minimum_title_similarity:
        warnings.append("low_title_similarity")
    if exact_definition_match and not normalize_key(article).startswith("pasal"):
        warnings.append("definition_found_in_non_article_metadata")
    return "|".join(warnings)


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
    frame.select(columns).write_parquet(
        path,
        compression="zstd",
        statistics=True,
    )


def _candidate_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row["term_present"]),
        -int(row["exact_definition_match"]),
        -row["definition_token_coverage"],
        -row["title_similarity"],
        -int(bool(ARTICLE_ONE_RE.match(row["article"]))),
        row["dataset_global_id"],
    )


def _match_status(
    identity_row_count: int,
    term_candidate_count: int,
    top_candidate: dict[str, Any] | None,
    high_coverage: float,
) -> str:
    if identity_row_count == 0:
        return "regulation_not_found"
    if term_candidate_count == 0:
        return "term_not_found_in_regulation"
    if top_candidate and top_candidate["exact_definition_match"]:
        return "candidate_exact_definition"
    if top_candidate and top_candidate["definition_token_coverage"] >= high_coverage:
        return "candidate_high_coverage"
    return "candidate_needs_review"


def _update_source_manifests(
    *,
    sources_manifest_path: Path | None,
    dataset_lock_path: Path | None,
    summary: dict[str, Any],
    source: dict[str, Any],
    kg_probe: dict[str, Any],
) -> None:
    if sources_manifest_path is not None:
        payload = json.loads(sources_manifest_path.read_text(encoding="utf-8"))
        for record in payload["sources"]:
            if record["source_id"] == source["source_id"]:
                record.update(
                    {
                        "license": source["license_claim"] + " claimed by dataset card; attribution and upstream rights still need review",
                        "processing_status": "processed_as_candidate",
                        "retrieved_at": summary["generated_at"],
                        "revision": source["revision"],
                        "sha256": summary["source_sha256"],
                        "size_bytes": summary["source_size_bytes"],
                        "row_count": summary["source_row_count"],
                        "verification_status": "candidate_corpus_needs_official_review",
                        "outputs": summary["output_hashes"],
                    }
                )
            if record["source_id"] == kg_probe["source_id"]:
                record.update(
                    {
                        "processing_status": kg_probe["decision"],
                        "retrieved_at": summary["generated_at"],
                        "revision": kg_probe["revision"],
                        "probe_result": kg_probe["reason"],
                    }
                )
        payload["status"] = "p0_4_complete"
        write_json(sources_manifest_path, payload)

    if dataset_lock_path is not None:
        payload = json.loads(dataset_lock_path.read_text(encoding="utf-8"))
        locked = {
            "dataset_id": source["source_id"],
            "repository": source["repository"],
            "revision": source["revision"],
            "input_path": summary["source_path"],
            "sha256": summary["source_sha256"],
            "size_bytes": summary["source_size_bytes"],
            "row_count": summary["source_row_count"],
            "outputs": summary["output_hashes"],
            "authority_role": source["authority_role"],
        }
        datasets = [
            record
            for record in payload["datasets"]
            if record["dataset_id"] != source["source_id"]
        ]
        datasets.append(locked)
        payload["datasets"] = datasets
        payload["status"] = "p0_4_source_snapshot_locked"
        payload["updated_at"] = summary["generated_at"]
        payload["note"] = (
            "Local glossary and ID_REG_MD_RAG snapshot are locked. External regulation rows remain candidate evidence and are not official verification."
        )
        write_json(dataset_lock_path, payload)


def render_report(summary: dict[str, Any]) -> str:
    status_lines = "\n".join(
        f"- `{status}`: {count}" for status, count in summary["match_status_counts"].items()
    )
    unresolved_lines = "\n".join(
        f"- {row['canonical_term']} — `{row['match_status']}` — {row['primary_regulation_label']}"
        for row in summary["unresolved_terms"]
    ) or "- Tidak ada"
    matched_lines = "\n".join(
        f"- {row['canonical_term']} — `{row['match_status']}` — `{row['top_article'] or '(missing)'}` — warning: `{row['top_metadata_warnings'] or 'none'}`"
        for row in summary["matched_terms"]
    ) or "- Tidak ada"

    return f"""# P0.4 Source Enrichment

## Outcome

Snapshot `{summary['source_repository']}` diproses sebagai corpus kandidat, bukan sumber hukum terverifikasi. Pencocokan identitas regulasi ditemukan untuk {summary['identity_matched_terms']} dari {summary['pilot_term_count']} istilah pilot; kandidat yang juga memuat istilah ditemukan untuk {summary['term_matched_terms']} istilah.

Tidak ada record yang dinaikkan menjadi `verified`. Hasil ini menunjukkan dataset eksternal dapat membantu sebagian enrichment, tetapi tidak cukup menjadi authority layer untuk pilot AMT tanpa pemeriksaan sumber resmi.

## Locked inputs

- Pilot: `{summary['pilot_path']}`
- Pilot SHA-256: `{summary['pilot_sha256']}`
- Corpus: `{summary['source_repository']}`
- Revision: `{summary['source_revision']}`
- Local snapshot: `{summary['source_path']}`
- Snapshot SHA-256: `{summary['source_sha256']}`
- Snapshot size: {summary['source_size_bytes']:,} byte
- Corpus rows: {summary['source_row_count']:,}
- Claimed dataset license: `{summary['source_license_claim']}`; attribution and upstream rights still require review

## Match statuses

{status_lines}

## Coverage and safety checks

- Identity coverage: {summary['identity_coverage']:.1%}
- Term-in-regulation coverage: {summary['term_coverage']:.1%}
- Exact source-definition matches: {summary['exact_definition_terms']}
- High token-coverage candidates: {summary['high_coverage_terms']}
- Terms with candidate metadata warnings: {summary['terms_with_candidate_metadata_warnings']}
- Officially verified records: {summary['officially_verified_terms']}
- Every enriched term remains `pending_review`: `{str(summary['all_pending_review']).lower()}`
- KG source decision: `{summary['kg_probe']['decision']}`

## Matched candidates

{matched_lines}

## Unresolved terms

{unresolved_lines}

## Decision boundary

- Dataset rows may propose a candidate article and text span.
- Dataset metadata, generated scores, embeddings, and knowledge-graph fields are not legal authority.
- `verified` requires an official regulation URL, identity check, text comparison, and human review.
- Query authoring and retrieval benchmarking must not treat unresolved records as gold labels.
"""


def enrich_sources(
    *,
    pilot_path: Path,
    source_path: Path,
    config_path: Path,
    interim_dir: Path,
    curated_dir: Path,
    manifest_path: Path,
    report_path: Path,
    sources_manifest_path: Path | None = None,
    dataset_lock_path: Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    source = config["source"]
    kg_probe = config["kg_probe"]
    if source_path.stat().st_size != source["expected_size_bytes"]:
        raise ValueError("Source snapshot size does not match the pinned configuration")
    source_sha256 = sha256_file(source_path)
    if source_sha256 != source["expected_sha256"]:
        raise ValueError("Source snapshot SHA-256 does not match the pinned configuration")

    pilot = pl.read_parquet(pilot_path)
    corpus = pl.read_parquet(source_path, columns=list(CORPUS_COLUMNS)).with_columns(
        pl.col("regulation_type")
        .map_elements(normalize_regulation_type, return_dtype=pl.String)
        .alias("_type_key"),
        pl.col("regulation_number")
        .map_elements(normalize_regulation_number, return_dtype=pl.String)
        .alias("_number_key"),
        pl.col("year").cast(pl.String).alias("_year_key"),
    )

    candidate_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, Any]] = []
    for pilot_row in pilot.sort("pilot_index").iter_rows(named=True):
        parsed = parse_regulation_label(pilot_row["primary_regulation_label"])
        source_definition = pilot_row["representative_source_definition"]
        identity_rows = corpus.filter(
            (pl.col("_type_key") == normalize_regulation_type(parsed["regulation_type"]))
            & (pl.col("_number_key") == normalize_regulation_number(parsed["regulation_number"]))
            & (pl.col("_year_key") == parsed["regulation_year"])
        )
        ranked: list[dict[str, Any]] = []
        term_key = normalize_key(pilot_row["canonical_term"])
        definition_key = normalize_key(source_definition)
        for corpus_row in identity_rows.iter_rows(named=True):
            content_key = normalize_key(corpus_row["content"])
            candidate_id = stable_id(
                "candidate",
                source["repository"],
                source["revision"],
                str(corpus_row["global_id"]),
                pilot_row["term_id"],
            )
            term_present = term_key in content_key
            exact_definition_match = bool(definition_key and definition_key in content_key)
            coverage = token_coverage(
                source_definition,
                corpus_row["content"],
            )
            candidate_title_similarity = round(
                title_similarity(
                    pilot_row["primary_regulation_title"],
                    corpus_row["about"],
                ),
                6,
            )
            ranked.append(
                {
                    "candidate_id": candidate_id,
                    "term_id": pilot_row["term_id"],
                    "canonical_term": pilot_row["canonical_term"],
                    "dataset_repository": source["repository"],
                    "dataset_revision": source["revision"],
                    "dataset_global_id": corpus_row["global_id"],
                    "dataset_chunk_id": corpus_row["chunk_id"],
                    "regulation_type": corpus_row["regulation_type"],
                    "regulation_number": corpus_row["regulation_number"],
                    "regulation_year": corpus_row["year"],
                    "regulation_title": corpus_row["about"],
                    "enacting_body": corpus_row["enacting_body"],
                    "effective_date": corpus_row["effective_date"],
                    "chapter": corpus_row["chapter"],
                    "article": corpus_row["article"],
                    "content": corpus_row["content"],
                    "term_present": term_present,
                    "exact_definition_match": exact_definition_match,
                    "definition_token_coverage": round(coverage, 6),
                    "title_similarity": candidate_title_similarity,
                    "metadata_warnings": metadata_warnings(
                        exact_definition_match=exact_definition_match,
                        article=corpus_row["article"],
                        title_score=candidate_title_similarity,
                        minimum_title_similarity=config["minimum_title_similarity"],
                    ),
                    "candidate_status": "candidate_unverified",
                }
            )

        ranked.sort(key=_candidate_rank_key)
        term_candidates = [row for row in ranked if row["term_present"]]
        output_candidates = term_candidates or ranked
        output_candidates = output_candidates[: config["maximum_candidates_per_term"]]
        for candidate_rank, candidate in enumerate(output_candidates, start=1):
            candidate["candidate_rank"] = candidate_rank
            candidate_rows.append(candidate)

        top = output_candidates[0] if output_candidates else None
        match_status = _match_status(
            identity_rows.height,
            len(term_candidates),
            top,
            config["high_definition_token_coverage"],
        )
        enriched_rows.append(
            {
                "pilot_index": pilot_row["pilot_index"],
                "term_id": pilot_row["term_id"],
                "canonical_term": pilot_row["canonical_term"],
                "primary_regulation_label": pilot_row["primary_regulation_label"],
                "primary_regulation_title": pilot_row["primary_regulation_title"],
                "source_definition": source_definition,
                "match_status": match_status,
                "identity_row_count": identity_rows.height,
                "term_candidate_count": len(term_candidates),
                "top_candidate_id": top["candidate_id"] if top else "",
                "top_dataset_global_id": top["dataset_global_id"] if top else None,
                "top_article": top["article"] if top else "",
                "top_content": top["content"] if top else "",
                "top_exact_definition_match": top["exact_definition_match"] if top else False,
                "top_definition_token_coverage": top["definition_token_coverage"] if top else 0.0,
                "top_title_similarity": top["title_similarity"] if top else 0.0,
                "top_metadata_warnings": top["metadata_warnings"] if top else "",
                "dataset_repository": source["repository"],
                "dataset_revision": source["revision"],
                "verification_status": config["verification_status"],
                "official_source_url": "",
                "review_status": "pending_review",
                "review_notes": "",
            }
        )

    interim_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)
    candidate_csv = interim_dir / "source_candidates.csv"
    candidate_parquet = interim_dir / "source_candidates.parquet"
    enriched_csv = curated_dir / "pilot_terms_enriched.csv"
    enriched_parquet = curated_dir / "pilot_terms_enriched.parquet"
    review_csv = curated_dir / "source_review_queue.csv"
    write_csv(candidate_csv, candidate_rows, CANDIDATE_COLUMNS)
    write_parquet(candidate_parquet, candidate_rows, CANDIDATE_COLUMNS)
    write_csv(enriched_csv, enriched_rows, ENRICHED_COLUMNS)
    write_parquet(enriched_parquet, enriched_rows, ENRICHED_COLUMNS)
    write_csv(
        review_csv,
        [{column: row[column] for column in REVIEW_COLUMNS} for row in enriched_rows],
        REVIEW_COLUMNS,
    )

    project_root = report_path.resolve().parents[2]
    output_paths = (
        candidate_csv,
        candidate_parquet,
        enriched_csv,
        enriched_parquet,
        review_csv,
    )
    output_hashes = {
        portable_path(path, project_root): sha256_file(path) for path in output_paths
    }
    status_counts = dict(sorted(Counter(row["match_status"] for row in enriched_rows).items()))
    identity_matched = sum(row["identity_row_count"] > 0 for row in enriched_rows)
    term_matched = sum(row["term_candidate_count"] > 0 for row in enriched_rows)
    exact_definition_terms = sum(row["top_exact_definition_match"] for row in enriched_rows)
    high_coverage_terms = sum(
        row["term_candidate_count"] > 0
        and row["top_definition_token_coverage"] >= config["high_definition_token_coverage"]
        for row in enriched_rows
    )
    metadata_warning_terms = sum(bool(row["top_metadata_warnings"]) for row in enriched_rows)
    generated_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "p0_4_complete",
        "generated_at": generated_at,
        "pilot_path": portable_path(pilot_path, project_root),
        "pilot_sha256": sha256_file(pilot_path),
        "pilot_term_count": len(enriched_rows),
        "config_path": portable_path(config_path, project_root),
        "config_sha256": sha256_file(config_path),
        "source_repository": source["repository"],
        "source_revision": source["revision"],
        "source_path": portable_path(source_path, project_root),
        "source_sha256": source_sha256,
        "source_size_bytes": source_path.stat().st_size,
        "source_row_count": corpus.height,
        "source_license_claim": source["license_claim"],
        "source_authority_role": source["authority_role"],
        "identity_matched_terms": identity_matched,
        "term_matched_terms": term_matched,
        "identity_coverage": identity_matched / len(enriched_rows) if enriched_rows else 0.0,
        "term_coverage": term_matched / len(enriched_rows) if enriched_rows else 0.0,
        "exact_definition_terms": exact_definition_terms,
        "high_coverage_terms": high_coverage_terms,
        "terms_with_candidate_metadata_warnings": metadata_warning_terms,
        "officially_verified_terms": 0,
        "all_pending_review": all(row["review_status"] == "pending_review" for row in enriched_rows),
        "candidate_row_count": len(candidate_rows),
        "match_status_counts": status_counts,
        "matched_terms": [
            {
                "pilot_index": row["pilot_index"],
                "term_id": row["term_id"],
                "canonical_term": row["canonical_term"],
                "match_status": row["match_status"],
                "top_article": row["top_article"],
                "top_metadata_warnings": row["top_metadata_warnings"],
            }
            for row in enriched_rows
            if row["term_candidate_count"] > 0
        ],
        "unresolved_terms": [
            {
                "pilot_index": row["pilot_index"],
                "term_id": row["term_id"],
                "canonical_term": row["canonical_term"],
                "primary_regulation_label": row["primary_regulation_label"],
                "match_status": row["match_status"],
            }
            for row in enriched_rows
            if row["match_status"] in {"regulation_not_found", "term_not_found_in_regulation"}
        ],
        "kg_probe": kg_probe,
        "output_hashes": output_hashes,
    }
    write_json(manifest_path, summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary), encoding="utf-8")
    _update_source_manifests(
        sources_manifest_path=sources_manifest_path,
        dataset_lock_path=dataset_lock_path,
        summary=summary,
        source=source,
        kg_probe=kg_probe,
    )
    return summary


def default_paths(project_root: Path) -> dict[str, Path]:
    config_path = project_root / "configs/source-enrichment.json"
    config = load_config(config_path)
    return {
        "pilot_path": project_root / "data/curated/pilot_terms.parquet",
        "source_path": project_root / config["source"]["relative_path"],
        "config_path": config_path,
        "interim_dir": project_root / "data/interim",
        "curated_dir": project_root / "data/curated",
        "manifest_path": project_root / "manifests/source-enrichment.json",
        "report_path": project_root / "reports/p0/source-enrichment.md",
        "sources_manifest_path": project_root / "manifests/sources.json",
        "dataset_lock_path": project_root / "manifests/dataset-lock.json",
    }
