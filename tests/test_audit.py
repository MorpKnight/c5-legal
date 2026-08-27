from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from c5_model.audit import quarantine_reason, run_audit, update_manifests
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
    def test_manifest_update_preserves_downstream_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources_path = root / "sources.json"
            lock_path = root / "dataset-lock.json"
            sources_path.write_text(
                '{"status":"p0_4_complete","sources":[{"source_id":"local_kamus_hukum","sha256":"same"},{"source_id":"hf_id_reg_md_rag","processing_status":"processed_as_candidate"}]}',
                encoding="utf-8",
            )
            lock_path.write_text(
                '{"schema_version":1,"status":"p0_4_source_snapshot_locked","created_at":"earlier","datasets":[{"dataset_id":"local_kamus_hukum"},{"dataset_id":"hf_id_reg_md_rag","sha256":"hf-hash"}],"note":"preserve"}',
                encoding="utf-8",
            )

            update_manifests(
                sources_manifest_path=sources_path,
                dataset_lock_path=lock_path,
                input_path_label="data/raw/kamus_hukum.csv",
                input_sha256="same",
                input_size_bytes=10,
                raw_records=2,
                generated_at="later",
                output_hashes={"output": "hash"},
            )

            sources = json.loads(sources_path.read_text(encoding="utf-8"))
            dataset_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(sources["status"], "p0_4_complete")
            self.assertEqual(dataset_lock["status"], "p0_4_source_snapshot_locked")
            self.assertEqual(dataset_lock["note"], "preserve")
            self.assertEqual(
                {record["dataset_id"] for record in dataset_lock["datasets"]},
                {"local_kamus_hukum", "hf_id_reg_md_rag"},
            )

    def test_manifest_update_rejects_changed_seed_after_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources_path = root / "sources.json"
            lock_path = root / "dataset-lock.json"
            sources_path.write_text(
                '{"status":"p0_4_complete","sources":[{"source_id":"local_kamus_hukum","sha256":"old"}]}',
                encoding="utf-8",
            )
            lock_path.write_text(
                '{"schema_version":1,"status":"p0_4_source_snapshot_locked","datasets":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Cannot change the P0.2 seed"):
                update_manifests(
                    sources_manifest_path=sources_path,
                    dataset_lock_path=lock_path,
                    input_path_label="data/raw/kamus_hukum.csv",
                    input_sha256="new",
                    input_size_bytes=10,
                    raw_records=2,
                    generated_at="later",
                    output_hashes={"output": "hash"},
                )

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
