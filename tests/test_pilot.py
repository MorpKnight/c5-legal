from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from c5_model.pilot import select_pilot


def synthetic_row(index: int, *, term: str | None = None, warning: str = "") -> dict[str, object]:
    canonical_term = term or f"Istilah Contoh {index:02d}"
    definition = f"{canonical_term} adalah definisi contoh nomor {index}."
    if index % 4 == 0:
        definition = f"{canonical_term}, selanjutnya disebut IC{index}, adalah definisi contoh."
    if index % 5 == 0:
        definition += " Masa berlaku 30 hari."
    if index % 7 == 0:
        definition += " " + ("uraian panjang " * 40)
    return {
        "term_id": f"term_{index:03d}",
        "sense_id": f"sense_{index:03d}",
        "source_id": f"source_{index:03d}",
        "raw_row_number": index + 2,
        "duplicate_count": 1,
        "canonical_term": canonical_term,
        "normalized_term": canonical_term.casefold(),
        "source_definition": definition,
        "retrieval_text": definition.split(" adalah ", 1)[-1],
        "retrieval_prefix_removed": not warning,
        "normalization_warning": warning,
        "regulation_label": f"Undang-Undang Nomor {index} Tahun 2020",
        "regulation_type": "Undang-Undang",
        "regulation_number": str(index),
        "regulation_year": "2020",
        "regulation_title": "Data dan Usaha" if index < 15 else f"Bidang {index}",
        "source_url": f"https://example.invalid/{index}",
        "source_host": "example.invalid",
        "source_status": "OK",
        "verification_status": "candidate_secondary_source",
        "quarantine_reason": "",
    }


class PilotSelectionTests(unittest.TestCase):
    def test_selection_is_deterministic_and_excludes_warning(self) -> None:
        rows = [synthetic_row(index) for index in range(1, 61)]
        rows.append(synthetic_row(99, term="Istilah Bermasalah", warning="term_prefix_not_found"))
        rows.append({**synthetic_row(61, term="Istilah Multi"), "term_id": "term_multi"})
        rows.append(
            {
                **synthetic_row(62, term="Istilah Multi"),
                "term_id": "term_multi",
                "sense_id": "sense_multi_2",
            }
        )
        quarantine = pl.DataFrame([synthetic_row(100, term="Istilah Karantina")], strict=False)
        quarantine = quarantine.with_columns(
            pl.lit("quarantined").alias("verification_status"),
            pl.lit("source_unverified").alias("quarantine_reason"),
        )
        config = {
            "schema_version": 1,
            "target_count": 12,
            "seed": "test-seed",
            "max_per_primary_source": 3,
            "near_neighbor_min_jaccard": 0.5,
            "anchors": ["Istilah Contoh 01", "Istilah Contoh 02"],
            "domain_focus_terms": ["Istilah Contoh 03", "Istilah Contoh 04"],
            "quotas": {
                "anchor": 2,
                "multi_sense": 1,
                "domain_focus": 2,
                "near_neighbor": 2,
                "alias": 1,
                "numeric": 1,
                "long_definition": 1,
                "typical_fill": 2
            }
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "data/interim/legal_term_senses.parquet"
            quarantine_path = root / "data/interim/quarantined_records.parquet"
            config_path = root / "configs/pilot-selection.json"
            input_path.parent.mkdir(parents=True)
            config_path.parent.mkdir(parents=True)
            pl.DataFrame(rows, strict=False).write_parquet(input_path)
            quarantine.write_parquet(quarantine_path)
            config_path.write_text(json.dumps(config), encoding="utf-8")

            first = select_pilot(
                input_path=input_path,
                quarantine_path=quarantine_path,
                config_path=config_path,
                output_dir=root / "data/curated",
                manifest_path=root / "manifests/pilot-selection.json",
                report_path=root / "reports/p0/pilot-selection.md",
            )
            first_terms = [row["term_id"] for row in first["selected_terms"]]
            second = select_pilot(
                input_path=input_path,
                quarantine_path=quarantine_path,
                config_path=config_path,
                output_dir=root / "data/curated",
                manifest_path=root / "manifests/pilot-selection.json",
                report_path=root / "reports/p0/pilot-selection.md",
            )
            second_terms = [row["term_id"] for row in second["selected_terms"]]
            selected_frame = pl.read_parquet(root / "data/curated/pilot_terms.parquet")
            review_queue = pl.read_csv(root / "data/curated/pilot_review_queue.csv")

            self.assertEqual(first_terms, second_terms)
            self.assertEqual(len(first_terms), 12)
            self.assertEqual(len(set(first_terms)), 12)
            self.assertIn("term_001", first_terms)
            self.assertIn("term_002", first_terms)
            self.assertNotIn("term_099", first_terms)
            self.assertEqual(selected_frame.height, 12)
            self.assertEqual(review_queue.height, 2)
            self.assertTrue(
                (selected_frame["review_status"] == "pending_review").all()
            )


if __name__ == "__main__":
    unittest.main()
