from __future__ import annotations

import argparse

from _types import SideEffect
from _util import stub_emit


def cmd_score(args: argparse.Namespace) -> int:
    return stub_emit("eval score", SideEffect.READ_ONLY)


def cmd_compare(args: argparse.Namespace) -> int:
    return stub_emit("eval compare", SideEffect.READ_ONLY)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    ev = sub.add_parser("eval", help="Evaluation harness (stubs)")
    ev_sub = ev.add_subparsers(dest="eval_cmd", required=True)

    p_score = ev_sub.add_parser(
        "score", help="Score predictions vs labels (READ_ONLY) [stub]"
    )
    p_score.add_argument("--pred", required=True)
    p_score.add_argument("--truth", required=True)
    p_score.add_argument("--json", action="store_true")
    p_score.set_defaults(func=cmd_score)

    p_cmp = ev_sub.add_parser("compare", help="Compare runs (READ_ONLY) [stub]")
    p_cmp.add_argument("--run-a", required=True)
    p_cmp.add_argument("--run-b", required=True)
    p_cmp.add_argument("--json", action="store_true")
    p_cmp.set_defaults(func=cmd_compare)
