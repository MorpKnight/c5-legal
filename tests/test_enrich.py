from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from c5_model.enrich import enrich_sources


class SourceEnrichmentTests(unittest.TestCase):
    def test_enrichment_preserves_unverified_boundary(self) -> None:
        pilot_rows = [
            {
                "pilot_index": 1,
                "term_id": "term_data",
                "canonical_term": "Data Pribadi",
                "primary_regulation_label": "Undang-Undang Nomor 27 Tahun 2022",
                "primary_regulation_title": "Perlindungan Data Pribadi",
                "representative_source_definition": "Data Pribadi adalah data tentang orang yang teridentifikasi.",
            },
            {
                "pilot_index": 2,
                "term_id": "term_missing_in_text",
                "canonical_term": "Istilah Tidak Ada",
                "primary_regulation_label": "Undang-Undang Nomor 27 Tahun 2022",
                "primary_regulation_title": "Perlindungan Data Pribadi",
                "representative_source_definition": "Istilah Tidak Ada adalah contoh.",
            },
            {
                "pilot_index": 3,
                "term_id": "term_missing_regulation",
                "canonical_term": "Regulasi Hilang",
                "primary_regulation_label": "Undang-Undang Nomor 99 Tahun 2099",
                "primary_regulation_title": "Regulasi Hilang",
                "representative_source_definition": "Regulasi Hilang adalah contoh.",
            },
        ]
        corpus_rows = [
            {
                "global_id": 1,
                "chunk_id": 1,
                "regulation_type": "UNDANG-UNDANG",
                "enacting_body": "REPUBLIK INDONESIA",
                "regulation_number": "27",
                "year": "2022",
                "about": "PERLINDUNGAN DATA PRIBADI",
                "effective_date": "17 Oktober 2022",
                "chapter": "BAB I",
                "article": "Pasal 1",
                "content": "Data Pribadi adalah data tentang orang yang teridentifikasi.",
            },
            {
                "global_id": 2,
                "chunk_id": 1,
                "regulation_type": "UNDANG-UNDANG",
                "enacting_body": "REPUBLIK INDONESIA",
                "regulation_number": "27",
                "year": "2022",
                "about": "PERLINDUNGAN DATA PRIBADI",
                "effective_date": "17 Oktober 2022",
                "chapter": "BAB II",
                "article": "Pasal 2",
                "content": "Undang-Undang ini berlaku untuk pemrosesan tertentu.",
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pilot_path = root / "data/curated/pilot_terms.parquet"
            source_path = root / "data/raw/source.parquet"
            config_path = root / "configs/source-enrichment.json"
            pilot_path.parent.mkdir(parents=True)
            source_path.parent.mkdir(parents=True)
            config_path.parent.mkdir(parents=True)
            pl.DataFrame(pilot_rows, strict=False).write_parquet(pilot_path)
            pl.DataFrame(corpus_rows, strict=False).write_parquet(source_path)
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            config = {
                "schema_version": 1,
                "source": {
                    "source_id": "test_source",
                    "repository": "test/source",
                    "revision": "test-revision",
                    "filename": "source.parquet",
                    "relative_path": "data/raw/source.parquet",
                    "expected_size_bytes": source_path.stat().st_size,
                    "expected_sha256": source_hash,
                    "license_claim": "test-only",
                    "authority_role": "candidate_enrichment_only",
                },
                "kg_probe": {
                    "source_id": "test_kg",
                    "repository": "test/kg",
                    "revision": "test-revision",
                    "decision": "deferred_after_probe",
                    "reason": "test",
                },
                "maximum_candidates_per_term": 2,
                "high_definition_token_coverage": 0.8,
                "verification_status": "needs_official_source_review",
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            summary = enrich_sources(
                pilot_path=pilot_path,
                source_path=source_path,
                config_path=config_path,
                interim_dir=root / "data/interim",
                curated_dir=root / "data/curated",
                manifest_path=root / "manifests/source-enrichment.json",
                report_path=root / "reports/p0/source-enrichment.md",
            )
            enriched = pl.read_parquet(root / "data/curated/pilot_terms_enriched.parquet")
            statuses = dict(zip(enriched["term_id"], enriched["match_status"], strict=True))

            self.assertEqual(summary["pilot_term_count"], 3)
            self.assertEqual(summary["identity_matched_terms"], 2)
            self.assertEqual(summary["term_matched_terms"], 1)
            self.assertEqual(summary["officially_verified_terms"], 0)
            self.assertEqual(statuses["term_data"], "candidate_exact_definition")
            self.assertEqual(
                statuses["term_missing_in_text"],
                "term_not_found_in_regulation",
            )
            self.assertEqual(statuses["term_missing_regulation"], "regulation_not_found")
            self.assertTrue(
                (enriched["verification_status"] == "needs_official_source_review").all()
            )
            self.assertTrue((enriched["review_status"] == "pending_review").all())


if __name__ == "__main__":
    unittest.main()
