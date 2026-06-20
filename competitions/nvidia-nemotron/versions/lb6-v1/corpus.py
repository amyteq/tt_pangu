"""Demo corpus builder for lb6-v1 (CPU; equation + template-bit + DFS-cryptarithm).

Provides `build_demo_corpus(n, seed)` -> [{category, answer, trace}] for the scorer /
validation / DUMMY-probe self-checks, built from the lb6-v1 solvers. Every trace ends
in `\\boxed{...}`.
"""

from __future__ import annotations

import bit_template_solver as bit
import cryptarithm_dfs as cry
import equation_solver as eqs

CATEGORIES = ("equation", "bit", "cryptarithm")


def _eq(seed):
    by_glyph, query, truth = eqs.generate(seed, deduce=True)
    pred, mode, rule = eqs.solve(by_glyph, query)
    lines = ["<think>"]
    for g, exs in by_glyph.items():
        lines.append(f"{g}: " + " ; ".join(f"{a}{g}{b}={z}" for a, b, z in exs))
    lines.append(f"resolve {query[0]} -> {rule} ({mode})")
    ans = pred if pred is not None else truth
    return {"category": "equation", "answer": str(truth), "trace": "\n".join(lines) + f"\n</think>\n\\boxed{{{ans}}}"}


def _bit(seed):
    truth, ex, q, ans = bit.generate(seed, arity=2)
    name, pred = bit.solve(ex, q, 2)
    trace = (
        bit.render_hex_cot(ex, q, 2)
        + f"\ntemplate={name}\n</think>\n\\boxed{{{bit.to_hex(pred if pred is not None else ans)}}}"
    )
    return {"category": "bit", "answer": bit.to_hex(ans), "trace": trace}


def _cry(seed):
    mapping, examples, query, truth = cry._gen(seed, op="*")
    pred, how = cry.solve(examples, query)
    lines = ["<think>"]
    for a, op, b, c in examples:
        lines.append(f"{a}{op}{b}={c}")
    lines.append(f"DFS ({how}) resolve {query[0]}{query[1]}{query[2]}")
    ans = pred if pred is not None else truth
    return {"category": "cryptarithm", "answer": truth, "trace": "\n".join(lines) + f"\n</think>\n\\boxed{{{ans}}}"}


_B = {"equation": _eq, "bit": _bit, "cryptarithm": _cry}


def build_demo_corpus(n, seed=0):
    recs = []
    per = max(1, n // len(CATEGORIES))
    for cat in CATEGORIES:
        for i in range(per):
            recs.append(_B[cat](seed + i))
    return recs


if __name__ == "__main__":
    from collections import Counter

    recs = build_demo_corpus(30, seed=1)
    print("demo corpus:", Counter(r["category"] for r in recs))
