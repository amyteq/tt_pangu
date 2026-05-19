#!/usr/bin/env python3
"""kca: stable execution layer over legacy tools, with side-effect classification.

Side-effect levels (see COMMANDS.md):
  READ_ONLY | LOCAL_WRITE | REMOTE_WRITE | SUBMISSION
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import nb
import run as run_mod
import kg
import eval as eval_mod
import workspace as workspace_mod
import decisions as decisions_mod


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kca",
        description="Kaggle Code Agent stable CLI. Each subcommand declares a side-effect level.",
    )
    sub = parser.add_subparsers(dest="group", required=True)
    nb.add_parsers(sub)
    run_mod.add_parsers(sub)
    kg.add_parsers(sub)
    eval_mod.add_parsers(sub)
    workspace_mod.add_parsers(sub)
    decisions_mod.add_parsers(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
