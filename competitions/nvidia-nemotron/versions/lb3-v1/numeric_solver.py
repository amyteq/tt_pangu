"""Minimal 13-op numeric solver + operation-family guessing (lb3-v1).

Reproduces the LB3 numeric lever (deduce 93.8% in the writeup): a deliberately
**minimal 13-operation** inventory, applied **globally** per problem in
simple/reverse structure, with **operation-family guessing** for an unseen query
operator (priority a-b, a+b, a*b — the writeup's family order).

The numeric category presents example lines ``x <sym> y = z`` for one or more
custom operator glyphs, then a query ``x <sym> y = ?``. Each glyph maps to exactly
one of the 13 ops. **Deduce** = query glyph appears in the examples; **guess** =
unseen glyph (resolve by family). Pure CPU; solve rates measured on synthetic
instances faithful to that structure.
"""

from __future__ import annotations

import argparse
import random

# 13-op minimal set, grouped by family (writeup guess priority: sub, add, mul).
OPS = {
    # subtraction family
    "sub": lambda a, b: a - b,
    "rsub": lambda a, b: b - a,
    "absdiff": lambda a, b: abs(a - b),
    # addition family
    "add": lambda a, b: a + b,
    "add1": lambda a, b: a + b + 1,
    "add_sq": lambda a, b: a + b * b,
    # multiplication family
    "mul": lambda a, b: a * b,
    "mul1": lambda a, b: a * b + 1,
    "mul_m1": lambda a, b: a * b - 1,
    # mixed / unary-ish
    "max": lambda a, b: max(a, b),
    "min": lambda a, b: min(a, b),
    "sum_sq": lambda a, b: a * a + b * b,
    "first": lambda a, b: a,
}
assert len(OPS) == 13, "the inventory must stay minimal (13 ops)"

FAMILY = {
    "sub": "sub",
    "rsub": "sub",
    "absdiff": "sub",
    "add": "add",
    "add1": "add",
    "add_sq": "add",
    "mul": "mul",
    "mul1": "mul",
    "mul_m1": "mul",
    "max": "mixed",
    "min": "mixed",
    "sum_sq": "mixed",
    "first": "mixed",
}
GUESS_FAMILY_ORDER = ["sub", "add", "mul", "mixed"]  # writeup priority


def consistent_ops(examples):
    """Ops whose output matches ALL example lines for a glyph."""
    return [name for name, fn in OPS.items() if all(fn(a, b) == z for a, b, z in examples)]


def solve_numeric(by_glyph: dict, query):
    """by_glyph: {glyph: [(a,b,z), ...]} ; query: (glyph, a, b).

    Returns (predicted, mode, op_name). mode in {'deduce','guess'}.
    """
    qglyph, qa, qb = query
    # resolve each seen glyph to its op (simple/reverse handled by the op set)
    resolved = {}
    used_families = set()
    for glyph, exs in by_glyph.items():
        cands = consistent_ops(exs)
        if cands:
            resolved[glyph] = cands[0]
            used_families.add(FAMILY[cands[0]])

    if qglyph in by_glyph:  # deduce
        cands = consistent_ops(by_glyph[qglyph])
        if cands:
            name = cands[0]
            return OPS[name](qa, qb), "deduce", name
        return None, "deduce", None

    # guess: unseen query glyph -> pick an op from an UNUSED family by priority
    for fam in GUESS_FAMILY_ORDER:
        if fam in used_families:
            continue
        for name, f in FAMILY.items():
            if f == fam:
                return OPS[name](qa, qb), "guess", name
    # fallback: first family in priority
    name = "sub"
    return OPS[name](qa, qb), "guess", name


_GLYPHS = list("@#$%&?!~^")


def generate_numeric_problem(seed: int, n_glyphs: int = 2, ex_per_glyph: int = 4, deduce: bool = True):
    rng = random.Random(seed)
    glyphs = rng.sample(_GLYPHS, n_glyphs + (0 if deduce else 1))
    op_names = rng.sample(list(OPS), len(glyphs))
    glyph_op = dict(zip(glyphs, op_names))
    by_glyph = {}
    seen = glyphs[:n_glyphs]
    for g in seen:
        fn = OPS[glyph_op[g]]
        by_glyph[g] = [(rng.randint(1, 20), rng.randint(1, 20)) for _ in range(ex_per_glyph)]
        by_glyph[g] = [(a, b, fn(a, b)) for a, b in by_glyph[g]]
    if deduce:
        qg = rng.choice(seen)
    else:
        qg = glyphs[-1]  # unseen glyph
    qa, qb = rng.randint(1, 20), rng.randint(1, 20)
    truth = OPS[glyph_op[qg]](qa, qb)
    return by_glyph, (qg, qa, qb), truth, glyph_op


def _measure(n, deduce):
    solved = 0
    for seed in range(n):
        by_glyph, query, truth, _ = generate_numeric_problem(seed, deduce=deduce)
        pred, mode, _name = solve_numeric(by_glyph, query)
        if pred == truth:
            solved += 1
    return solved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    d = _measure(args.n, deduce=True)
    g = _measure(args.n, deduce=False)
    print("numeric 13-op solver (global simple/reverse):")
    print(f"  deduce: {d}/{args.n} = {100 * d / args.n:5.1f}%   (writeup ref 93.8%)")
    print(
        f"  guess : {g}/{args.n} = {100 * g / args.n:5.1f}%   (family-order {GUESS_FAMILY_ORDER}; writeup guess ~57%)"
    )
    assert len(OPS) == 13
    print("  inventory size = 13 (minimal set OK)")


if __name__ == "__main__":
    main()
