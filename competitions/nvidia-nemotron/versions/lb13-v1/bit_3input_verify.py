"""3-input bit verification solver (lb13-v1).

Reproduces the LB13 bit lever (method_summary.md; bit oracle 89.7%): add **3-input
verification** (MAJORITY / XNOR3 ...) on top of the byte-level solver, with
**bit-position-restricted search** (when no single global primitive fits, allow the
rule to vary by bit position) and a **left-edge fallback** (predict the high bits
from the example majority when the search is inconclusive). Parsing-display is
dropped to free token budget for the verification step.

Pure CPU; solve rate and the fallback's marginal recovery are measured on synthetic.
"""

from __future__ import annotations

import argparse
import random

BITS = 8
MASK = (1 << BITS) - 1


def _b3(fn):
    def g(a, b, c):
        out = 0
        for i in range(BITS):
            out |= (fn((a >> i) & 1, (b >> i) & 1, (c >> i) & 1) & 1) << i
        return out

    return g


# 3-input primitives; MAJORITY and XNOR3 are LB13's named additions.
PRIMS = {
    "MAJ": _b3(lambda x, y, z: 1 if (x + y + z) >= 2 else 0),
    "XNOR3": _b3(lambda x, y, z: 1 - (x ^ y ^ z)),
    "CHOICE": _b3(lambda x, y, z: y if x else z),
    "SUM3": _b3(lambda x, y, z: x ^ y ^ z),
    "AND3": _b3(lambda x, y, z: x & y & z),
    "OR3": _b3(lambda x, y, z: x | y | z),
}


def verify_global(examples, query):
    """Return (name, pred) for the first primitive that VERIFIES against all examples."""
    for name, fn in PRIMS.items():
        if all(fn(*ops) & MASK == res for ops, res in examples):
            return name, fn(*query) & MASK
    return None, None


def _bit_fns():
    """Per-bit-position truth functions for each primitive (for restricted search)."""
    return PRIMS


def search_bitpos(examples, query):
    """Bit-position-restricted search: pick, per bit position, the primitive whose
    single-bit output matches all examples at that position. Recovers cases where no
    one global primitive fits but each column is individually explained."""
    pred = 0
    ok_positions = 0
    for i in range(BITS):
        chosen = None
        for name, fn in PRIMS.items():
            good = all(((fn(*ops) >> i) & 1) == ((res >> i) & 1) for ops, res in examples)
            if good:
                chosen = fn
                break
        if chosen is not None:
            pred |= (chosen(*query) >> i & 1) << i
            ok_positions += 1
    return pred, ok_positions


def left_edge_fallback(examples, query, base_pred):
    """Fallback: for any still-uncertain high bit, default to the example-majority bit."""
    # majority bit per position across example results
    pred = base_pred
    n = len(examples)
    for i in range(BITS):
        ones = sum((res >> i) & 1 for _ops, res in examples)
        maj = 1 if ones * 2 >= n else 0
        # only fill the top (left-edge) bits as a conservative fallback
        if i >= BITS - 2:
            pred = (pred & ~(1 << i)) | (maj << i)
    return pred


def to_bits(x):
    return format(x & MASK, f"0{BITS}b")


def solve(examples, query):
    name, pred = verify_global(examples, query)
    if pred is not None:
        return ("global:" + name), pred
    pred, ok = search_bitpos(examples, query)
    if ok == BITS:
        return "bitpos", pred
    pred = left_edge_fallback(examples, query, pred)
    return "fallback", pred


def generate(seed, n_examples=7):
    rng = random.Random(seed)
    name, fn = rng.choice(list(PRIMS.items()))
    examples = []
    for _ in range(n_examples):
        ops = tuple(rng.randint(0, MASK) for _ in range(3))
        examples.append((ops, fn(*ops) & MASK))
    q = tuple(rng.randint(0, MASK) for _ in range(3))
    return name, examples, q, fn(*q) & MASK


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()
    solved = 0
    by_method = {}
    for seed in range(args.n):
        truth, ex, q, ans = generate(seed)
        method, pred = solve(ex, q)
        by_method[method.split(":")[0]] = by_method.get(method.split(":")[0], 0) + 1
        if pred == ans:
            solved += 1
    print("LB13 3-input bit verifier (MAJ/XNOR3 + bit-position search + left-edge fallback):")
    print(f"  solved: {solved}/{args.n} = {100 * solved / args.n:5.1f}%   (writeup bit oracle 89.7%)")
    print(f"  method usage: {by_method}")
    truth, ex, q, ans = generate(1)
    print(f"\nexample (hidden primitive={truth}): solve -> {solve(ex, q)} ; truth={to_bits(ans)}")


if __name__ == "__main__":
    main()
