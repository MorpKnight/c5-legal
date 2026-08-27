from __future__ import annotations

import json
import unittest
from pathlib import Path

from c5_model.cli import PROJECT_ROOT, scaffold_status


class ScaffoldTests(unittest.TestCase):
    def test_required_scaffold_is_ready(self) -> None:
        status = scaffold_status()

        self.assertTrue(status["scaffold_ready"])
        self.assertFalse(status["p0_2_started"])
        self.assertEqual(status["next"], "P0.2")
        self.assertEqual(status["missing_paths"], [])

    def test_sources_are_not_processed_yet(self) -> None:
        manifest_path = PROJECT_ROOT / "manifests/sources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        statuses = {source["processing_status"] for source in manifest["sources"]}
        self.assertNotIn("processed", statuses)
        self.assertEqual(manifest["status"], "pending_p0_2")

    def test_generated_data_directories_exist(self) -> None:
        expected = (
            "data/raw",
            "data/interim",
            "data/curated",
            "data/evaluation",
            "data/samples",
            "artifacts",
            "exports",
            "reports/p0",
        )

        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_dir())


if __name__ == "__main__":
    unittest.main()

