"""Equation reversal-symmetry probe (lb25-v1 — LB25 lever #2).

LB25's equation change: in one prompt, **either both the inputs and the output are
reversed, or neither** — i.e. all non-join operators share a single REVERSE/NORMAL
"world". This is exactly Observation 1 of the 24-rule inventory (`rules24.py`: each
rule carries mode ∈ {normal, flip}). Enforcing one mode per prompt halves the
operator-rule search. LB25 is the **earliest** of the seven independent writeups
(LB1/LB3/LB5/LB6/LB10/LB13) confirming equation is *per-problem structured*, not a
global cipher — the same finding our `eq_reprobe.py` quantifies (deduce ≈ 95%).

This probe measures, on the REAL `train.csv` equation-numeric prompts:
  * how often a single consistent mode (normal XOR flip) explains all of a prompt's
    operators (the reversal symmetry holds), and
  * the resulting search reduction (rules considered with vs without the symmetry).

It reuses `eq_reprobe` (parsing + per-operator consistent-rule inference) and
`rules24` (the inventory + modes). CPU-only; needs the gitignored competition
`train.csv` (skips with a clear message if absent).
"""

from __future__ import annotations

import argparse
import csv
import os

from rules24 import RULES, NON_JOIN_RULES
import eq_reprobe

DEFAULT_TRAIN = eq_reprobe.DEFAULT_TRAIN
_NORMAL = [r for r in NON_JOIN_RULES if RULES[r]["mode"] == "normal"]
_FLIP = [r for r in NON_JOIN_RULES if RULES[r]["mode"] == "flip"]


def prompt_modes(examples):
    """Return the set of modes that can consistently explain ALL operators in a prompt.

    For each non-join operator, collect the modes of its consistent rules; the prompt
    is explainable in mode m iff every operator has at least one consistent rule in m.
    Reversal symmetry => exactly one such mode (not both, not neither).
    """
    op_modes = {}
    for op, exs in examples.items():
        rules = eq_reprobe.consistent_rules(op, exs)
        nonjoin = [r for r in rules if RULES[r]["group"] != "join"]
        if not nonjoin:
            continue  # join-only operator: exempt from the mode symmetry
        op_modes[op] = {RULES[r]["mode"] for r in nonjoin}
    if not op_modes:
        return set()
    feasible = {"normal", "flip"}
    for modes in op_modes.values():
        feasible &= modes
    return feasible


def run(train_path, limit=None):
    rows = list(csv.DictReader(open(train_path, encoding="utf-8")))
    eqn = [r for r in rows if eq_reprobe.is_equation_numeric(r["prompt"])]
    if limit:
        eqn = eqn[:limit]
    stats = {"total": 0, "deduce": 0, "single_mode": 0, "both_modes": 0, "no_mode": 0}
    rules_full = rules_sym = 0
    for r in eqn:
        examples, query = eq_reprobe.parse_prompt(r["prompt"])
        if not query or not examples:
            continue
        if query[1] not in examples:
            continue  # restrict the symmetry probe to the deduce subset
        stats["total"] += 1
        stats["deduce"] += 1
        feasible = prompt_modes(examples)
        if len(feasible) == 1:
            stats["single_mode"] += 1
        elif len(feasible) == 2:
            stats["both_modes"] += 1
        else:
            stats["no_mode"] += 1
        # search reduction: rules per operator without vs with the single-mode constraint
        n_ops = sum(
            1
            for op in examples
            if any(RULES[r]["group"] != "join" for r in eq_reprobe.consistent_rules(op, examples[op]))
        )
        rules_full += n_ops * len(NON_JOIN_RULES)
        rules_sym += n_ops * (
            len(_NORMAL) if feasible == {"normal"} else len(_FLIP) if feasible == {"flip"} else len(NON_JOIN_RULES)
        )
    return stats, rules_full, rules_sym


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=DEFAULT_TRAIN)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if not os.path.exists(args.train):
        raise SystemExit(
            f"train.csv not found at {args.train}\n"
            "Download (Kaggle creds, read-only): kaggle competitions download "
            "-c nvidia-nemotron-model-reasoning-challenge -p <dir>"
        )
    stats, rules_full, rules_sym = run(args.train, args.limit)
    d = stats["deduce"] or 1
    print(f"equation-numeric deduce prompts probed: {stats['deduce']}")
    print(f"  reversal symmetry holds (single mode): {stats['single_mode']} ({100 * stats['single_mode'] / d:.1f}%)")
    print(f"  ambiguous (both modes feasible)       : {stats['both_modes']} ({100 * stats['both_modes'] / d:.1f}%)")
    print(f"  unexplained (no single mode)          : {stats['no_mode']} ({100 * stats['no_mode'] / d:.1f}%)")
    if rules_full:
        print(
            f"  rule-search reduction from symmetry   : {rules_full} -> {rules_sym} ({100 * (1 - rules_sym / rules_full):.1f}% fewer)"
        )
    print("LB25 lever #2: a single REVERSE/NORMAL world per prompt (Obs.1) is the reversal symmetry.")


if __name__ == "__main__":
    main()
