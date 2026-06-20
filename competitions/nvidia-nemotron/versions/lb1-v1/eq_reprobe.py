"""Equation-numeric re-probe (lb1-v1, plan checklist #1; CPU, no GPU).

Settles the premise conflict flagged in `gap_analysis.md`: our EQ-0/EQ-2' verdict
called equation-numeric an *unrecoverable global cipher*, while the 1st-place
writeup reports equation-numeric **deduce 95.5% / guess 52.9%** solvable via a
**per-prompt** 24-rule operator inventory (+ Observation 1/2 + operator priors).

This probe re-derives that inventory (`rules24.py`) and measures, on the REAL
`train.csv` equation-numeric prompts:
  * deduce (query operator appears in the examples) vs guess (unseen operator),
  * per-prompt operator-rule inference consistent with ALL example lines,
  * solved fraction (query answer matches ground truth via the official metric).

It is a *measurement*, not a hand-proof: it reports whatever fraction the
reconstructed inventory explains. A high deduce fraction refutes the global-cipher
premise for the deduce subset; a low one documents gaps in the re-derivation.

Usage:
    python eq_reprobe.py [--train /path/to/train.csv] [--limit N] [--show-fails K]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter, defaultdict

from rules24 import NON_JOIN_RULES, RULES, apply_rule, render_output_human

# official metric (extract/verify) lives in competitions/nvidia-nemotron/eval/
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import verify as official_verify  # noqa: E402

DEFAULT_TRAIN = os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")

ALL_RULES = ("join", "join_swap") + NON_JOIN_RULES

# Operator priors (writeup): '+' biased add-like, '-' sub-like, '*' mul-like.
# Equation-numeric operators are punctuation, not +-*, so priors apply only when
# the prompt's operator glyph is literally one of these (rare); kept for parity.
_PRIOR_GROUP = {"+": "add", "-": "sub", "*": "mul"}

_EX_RE = re.compile(r"^\s*(\d{2})(\D)(\d{2})\s*=\s*(.+?)\s*$")
_Q_RE = re.compile(r"determine the result for:\s*(\d{2})(\D)(\d{2})", re.I)


def is_equation_numeric(prompt: str) -> bool:
    if "transformation rules is applied to equations" not in prompt.lower():
        return False
    for ln in prompt.splitlines():
        if "determine" in ln.lower():
            continue
        m = _EX_RE.match(ln)
        if m:
            return True  # first example line has 2-digit operands
    return False


def parse_prompt(prompt: str):
    """Return (examples, query) where examples is {op: [(sA, sB, out_str), ...]}."""
    examples = defaultdict(list)
    query = None
    for ln in prompt.splitlines():
        if "determine the result for" in ln.lower():
            mq = _Q_RE.search(ln)
            if mq:
                query = (mq.group(1), mq.group(2), mq.group(3))
            continue
        m = _EX_RE.match(ln)
        if m:
            sA, op, sB, out = m.group(1), m.group(2), m.group(3), m.group(4)
            examples[op].append((sA, sB, out))
    return examples, query


def consistent_rules(op_symbol: str, exs):
    """Rules (from the 24) whose rendered output matches ALL examples of this op."""
    ok = []
    for rule in ALL_RULES:
        good = True
        for sA, sB, out in exs:
            tok = apply_rule(rule, sA, sB)
            if tok is None or render_output_human(tok, op_symbol) != out:
                good = False
                break
        if good:
            ok.append(rule)
    return ok


def disambiguate(op_symbol, candidates, prompt_mode, used_groups):
    """Narrow candidate rules with Observation 1 (mode) / 2 (group) + priors."""
    cand = list(candidates)
    # join group is exempt from mode/group observations.
    non_join = [r for r in cand if RULES[r]["group"] != "join"]
    join = [r for r in cand if RULES[r]["group"] == "join"]
    if prompt_mode is not None:
        non_join = [r for r in non_join if RULES[r]["mode"] == prompt_mode] or non_join
    if used_groups:
        narrowed = [r for r in non_join if RULES[r]["group"] not in used_groups]
        if narrowed:
            non_join = narrowed
    prior = _PRIOR_GROUP.get(op_symbol)
    pool = non_join + join
    if prior:
        pref = [r for r in pool if RULES[r]["group"] == prior]
        if pref:
            pool = pref
    return pool


def infer_prompt_mode_and_groups(examples):
    """Determine the single non-join mode and the set of used non-join groups.

    Observation 1: all non-join operators in a prompt share one mode.
    Observation 2: non-join operators do not reuse a group.
    We infer them from operators that have a UNIQUE consistent non-join rule first,
    then propagate.
    """
    op_candidates = {op: consistent_rules(op, exs) for op, exs in examples.items()}
    mode = None
    groups = set()
    # seed from unambiguous non-join operators
    for op, cands in op_candidates.items():
        non_join = [r for r in cands if RULES[r]["group"] != "join"]
        modes = {RULES[r]["mode"] for r in non_join}
        if len(modes) == 1:
            mode = next(iter(modes))
            break
    return op_candidates, mode


def solve_prompt(prompt: str):
    """Return dict(status, predicted, query_op, seen) or None if unparseable."""
    examples, query = parse_prompt(prompt)
    if not query or not examples:
        return None
    q_sA, q_op, q_sB = query
    seen = q_op in examples
    op_candidates, mode = infer_prompt_mode_and_groups(examples)

    # Resolve a rule per operator using observations, building used-groups greedily
    used_groups = set()
    resolved = {}
    # process operators with fewest candidates first (most constrained)
    for op in sorted(examples, key=lambda o: len(op_candidates[o])):
        cands = op_candidates[op]
        if not cands:
            continue
        pool = disambiguate(op, cands, mode, used_groups)
        if not pool:
            continue
        chosen = pool[0]
        resolved[op] = chosen
        if RULES[chosen]["group"] != "join":
            used_groups.add(RULES[chosen]["group"])

    # Determine the rule for the query operator
    if seen:
        rule = resolved.get(q_op)
        if rule is None:
            cands = op_candidates.get(q_op, [])
            pool = disambiguate(q_op, cands, mode, used_groups)
            rule = pool[0] if pool else None
    else:
        # guess: query operator unseen. Infer from prompt mode + unused group + priors.
        all_groups = ["add", "sub", "mul"]
        unused = [g for g in all_groups if g not in used_groups]
        cand_rules = [r for r in NON_JOIN_RULES if (mode is None or RULES[r]["mode"] == mode)]
        prior = _PRIOR_GROUP.get(q_op)
        if prior and prior in unused:
            cand_rules = [r for r in cand_rules if RULES[r]["group"] == prior] or cand_rules
        elif unused:
            cand_rules = [r for r in cand_rules if RULES[r]["group"] in unused] or cand_rules
        # writeup guess heuristic: early `join` candidate as fallback
        rule = cand_rules[0] if cand_rules else "join"

    if rule is None:
        return {"status": "no_rule", "predicted": None, "query_op": q_op, "seen": seen}
    tok = apply_rule(rule, q_sA, q_sB)
    if tok is None:
        return {"status": "no_rule", "predicted": None, "query_op": q_op, "seen": seen}
    predicted = render_output_human(tok, q_op)
    return {"status": "ok", "predicted": predicted, "query_op": q_op, "seen": seen, "rule": rule}


def run(train_path, limit=None, show_fails=0):
    rows = list(csv.DictReader(open(train_path, encoding="utf-8")))
    eqn = [r for r in rows if is_equation_numeric(r["prompt"])]
    if limit:
        eqn = eqn[:limit]
    tally = {"deduce": Counter(), "guess": Counter()}
    fails = []
    for r in eqn:
        res = solve_prompt(r["prompt"])
        bucket = "guess"
        if res is None:
            tally["deduce"]["unparsed"] += 1
            continue
        bucket = "deduce" if res["seen"] else "guess"
        tally[bucket]["total"] += 1
        if res["status"] == "ok" and res["predicted"] is not None and official_verify(r["answer"], res["predicted"]):
            tally[bucket]["solved"] += 1
        elif len(fails) < show_fails:
            fails.append((r, res))
    return eqn, tally, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=DEFAULT_TRAIN)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--show-fails", type=int, default=0)
    args = ap.parse_args()

    if not os.path.exists(args.train):
        raise SystemExit(
            f"train.csv not found at {args.train}\n"
            "Download (Kaggle creds required, read-only):\n"
            "  kaggle competitions download -c nvidia-nemotron-model-reasoning-challenge -p <dir>"
        )

    eqn, tally, fails = run(args.train, args.limit, args.show_fails)
    print(f"equation-numeric prompts: {len(eqn)}")
    print("(writeup split: deduce 596 / guess 136 = 732)\n")
    for bucket in ("deduce", "guess"):
        t = tally[bucket].get("total", 0)
        s = tally[bucket].get("solved", 0)
        pct = (100 * s / t) if t else 0.0
        ref = "95.5%" if bucket == "deduce" else "52.9%"
        print(f"  {bucket:7s}: {s}/{t}  = {pct:5.1f}%   (writeup solver-within-budget {ref})")
    for r, res in fails:
        print(f"\n--- FAIL (op={res['query_op']} seen={res['seen']} rule={res.get('rule')}) ---")
        print(f"gold={r['answer']!r} pred={res['predicted']!r}")
        print(r["prompt"][:300])


if __name__ == "__main__":
    main()
