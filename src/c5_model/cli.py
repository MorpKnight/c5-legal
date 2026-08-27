"""Command-line entry points for the P0 pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from c5_model.audit import default_paths, run_audit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PATHS = (
    "configs/p0.yaml",
    "docs/p0-contract.md",
    "manifests/sources.json",
    "manifests/dataset-lock.json",
)


def scaffold_status() -> dict[str, object]:
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).is_file()]
    sources_path = PROJECT_ROOT / "manifests/sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.is_file() else {}
    p0_2_complete = sources.get("status") == "p0_2_complete"
    completed = ["P0.0", "P0.1"]
    if p0_2_complete:
        completed.append("P0.2")
    return {
        "phase": "P0",
        "completed": completed,
        "next": "P0.3" if p0_2_complete else "P0.2",
        "p0_2_complete": p0_2_complete,
        "scaffold_ready": not missing,
        "missing_paths": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="c5-model P0 utilities")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Show the current P0 state")
    audit_parser = subparsers.add_parser("audit", help="Run the P0.2 glossary audit")
    defaults = default_paths(PROJECT_ROOT)
    audit_parser.add_argument("--input", type=Path, default=defaults["input_path"])
    audit_parser.add_argument("--output-dir", type=Path, default=defaults["output_dir"])
    audit_parser.add_argument("--report", type=Path, default=defaults["report_path"])
    audit_parser.add_argument(
        "--run-manifest",
        type=Path,
        default=defaults["run_manifest_path"],
    )
    args = parser.parse_args()

    if args.command in (None, "status"):
        print(json.dumps(scaffold_status(), indent=2))
    elif args.command == "audit":
        stats = run_audit(
            input_path=args.input,
            output_dir=args.output_dir,
            report_path=args.report,
            run_manifest_path=args.run_manifest,
            sources_manifest_path=defaults["sources_manifest_path"],
            dataset_lock_path=defaults["dataset_lock_path"],
        )
        print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
