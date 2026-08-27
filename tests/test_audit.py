from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import polars as pl

from c5_model.audit import quarantine_reason, run_audit
from c5_model.cli import PROJECT_ROOT
from c5_model.normalize import parse_regulation_label, strip_term_prefix


class NormalizeTests(unittest.TestCase):
    def test_strips_answer_bearing_prefix(self) -> None:
        text, removed = strip_term_prefix(
            "Data Pribadi",
            "Data Pribadi adalah informasi mengenai orang yang dapat dikenali.",
        )

        self.assertTrue(removed)
        self.assertEqual(text, "informasi mengenai orang yang dapat dikenali.")

    def test_preserves_definition_without_prefix(self) -> None:
        definition = "Informasi mengenai orang yang dapat dikenali."
        text, removed = strip_term_prefix("Data Pribadi", definition)

        self.assertFalse(removed)
        self.assertEqual(text, definition)

    def test_strips_term_before_defined_alias(self) -> None:
        text, removed = strip_term_prefix(
            "Anggaran Pendapatan dan Belanja Negara",
            "Anggaran Pendapatan dan Belanja Negara, selanjutnya disebut APBN, adalah rencana keuangan tahunan negara.",
        )

        self.assertTrue(removed)
        self.assertEqual(text, "selanjutnya disebut APBN, adalah rencana keuangan tahunan negara.")

    def test_parses_regulation_identity(self) -> None:
        parsed = parse_regulation_label("Undang-Undang Nomor 27 Tahun 2022")

        self.assertEqual(parsed["regulation_type"], "Undang-Undang")
        self.assertEqual(parsed["regulation_number"], "27")
        self.assertEqual(parsed["regulation_year"], "2022")


class AuditTests(unittest.TestCase):
    def test_unparseable_regulation_identity_is_quarantined(self) -> None:
        row = {
            "istilah": "Istilah Rusak",
            "pengertian": "Istilah Rusak adalah contoh.",
            "undang_undang": "Bukan Identitas Regulasi",
            "uu": "Judul Contoh",
            "url": "https://example.invalid/rusak",
            "status": "OK",
        }
        regulation = {
            "regulation_label": "Bukan Identitas Regulasi",
            "regulation_type": "Bukan Identitas Regulasi",
            "regulation_number": "",
            "regulation_year": "",
        }

        self.assertEqual(
            quarantine_reason(row, regulation),
            "unparseable_regulation_identity",
        )

    def test_fixture_audit_is_deterministic_and_quarantines_unverified(self) -> None:
        source = PROJECT_ROOT / "data/samples/kamus_hukum_fixture.csv"
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stats = run_audit(
                input_path=source,
                output_dir=root / "interim",
                report_path=root / "report.md",
                run_manifest_path=root / "run.json",
            )

            curated = pl.read_parquet(root / "interim/legal_term_senses.parquet")
            quarantined = pl.read_parquet(root / "interim/quarantined_records.parquet")

            self.assertEqual(stats["raw_records"], 5)
            self.assertEqual(stats["exact_duplicate_rows_removed"], 1)
            self.assertEqual(stats["unique_records"], 4)
            self.assertEqual(stats["unique_terms"], 3)
            self.assertEqual(stats["multi_sense_term_groups"], 1)
            self.assertEqual(stats["curated_records"], 3)
            self.assertEqual(stats["quarantined_records"], 1)
            self.assertEqual(stats["quarantined_raw_records"], 1)
            self.assertEqual(curated.height, 3)
            self.assertEqual(quarantined.height, 1)
            self.assertEqual(quarantined["verification_status"][0], "quarantined")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)


if __name__ == "__main__":
    unittest.main()
