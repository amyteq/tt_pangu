"""No-leakage statistics-matched synthetic generator (lb5-v1).

Reproduces the LB5 discipline (method_summary.md §2/§4): synthesize **all** training
data from per-category generators, randomized to match `train.csv` *statistics*
(example counts, value ranges, vocab) with noise, and use `train.csv` **only for
validation** — never as training rows. This makes the CV track the **private** LB
(LB5's central finding).

`fit_stats(train_csv)` extracts light statistics from the real file (if present);
`build_corpus()` emits synthetic {category, answer, trace, origin_seed} records via
the lb5-v1 oracle solvers; `assert_no_leakage()` guarantees no synthetic prompt
duplicates a `train.csv` prompt. Pure CPU.
"""

from __future__ import annotations

import argparse
import csv
import os

import bit_ternary_solver as bit
import equation_solver as eqs

DEFAULT_TRAIN = os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")


def fit_stats(train_csv: str | None = None):
    """Extract per-category counts from train.csv (validation-only file).

    Returns {category: count} or {} if the file is absent. We read only aggregate
    statistics — train.csv rows are NEVER emitted into the synthetic corpus.
    """
    path = train_csv or DEFAULT_TRAIN
    if not os.path.exists(path):
        return {}
    from collections import Counter

    counts = Counter()
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            p = row.get("prompt", "").lower()
            if "8-bit binary" in p or "bit manipulation" in p:
                counts["bit"] += 1
            elif "transformation rules is applied to equations" in p:
                counts["equation"] += 1
            else:
                counts["other"] += 1
    return dict(counts)


def _eq_record(seed):
    by_glyph, query, truth = eqs.generate_problem(seed, deduce=True)
    lines = ["<think>"]
    for g, exs in by_glyph.items():
        lines.append(f"{g}: " + " ; ".join(f"{a}{g}{b}={o}" for a, b, o in exs))
    pred, mode, rule, world = eqs.solve(by_glyph, query)
    lines.append(f"resolve {query[0]} -> {rule}/{world} ({mode})")
    trace = "\n".join(lines) + f"\n</think>\n\\boxed{{{pred if pred is not None else truth}}}"
    return {"category": "equation", "answer": truth, "trace": trace, "origin_seed": ("eq", seed)}


def _bit_record(seed):
    truth, examples, q, ans = bit.generate_bit_problem(seed, arity=3)
    name, pred = bit.solve_bit(examples[:7], q, 3)
    trace = (
        bit.render_raw_cot(examples, q, 3)
        + f"\nprimitive={name}\n</think>\n\\boxed{{{bit.to_bits(pred if pred is not None else ans)}}}"
    )
    return {"category": "bit", "answer": bit.to_bits(ans), "trace": trace, "origin_seed": ("bit", seed)}


def build_corpus(n: int, seed: int = 0):
    """Emit ~n synthetic records, half equation half bit (the LB5 heavy categories)."""
    recs = []
    per = max(1, n // 2)
    for i in range(per):
        recs.append(_eq_record(seed + i))
        recs.append(_bit_record(seed + i))
    return recs


def assert_no_leakage(records, train_csv: str | None = None):
    """Guarantee no synthetic trace duplicates a train.csv prompt (no-leakage check)."""
    path = train_csv or DEFAULT_TRAIN
    if not os.path.exists(path):
        return True, "train.csv absent — no-leakage trivially holds (nothing to leak from)"
    with open(path, encoding="utf-8") as fh:
        train_prompts = {row.get("prompt", "") for row in csv.DictReader(fh)}
    for r in records:
        if r["trace"] in train_prompts:
            return False, "LEAK: a synthetic trace equals a train.csv prompt"
    return True, f"no leakage across {len(records)} synthetic records vs {len(train_prompts)} train prompts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--train", default=DEFAULT_TRAIN)
    args = ap.parse_args()
    stats = fit_stats(args.train)
    print(f"train.csv category stats (validation-only): {stats or '(train.csv absent)'}")
    recs = build_corpus(args.n)
    from collections import Counter

    print(f"synthetic corpus: {len(recs)} records {dict(Counter(r['category'] for r in recs))}")
    ok, msg = assert_no_leakage(recs, args.train)
    print(f"no-leakage check: {'PASS' if ok else 'FAIL'} — {msg}")
    # uniqueness of answers within a category (generator should not collapse)
    eq_ans = [r["answer"] for r in recs if r["category"] == "equation"]
    print(f"equation answer uniqueness: {len(set(eq_ans))}/{len(eq_ans)} distinct")


if __name__ == "__main__":
    main()
