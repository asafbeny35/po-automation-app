from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_command(args: argparse.Namespace) -> list[str]:
    root = Path(__file__).resolve().parent
    command = [sys.executable, "-m", "pytest", str(root)]
    if args.group == "unit":
        command.extend(["-m", "unit"])
    elif args.group == "api":
        command.extend(["-m", "api"])
    elif args.group == "e2e":
        command.extend(["-m", "e2e"])
    elif args.group == "smoke":
        command.extend(["-m", "unit or api"])
    if args.keyword:
        command.extend(["-k", args.keyword])
    if args.extra:
        command.extend(args.extra)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the PO Automation full-system test suite.")
    parser.add_argument(
        "--group",
        choices=["all", "unit", "api", "e2e", "smoke"],
        default="all",
        help="Subset of the suite to run.",
    )
    parser.add_argument("--keyword", default="", help="Optional pytest -k expression.")
    parser.add_argument("extra", nargs="*", help="Extra raw pytest arguments.")
    args = parser.parse_args()
    command = build_command(args)
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
