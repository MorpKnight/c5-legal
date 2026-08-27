from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from c5_model.review import (
    GOLD_QUERY_COLUMNS,
    SOURCE_REVIEW_COLUMNS,
    prepare_source_review,
    validate_source_review,
)


class SourceReviewTests(unittest.TestCase):
    def _prepare_fixture(self, root: Path) -> tuple[dict, Path, Path]:
        pilot_path = root / "data/curated/pilot_terms.parquet"
        enriched_path = root / "data/curated/pilot_terms_enriched.parquet"
        config_path = root / "configs/source-review.json"
        registry_path = root / "configs/official-source-registry.json"
        pilot_path.parent.mkdir(parents=True)
        config_path.parent.mkdir(parents=True)

        pilot_rows = [
            {
                "pilot_index": 1,
                "term_id": "term_data",
                "canonical_term": "Data Pribadi",
                "selection_bucket": "anchor",
                "primary_regulation_label": "Undang-Undang Nomor 27 Tahun 2022",
                "primary_regulation_title": "Pelindungan Data Pribadi",
            },
            {
                "pilot_index": 2,
                "term_id": "term_fidusia",
                "canonical_term": "Jaminan Fidusia",
                "selection_bucket": "domain_focus",
                "primary_regulation_label": "Undang-Undang Nomor 42 Tahun 1999",
                "primary_regulation_title": "Jaminan Fidusia",
            },
        ]
        enriched_rows = [
            {
                **row,
                "match_status": "regulation_not_found",
                "top_candidate_id": "",
                "top_dataset_global_id": None,
                "top_article": "",
                "top_metadata_warnings": "",
            }
            for row in pilot_rows
        ]
        pl.DataFrame(pilot_rows, strict=False).write_parquet(pilot_path)
        pl.DataFrame(enriched_rows, strict=False).write_parquet(enriched_path)
        registry = {
            "schema_version": 1,
            "sources": [
                {
                    "source_id": "official_uu_27_2022",
                    "regulation_label": "Undang-Undang Nomor 27 Tahun 2022",
                    "regulation_title": "Pelindungan Data Pribadi",
                    "official_portal_url": "https://peraturan.go.id/id/uu-no-27-tahun-2022",
                    "status_signal": "status_not_reviewed",
                    "status_note": "review",
                },
                {
                    "source_id": "official_uu_42_1999",
                    "regulation_label": "Undang-Undang Nomor 42 Tahun 1999",
                    "regulation_title": "Jaminan Fidusia",
                    "official_portal_url": "https://peraturan.go.id/id/uu-no-42-tahun-1999",
                    "status_signal": "status_not_reviewed",
                    "status_note": "review",
                },
            ],
        }
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        config = {
            "schema_version": 1,
            "source_registry_path": "configs/official-source-registry.json",
            "gold_query_slots_per_term": 3,
            "locked_test_term_count": 1,
            "locked_test_seed": "test-seed",
        }
        config_path.write_text(json.dumps(config), encoding="utf-8")
        summary = prepare_source_review(
            pilot_path=pilot_path,
            enriched_path=enriched_path,
            registry_path=registry_path,
            config_path=config_path,
            evaluation_dir=root / "data/evaluation",
            manifest_path=root / "manifests/source-review.json",
            report_path=root / "reports/p0/source-review.md",
        )
        return summary, root / "data/evaluation/source_review_queue.csv", root / "data/evaluation/gold_queries.csv"

    def test_prepare_is_deterministic_and_does_not_generate_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            summary, source_path, gold_path = self._prepare_fixture(Path(temporary_directory))
            with source_path.open(encoding="utf-8", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            with gold_path.open(encoding="utf-8", newline="") as handle:
                gold_rows = list(csv.DictReader(handle))

            self.assertEqual(summary["source_review_count"], 2)
            self.assertEqual(summary["gold_query_slot_count"], 6)
            self.assertEqual(summary["locked_test_term_count"], 1)
            self.assertEqual(set(source_rows[0]), set(SOURCE_REVIEW_COLUMNS))
            self.assertEqual(set(gold_rows[0]), set(GOLD_QUERY_COLUMNS))
            self.assertTrue(
                all(row["source_review_status"] == "pending_human_review" for row in source_rows)
            )
            self.assertTrue(
                all(row["review_status"] == "blocked_unverified_source" for row in gold_rows)
            )
            self.assertTrue(all(row["query_text"] == "" for row in gold_rows))
            self.assertEqual(
                validate_source_review(
                    source_review_path=source_path,
                    gold_queries_path=gold_path,
                )["gold_query_slot_count"],
                6,
            )

    def test_validation_rejects_incomplete_verified_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, source_path, gold_path = self._prepare_fixture(root)
            with source_path.open(encoding="utf-8", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            source_rows[0]["source_review_status"] = "verified"
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SOURCE_REVIEW_COLUMNS)
                writer.writeheader()
                writer.writerows(source_rows)

            with self.assertRaisesRegex(ValueError, "official_document_url_missing"):
                validate_source_review(
                    source_review_path=source_path,
                    gold_queries_path=gold_path,
                )

    def test_validation_rejects_approved_query_before_source_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, source_path, gold_path = self._prepare_fixture(root)
            with gold_path.open(encoding="utf-8", newline="") as handle:
                gold_rows = list(csv.DictReader(handle))
            gold_rows[0].update(
                {
                    "query_text": "Uraian mengenai informasi seseorang yang dapat dikenali",
                    "query_type": "definition_paraphrase",
                    "review_status": "approved",
                    "author_status": "human_authored",
                    "author_id": "author",
                    "reviewer_id": "reviewer",
                    "reviewed_at": "2026-08-27T00:00:00+00:00",
                }
            )
            with gold_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=GOLD_QUERY_COLUMNS)
                writer.writeheader()
                writer.writerows(gold_rows)

            with self.assertRaisesRegex(ValueError, "approved before source verification"):
                validate_source_review(
                    source_review_path=source_path,
                    gold_queries_path=gold_path,
                )


if __name__ == "__main__":
    unittest.main()
