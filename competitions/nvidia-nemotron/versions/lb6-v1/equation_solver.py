"""Equation_numeric DFS solver — families + maxmodmin (lb6-v1).

Reproduces the LB6 equation lever (method_summary.md; equation guess 550/594 ≈ 93%,
the batch-high guess rate): per-prompt operator deduction over **add / sub / mul
families plus a maxmodmin family** (max, min, mod), with **family-exclusion guessing**
for an unseen query operator. This is the LB6-specific re-expression of the per-prompt
inventory (vs LB1's 24-rule, LB5's 2-world, LB13's global-reversal model).

Validated on synthetic; the shared real-`train.csv` premise re-test is `eq_reprobe.py`.
"""

from __future__ import annotations

import argparse
import random

FAMILIES = {
    "ADD": {"add": lambda a, b: a + b, "add1": lambda a, b: a + b + 1},
    "SUB": {"subab": lambda a, b: a - b, "subba": lambda a, b: b - a, "absdiff": lambda a, b: abs(a - b)},
    "MUL": {"mul": lambda a, b: a * b, "mul1": lambda a, b: a * b + 1},
    "MAXMODMIN": {
        "maxv": lambda a, b: max(a, b),
        "minv": lambda a, b: min(a, b),
        "mod": lambda a, b: a % b if b else 0,
    },
}
FAMILY_ORDER = ["SUB", "ADD", "MUL", "MAXMODMIN"]  # guess tie priority
RULE_FAMILY = {r: f for f, rs in FAMILIES.items() for r in rs}
RULE_FN = {r: fn for rs in FAMILIES.values() for r, fn in rs.items()}
RULE_ORDER = [r for f in FAMILY_ORDER for r in FAMILIES[f]]


def consistent(examples):
    return [r for r in RULE_ORDER if all(RULE_FN[r](a, b) == z for a, b, z in examples)]


def solve(by_glyph, query):
    qg, qa, qb = query
    used = set()
    for g in by_glyph:
        c = consistent(by_glyph[g])
        c = [r for r in c if RULE_FAMILY[r] not in used] or c
        if c:
            used.add(RULE_FAMILY[c[0]])
    if qg in by_glyph:  # deduce
        c = consistent(by_glyph[qg])
        if c:
            return RULE_FN[c[0]](qa, qb), "deduce", c[0]
        return None, "deduce", None
    for fam in FAMILY_ORDER:  # guess: unused family (maxmodmin gives LB6 its high guess)
        if fam not in used:
            r = next(iter(FAMILIES[fam]))
            return RULE_FN[r](qa, qb), "guess", r
    return RULE_FN["subab"](qa, qb), "guess", "subab"


_GLYPHS = list("@#$%&?!~^+=<>/")


def generate(seed, n_glyphs=3, ex=4, deduce=True):
    rng = random.Random(seed)
    glyphs = rng.sample(_GLYPHS, n_glyphs + (0 if deduce else 1))
    fams = rng.sample(FAMILY_ORDER, min(len(glyphs), len(FAMILY_ORDER)))
    while len(fams) < len(glyphs):
        fams.append(rng.choice(FAMILY_ORDER))
    grule = {g: rng.choice(list(FAMILIES[f])) for g, f in zip(glyphs, fams)}
    seen = glyphs[:n_glyphs]
    by_glyph = {
        g: [(lambda a, b: (a, b, RULE_FN[grule[g]](a, b)))(rng.randint(10, 99), rng.randint(10, 99)) for _ in range(ex)]
        for g in seen
    }
    qg = rng.choice(seen) if deduce else glyphs[-1]
    qa, qb = rng.randint(10, 99), rng.randint(10, 99)
    return by_glyph, (qg, qa, qb), RULE_FN[grule[qg]](qa, qb)


def _measure(n, deduce):
    return sum(1 for s in range(n) if (lambda bg, q, t: solve(bg, q)[0] == t)(*generate(s, deduce=deduce)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    n = args.n
    print("LB6 equation solver (add/sub/mul + maxmodmin families, family-exclusion guess):")
    print(f"  deduce: {_measure(n, True)}/{n} = {100 * _measure(n, True) / n:5.1f}%")
    print(
        f"  guess : {_measure(n, False)}/{n} = {100 * _measure(n, False) / n:5.1f}%   (writeup guess 550/594 = 92.6%)"
    )


if __name__ == "__main__":
    main()
