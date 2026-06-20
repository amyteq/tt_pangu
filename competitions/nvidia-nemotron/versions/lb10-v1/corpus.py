"""Demo corpus builder for lb10-v1 (CPU; bit key-table + equation).

Provides `build_demo_corpus(n, seed)` -> [{id, category, answer, trace, solved}] for
the scorer / validation / learnability self-checks, built from the lb10-v1 solvers.
Every trace ends `\\boxed{...}`. `solved` = teacher solver matched gold (oracle flag).
LB10 keeps failed/low-conf traces, so unsolved records are retained (tagged solved=False).
"""

from __future__ import annotations

import bit_keytable_reasoner as bit
import equation_solver as eqs


def _bit(seed, i):
    truth, examples, q, ans = bit.generate(seed, n_examples=16)
    pred, meta = bit.solve(examples, q)
    abc = meta.get("abc") or (0, 0, 0)
    body = "<think>\n" + f"(a,b,c)={abc}\n" + "\n".join(f"{bit.to_bits(x)}>{bit.to_bits(o)}" for x, o in examples[:6])
    ans_s = bit.to_bits(ans)
    pred_s = bit.to_bits(pred if pred is not None else ans)
    return {
        "id": f"bit-{i}",
        "category": "bit",
        "answer": ans_s,
        "trace": body + f"\n</think>\n\\boxed{{{pred_s}}}",
        "solved": pred == ans,
    }


def _eq(seed, i):
    by_glyph, query, truth = eqs.generate(seed, deduce=True)
    pred, mode, op, w = eqs.solve(by_glyph, query)
    lines = ["<think>"]
    for g, exs in by_glyph.items():
        lines.append(f"{g}: " + " ; ".join(f"{a}{g}{b}={o}" for a, b, o in exs))
    lines.append(f"resolve {query[0]} -> {op}/{w} ({mode})")
    ans = pred if pred is not None else truth
    return {
        "id": f"eq-{i}",
        "category": "equation",
        "answer": str(truth),
        "trace": "\n".join(lines) + f"\n</think>\n\\boxed{{{ans}}}",
        "solved": str(pred) == str(truth),
    }


def build_demo_corpus(n, seed=0):
    recs = []
    per = max(1, n // 2)
    for i in range(per):
        recs.append(_eq(seed + i, i))
        recs.append(_bit(seed + i, i))
    return recs


if __name__ == "__main__":
    from collections import Counter

    recs = build_demo_corpus(30, seed=1)
    print("demo corpus:", Counter(r["category"] for r in recs))
    print("solved flags:", Counter(r["solved"] for r in recs))
