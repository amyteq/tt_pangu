"""Demo corpus builder for lb3-v1 (CPU; ties the per-category solvers together).

Builds {category, answer, trace} records from the lb3-v1 solvers so the scorer and
the validation harness can be exercised end-to-end without the (uncommitted)
competition train.csv. Every trace ends in an extractable ``\\boxed{...}``.

This stands in for the plan's "augment by resampling originals" stream: it produces
verified solver traces per category. On real data the same record shape is built
from train.csv rows (resampled operands/symbols), with leakage exclusion applied by
``validate.py``.
"""

from __future__ import annotations

import bit_hex_trace as bit
import cryptarithm_csp as cry
import numeric_solver as num

CATEGORIES = ("cryptarithm", "bit", "numeric")


def _boxed(trace_body: str, answer: str) -> str:
    return f"{trace_body}\n</think>\n\\boxed{{{answer}}}"


def cryptarithm_record(seed: int):
    p = cry.generate_problem(seed=seed, op="*", n_examples=6, deduce=True)
    trace = cry.emit_trace(p)  # already ends in </think>\boxed{...}
    return {"category": "cryptarithm", "answer": p.enc(p.qc), "trace": trace, "origin_seed": seed}


def bit_record(seed: int):
    truth, examples, q, ans = bit.generate_bit_problem(seed, n_examples=6)
    name, pred = bit.solve_bit(examples, q)
    body = "<think>\n" + bit.render_hex_trace(examples, q) + f"\nrule={name} (OR-NOT-first)"
    return {
        "category": "bit",
        "answer": bit.to_bits(ans),
        "trace": _boxed(body, bit.to_bits(pred if pred is not None else ans)),
        "origin_seed": seed,
    }


def numeric_record(seed: int):
    by_glyph, query, truth, _ = num.generate_numeric_problem(seed, deduce=True)
    pred, mode, opname = num.solve_numeric(by_glyph, query)
    lines = ["<think>"]
    for g, exs in by_glyph.items():
        lines.append(f"{g}: " + " ; ".join(f"{a}{g}{b}={z}" for a, b, z in exs))
    lines.append(f"resolve {query[0]} -> op={opname} ({mode})")
    body = "\n".join(lines)
    return {
        "category": "numeric",
        "answer": str(truth),
        "trace": _boxed(body, str(pred if pred is not None else truth)),
        "origin_seed": seed,
    }


_BUILDERS = {"cryptarithm": cryptarithm_record, "bit": bit_record, "numeric": numeric_record}


def build_demo_corpus(n: int, seed: int = 0):
    """Round-robin across categories; returns a list of records of length ~n."""
    recs = []
    per = max(1, n // len(CATEGORIES))
    for cat in CATEGORIES:
        for i in range(per):
            recs.append(_BUILDERS[cat](seed + i))
    return recs


if __name__ == "__main__":
    recs = build_demo_corpus(30, seed=1)
    from collections import Counter

    print("demo corpus:", Counter(r["category"] for r in recs))
    print("sample numeric trace:\n", next(r for r in recs if r["category"] == "numeric")["trace"])
