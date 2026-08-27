"""Small dependency-free project status command for the P0 scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PATHS = (
    "configs/p0.yaml",
    "docs/p0-contract.md",
    "manifests/sources.json",
    "manifests/dataset-lock.json",
)


def scaffold_status() -> dict[str, object]:
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).is_file()]
    return {
        "phase": "P0",
        "completed": ["P0.0", "P0.1"],
        "next": "P0.2",
        "p0_2_started": False,
        "scaffold_ready": not missing,
        "missing_paths": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="c5-model P0 utilities")
    parser.add_argument(
        "command",
        choices=("status",),
        nargs="?",
        default="status",
        help="Command to run (default: status)",
    )
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(scaffold_status(), indent=2))


if __name__ == "__main__":
    main()

