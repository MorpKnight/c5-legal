"""Command-line entry points for the P0 pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from c5_model.audit import default_paths, run_audit
from c5_model.pilot import default_paths as default_pilot_paths
from c5_model.pilot import select_pilot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PATHS = (
    "configs/p0.yaml",
    "configs/pilot-selection.json",
    "docs/p0-contract.md",
    "manifests/sources.json",
    "manifests/dataset-lock.json",
)


def scaffold_status() -> dict[str, object]:
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).is_file()]
    sources_path = PROJECT_ROOT / "manifests/sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.is_file() else {}
    p0_2_complete = sources.get("status") == "p0_2_complete"
    pilot_manifest_path = PROJECT_ROOT / "manifests/pilot-selection.json"
    pilot_manifest = (
        json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
        if pilot_manifest_path.is_file()
        else {}
    )
    p0_3_complete = pilot_manifest.get("status") == "p0_3_complete"
    completed = ["P0.0", "P0.1"]
    if p0_2_complete:
        completed.append("P0.2")
    if p0_3_complete:
        completed.append("P0.3")
    return {
        "phase": "P0",
        "completed": completed,
        "next": "P0.4" if p0_3_complete else ("P0.3" if p0_2_complete else "P0.2"),
        "p0_2_complete": p0_2_complete,
        "p0_3_complete": p0_3_complete,
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
    pilot_parser = subparsers.add_parser(
        "select-pilot", help="Select the deterministic P0.3 pilot terms"
    )
    pilot_defaults = default_pilot_paths(PROJECT_ROOT)
    pilot_parser.add_argument("--input", type=Path, default=pilot_defaults["input_path"])
    pilot_parser.add_argument(
        "--quarantine", type=Path, default=pilot_defaults["quarantine_path"]
    )
    pilot_parser.add_argument("--config", type=Path, default=pilot_defaults["config_path"])
    pilot_parser.add_argument(
        "--output-dir", type=Path, default=pilot_defaults["output_dir"]
    )
    pilot_parser.add_argument(
        "--manifest", type=Path, default=pilot_defaults["manifest_path"]
    )
    pilot_parser.add_argument("--report", type=Path, default=pilot_defaults["report_path"])
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
    elif args.command == "select-pilot":
        summary = select_pilot(
            input_path=args.input,
            quarantine_path=args.quarantine,
            config_path=args.config,
            output_dir=args.output_dir,
            manifest_path=args.manifest,
            report_path=args.report,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
