"""Demo corpus builder for lb13-v1 (CPU; equation + 3-input-bit records).

Provides `build_demo_corpus(n, seed)` -> [{category, answer, trace, correct}] for the
scorer / validation self-checks, built from the lb13-v1 solvers. Every trace ends in
`\\boxed{...}`. Records carry a `correct` flag so `rebalance.py` can be exercised.
"""

from __future__ import annotations

import bit_3input_verify as bit
import equation_solver as eqs


def _eq_record(seed):
    by_glyph, query, truth = eqs.generate_problem(seed, deduce=True)
    pred, mode, rule, reverse = eqs.solve(by_glyph, query)
    lines = ["<think>"]
    for g, exs in by_glyph.items():
        lines.append(f"{g}: " + " ; ".join(f"{a}{g}{b}={o}" for a, b, o in exs))
    lines.append(f"global_reverse={reverse}; resolve {query[0]} -> {rule} ({mode})")
    ans = pred if pred is not None else truth
    trace = "\n".join(lines) + f"\n</think>\n\\boxed{{{ans}}}"
    return {
        "category": "equation",
        "answer": truth,
        "trace": trace,
        "correct": ans == truth,
        "origin_seed": ("eq", seed),
    }


def _bit_record(seed):
    truth, examples, q, ans = bit.generate(seed)
    method, pred = bit.solve(examples, q)
    lines = ["<think>"]
    for ops, res in examples:
        lines.append(" ".join(bit.to_bits(o) for o in ops) + " -> " + bit.to_bits(res))
    lines.append(f"verify {method}")
    p = pred if pred is not None else ans
    trace = "\n".join(lines) + f"\n</think>\n\\boxed{{{bit.to_bits(p)}}}"
    return {
        "category": "bit",
        "answer": bit.to_bits(ans),
        "trace": trace,
        "correct": p == ans,
        "origin_seed": ("bit", seed),
    }


def build_demo_corpus(n: int, seed: int = 0):
    recs = []
    per = max(1, n // 2)
    for i in range(per):
        recs.append(_eq_record(seed + i))
        recs.append(_bit_record(seed + i))
    return recs


if __name__ == "__main__":
    from collections import Counter

    recs = build_demo_corpus(20, seed=1)
    print("demo corpus:", Counter(r["category"] for r in recs))
    print("correct flags:", Counter(r["correct"] for r in recs))
