"""Local pass@2 evaluation harness for ARC-AGI-2.

Score a submission.json, or run a built-in baseline, against a split that carries
ground-truth solutions (the public training/evaluation splits do).

    # score an existing submission against the public eval split
    python competitions/arc-agi2/eval/evaluate.py --submission sub.json --split evaluation

    # run a baseline and score it (validates the harness end-to-end)
    python competitions/arc-agi2/eval/evaluate.py --baseline identity --split evaluation

    # write a baseline's predictions to a submission file without scoring
    python competitions/arc-agi2/eval/evaluate.py --baseline identity --split test \\
        --layout kaggle --out submission.json --no-score
"""

from __future__ import annotations

import argparse
import sys

import baselines
from arc_io import (
    DEFAULT_GITHUB_ROOT,
    DEFAULT_KAGGLE_ROOT,
    load_github_split,
    load_kaggle_split,
    load_solutions,
    load_submission,
    write_submission,
)
from metric import score_submission


def _load_tasks(split: str, layout: str):
    if layout == "github":
        return load_github_split(split, DEFAULT_GITHUB_ROOT)
    return load_kaggle_split(split, DEFAULT_KAGGLE_ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--submission", help="path to a submission.json to score")
    src.add_argument("--baseline", choices=sorted(baselines.REGISTRY), help="run a built-in baseline")
    ap.add_argument(
        "--split", default="evaluation", help="github: training|evaluation ; kaggle: training|evaluation|test"
    )
    ap.add_argument("--layout", default="github", choices=["github", "kaggle"])
    ap.add_argument("--out", help="write the (baseline) submission to this path")
    ap.add_argument("--no-score", action="store_true", help="skip scoring (e.g. hidden test split)")
    ap.add_argument("--show-fails", type=int, default=0, help="print N solved/failed task ids")
    args = ap.parse_args(argv)

    tasks = _load_tasks(args.split, args.layout)
    print(f"loaded {len(tasks)} tasks from split='{args.split}' layout='{args.layout}'")

    if args.baseline:
        submission = baselines.build_submission(tasks, args.baseline)
        print(f"built baseline '{args.baseline}' over {len(submission)} tasks")
    else:
        submission = load_submission(args.submission)
        print(f"loaded submission with {len(submission)} tasks from {args.submission}")

    if args.out:
        write_submission(submission, args.out)
        print(f"wrote submission -> {args.out}")

    if args.no_score:
        return 0

    solutions = load_solutions(tasks)
    if not solutions:
        print("WARNING: this split carries no solutions; cannot score. Use --no-score + --out.")
        return 1

    report = score_submission(submission, solutions)
    print("\n" + str(report))

    if args.show_fails:
        solved = [t for t, s in report.per_task.items() if s >= 1.0][: args.show_fails]
        failed = [t for t, s in report.per_task.items() if s <= 0.0][: args.show_fails]
        print(f"\nsolved (sample): {solved}")
        print(f"failed (sample): {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
