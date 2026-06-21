"""Equation_numeric solver — frequency-deduce + two-axis guess (lb10-v1).

Reproduces the LB10 equation lever (method_summary.md; deduce 93.1%):
  * **deduce**: order operator-rule candidates by **frequency** (prefer the rule that
    explains the most example lines for the glyph), then apply to the query;
  * **two-axis guess** for an unseen query operator:
      - *operation axis*: **conventional-if-free** (use the conventional op for the
        glyph if its family is unused) else the **first-unused** of
        {add, unsigned abs-diff (absdiff), mul};
      - *wrapper axis*: **pinned** from the wrapper of the most-example-seen operator
        (NORMAL vs REVERSE), shared across the prompt.

LB10-specific re-expression of the per-prompt inventory. Validated on synthetic; the
shared real-`train.csv` premise re-test is `eq_reprobe.py`.
"""

from __future__ import annotations

import argparse
import random

# operation axis (families) + wrapper axis (NORMAL/REVERSE output rendering)
OPS = {
    "add": lambda a, b: a + b,
    "absdiff": lambda a, b: abs(a - b),
    "mul": lambda a, b: a * b,
    "sub": lambda a, b: a - b,
    "mod": lambda a, b: a % b if b else 0,
}
GUESS_OP_ORDER = ["add", "absdiff", "mul"]  # writeup two-axis guess priority
WRAPPERS = ["NORMAL", "REVERSE"]


def _wrap(v, w):
    neg = v < 0
    s = str(abs(v))
    if w == "REVERSE":
        s = s[::-1]
    return ("-" if neg else "") + s


def _render(op, w, a, b):
    return _wrap(OPS[op](a, b), w)


def _freq_candidates(examples):
    """(op, wrapper) candidates ordered by how many examples they explain (desc)."""
    scored = []
    for op in OPS:
        for w in WRAPPERS:
            hits = sum(1 for a, b, o in examples if _render(op, w, a, b) == o)
            if hits:
                scored.append((hits, op, w))
    scored.sort(key=lambda t: -t[0])
    return scored


def solve(by_glyph, query):
    """Returns (pred, mode, op, wrapper). deduce = frequency-ordered; guess = two-axis."""
    qg, qa, qb = query
    # pin the wrapper from the most-example-seen operator
    wrapper_votes = {}
    seen_ops = set()
    for g, exs in by_glyph.items():
        cands = _freq_candidates(exs)
        if cands:
            _h, op, w = cands[0]
            wrapper_votes[w] = wrapper_votes.get(w, 0) + len(exs)
            seen_ops.add(op)
    pinned_wrapper = max(wrapper_votes, key=wrapper_votes.get) if wrapper_votes else "NORMAL"

    if qg in by_glyph:  # deduce: frequency-ordered candidate for the query glyph
        cands = _freq_candidates(by_glyph[qg])
        if cands:
            _h, op, w = cands[0]
            return _render(op, w, qa, qb), "deduce", op, w
        return None, "deduce", None, None

    # two-axis guess: operation = first-unused of {add, absdiff, mul}; wrapper pinned
    used_families = {op for op in seen_ops}
    op = next((o for o in GUESS_OP_ORDER if o not in used_families), GUESS_OP_ORDER[0])
    return _render(op, pinned_wrapper, qa, qb), "guess", op, pinned_wrapper


_GLYPHS = list("@#$%&?!~^+=<>/")


def generate(seed, n_glyphs=3, ex=4, deduce=True):
    rng = random.Random(seed)
    glyphs = rng.sample(_GLYPHS, n_glyphs + (0 if deduce else 1))
    ops = rng.sample(list(OPS), min(len(glyphs), len(OPS)))
    while len(ops) < len(glyphs):
        ops.append(rng.choice(list(OPS)))
    w = rng.choice(WRAPPERS)  # one wrapper per prompt
    gop = {g: ops[i] for i, g in enumerate(glyphs)}
    seen = glyphs[:n_glyphs]
    by_glyph = {
        g: [
            (lambda a, b: (a, b, _render(gop[g], w, a, b)))(rng.randint(10, 99), rng.randint(10, 99)) for _ in range(ex)
        ]
        for g in seen
    }
    qg = rng.choice(seen) if deduce else glyphs[-1]
    qa, qb = rng.randint(10, 99), rng.randint(10, 99)
    return by_glyph, (qg, qa, qb), _render(gop[qg], w, qa, qb)


def _measure(n, deduce):
    return sum(1 for s in range(n) if (lambda bg, q, t: solve(bg, q)[0] == t)(*generate(s, deduce=deduce)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    n = args.n
    print("LB10 equation solver (frequency-deduce + two-axis guess):")
    print(f"  deduce: {_measure(n, True)}/{n} = {100 * _measure(n, True) / n:5.1f}%   (writeup 93.1%)")
    print(f"  guess : {_measure(n, False)}/{n} = {100 * _measure(n, False) / n:5.1f}%   (two-axis rebuild)")


if __name__ == "__main__":
    main()
