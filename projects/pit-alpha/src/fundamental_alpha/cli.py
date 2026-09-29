"""Command-line entry point."""

from __future__ import annotations

import argparse
import json

from .pipeline import run_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PIT fundamental alpha research demo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run the reproducible synthetic-data study")
    demo.add_argument("--output", default="outputs/demo", help="artifact directory")
    demo.add_argument("--seed", default=42, type=int)
    demo.add_argument("--split-date", default="2022-01-01")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "demo":
        summary = run_demo(args.output, seed=args.seed, split_date=args.split_date)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

