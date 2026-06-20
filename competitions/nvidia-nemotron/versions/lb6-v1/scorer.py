"""Local official-like scorer with the 7680-token budget rule (lb1-v1).

Reuses the ported official metric (`eval/official_metric.py`) for extraction +
verification, and adds the 1st-place "correct within the first 7680 tokens" rule:
if a trace exceeds the budget but the answer extracted from the truncated prefix
is still correct, it counts as correct (token budget is the binding design
constraint — gap_analysis.md). Also provides a per-category trace-token histogram.

This is the *extract+verify+accuracy* half of the metric; the *generation* half
(vLLM greedy, temp=0, max_tokens=7680) runs inside the Kaggle kernel.

    from scorer import score_within_budget, accuracy_within_budget
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import extract_final_answer, verify  # noqa: E402

MAX_TOKENS = 7680


def approx_tokens(text: str) -> int:
    """Nemotron tokenizer ~ 1 token / char (writeup); a real tokenizer is used in-kernel."""
    return len(text)


def truncate_to_budget(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """Approximate the kernel's max_tokens truncation by a char prefix."""
    return text[:max_tokens]


def score_within_budget(raw_output: str, gold: str, max_tokens: int = MAX_TOKENS) -> bool:
    """Correct if the answer extracted from the first ``max_tokens`` matches gold."""
    truncated = truncate_to_budget(raw_output, max_tokens)
    return verify(gold, extract_final_answer(truncated))


def accuracy_within_budget(golds, raw_outputs, max_tokens: int = MAX_TOKENS) -> float:
    golds, raw_outputs = list(golds), list(raw_outputs)
    if not golds:
        return 0.0
    correct = sum(score_within_budget(o, g, max_tokens) for g, o in zip(golds, raw_outputs))
    return correct / len(golds)


def category_coverage(records, max_tokens: int = MAX_TOKENS):
    """Catalog-coverage-within-budget per category (the plan's primary offline metric).

    ``records`` = iterable of dicts with keys category, answer, trace.
    Returns {category: (solved_within_budget, total, median_tokens)}.
    """
    from collections import defaultdict
    import statistics

    tot = defaultdict(int)
    ok = defaultdict(int)
    toks = defaultdict(list)
    for r in records:
        c = r["category"]
        tot[c] += 1
        toks[c].append(approx_tokens(r["trace"]))
        if score_within_budget(r["trace"], r["answer"], max_tokens):
            ok[c] += 1
    return {c: (ok[c], tot[c], statistics.median(toks[c]) if toks[c] else 0) for c in tot}


if __name__ == "__main__":
    # self-check on a tiny synthetic corpus built from the lb3-v1 solvers
    from corpus import build_demo_corpus

    recs = build_demo_corpus(60, seed=7)
    cov = category_coverage(recs)
    print(f"within-budget coverage (max_tokens={MAX_TOKENS}):")
    for c, (s, t, med) in sorted(cov.items()):
        print(f"  {c:18s} {s}/{t} = {100 * s / t:5.1f}%  median_tokens={med:.0f}")
    over = [r for r in recs if approx_tokens(r["trace"]) > MAX_TOKENS]
    print(f"traces over budget: {len(over)}/{len(recs)}")
