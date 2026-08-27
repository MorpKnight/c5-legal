"""Command-line entry points for the P0 pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from c5_model.audit import default_paths, run_audit
from c5_model.enrich import default_paths as default_enrichment_paths
from c5_model.enrich import enrich_sources
from c5_model.pilot import default_paths as default_pilot_paths
from c5_model.pilot import select_pilot
from c5_model.review import default_paths as default_review_paths
from c5_model.review import prepare_source_review, validate_source_review


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PATHS = (
    "configs/p0.yaml",
    "configs/pilot-selection.json",
    "configs/source-enrichment.json",
    "configs/source-review.json",
    "configs/official-source-registry.json",
    "docs/p0-contract.md",
    "manifests/sources.json",
    "manifests/dataset-lock.json",
)


def scaffold_status() -> dict[str, object]:
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).is_file()]
    sources_path = PROJECT_ROOT / "manifests/sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.is_file() else {}
    p0_2_complete = sources.get("status") in {"p0_2_complete", "p0_4_complete"}
    pilot_manifest_path = PROJECT_ROOT / "manifests/pilot-selection.json"
    pilot_manifest = (
        json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
        if pilot_manifest_path.is_file()
        else {}
    )
    p0_3_complete = pilot_manifest.get("status") == "p0_3_complete"
    enrichment_manifest_path = PROJECT_ROOT / "manifests/source-enrichment.json"
    enrichment_manifest = (
        json.loads(enrichment_manifest_path.read_text(encoding="utf-8"))
        if enrichment_manifest_path.is_file()
        else {}
    )
    p0_4_complete = enrichment_manifest.get("status") == "p0_4_complete"
    review_manifest_path = PROJECT_ROOT / "manifests/source-review.json"
    review_manifest = (
        json.loads(review_manifest_path.read_text(encoding="utf-8"))
        if review_manifest_path.is_file()
        else {}
    )
    p0_5_ready = review_manifest.get("status") == "p0_5_ready_for_human_review"
    completed = ["P0.0", "P0.1"]
    if p0_2_complete:
        completed.append("P0.2")
    if p0_3_complete:
        completed.append("P0.3")
    if p0_4_complete:
        completed.append("P0.4")
    return {
        "phase": "P0",
        "completed": completed,
        "next": "P0.5" if p0_4_complete else ("P0.4" if p0_3_complete else ("P0.3" if p0_2_complete else "P0.2")),
        "p0_2_complete": p0_2_complete,
        "p0_3_complete": p0_3_complete,
        "p0_4_complete": p0_4_complete,
        "p0_5_ready_for_human_review": p0_5_ready,
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
    enrichment_parser = subparsers.add_parser(
        "enrich-sources", help="Run P0.4 candidate source enrichment"
    )
    enrichment_defaults = default_enrichment_paths(PROJECT_ROOT)
    enrichment_parser.add_argument(
        "--pilot", type=Path, default=enrichment_defaults["pilot_path"]
    )
    enrichment_parser.add_argument(
        "--source", type=Path, default=enrichment_defaults["source_path"]
    )
    enrichment_parser.add_argument(
        "--config", type=Path, default=enrichment_defaults["config_path"]
    )
    enrichment_parser.add_argument(
        "--interim-dir", type=Path, default=enrichment_defaults["interim_dir"]
    )
    enrichment_parser.add_argument(
        "--curated-dir", type=Path, default=enrichment_defaults["curated_dir"]
    )
    enrichment_parser.add_argument(
        "--manifest", type=Path, default=enrichment_defaults["manifest_path"]
    )
    enrichment_parser.add_argument(
        "--report", type=Path, default=enrichment_defaults["report_path"]
    )
    review_parser = subparsers.add_parser(
        "prepare-p05", help="Prepare P0.5 official-source review and gold-query slots"
    )
    review_defaults = default_review_paths(PROJECT_ROOT)
    review_parser.add_argument("--pilot", type=Path, default=review_defaults["pilot_path"])
    review_parser.add_argument(
        "--enriched", type=Path, default=review_defaults["enriched_path"]
    )
    review_parser.add_argument(
        "--registry", type=Path, default=review_defaults["registry_path"]
    )
    review_parser.add_argument(
        "--config", type=Path, default=review_defaults["config_path"]
    )
    review_parser.add_argument(
        "--evaluation-dir", type=Path, default=review_defaults["evaluation_dir"]
    )
    review_parser.add_argument(
        "--manifest", type=Path, default=review_defaults["manifest_path"]
    )
    review_parser.add_argument(
        "--report", type=Path, default=review_defaults["report_path"]
    )
    validate_parser = subparsers.add_parser(
        "validate-p05", help="Validate manually reviewed P0.5 CSV files"
    )
    validate_parser.add_argument(
        "--source-review", type=Path, default=review_defaults["source_review_path"]
    )
    validate_parser.add_argument(
        "--gold-queries", type=Path, default=review_defaults["gold_queries_path"]
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
    elif args.command == "enrich-sources":
        summary = enrich_sources(
            pilot_path=args.pilot,
            source_path=args.source,
            config_path=args.config,
            interim_dir=args.interim_dir,
            curated_dir=args.curated_dir,
            manifest_path=args.manifest,
            report_path=args.report,
            sources_manifest_path=enrichment_defaults["sources_manifest_path"],
            dataset_lock_path=enrichment_defaults["dataset_lock_path"],
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "prepare-p05":
        summary = prepare_source_review(
            pilot_path=args.pilot,
            enriched_path=args.enriched,
            registry_path=args.registry,
            config_path=args.config,
            evaluation_dir=args.evaluation_dir,
            manifest_path=args.manifest,
            report_path=args.report,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "validate-p05":
        summary = validate_source_review(
            source_review_path=args.source_review,
            gold_queries_path=args.gold_queries,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
