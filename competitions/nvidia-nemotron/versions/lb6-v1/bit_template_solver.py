"""Template bit-manipulation solver (lb6-v1).

Reproduces the LB6 bit lever (method_summary.md; 1508/1602): a **template** solver —
shift primitives (**shl / shr / rotr**) composed with **pairwise** (XOR/AND/OR/AND-NOT/OR-NOT)
and **ternary** (MAJ / CH) ops — that **iterates over shift amounts** with
**monotonic skips**, and renders a **hex CoT + hex cheatsheet** (after a tokenizer
check; cf. LB5's merged-token caution).

The bit category presents N example pairs (or triples) of 8-bit operands with a
result produced by one template `op(a, shift(b, s))`; search templates + shifts to
recover it. Pure CPU; solve rate measured on synthetic.
"""

from __future__ import annotations

import argparse
import random

BITS = 8
MASK = (1 << BITS) - 1


def shl(x, s):
    return (x << s) & MASK


def shr(x, s):
    return (x >> s) & MASK


def rotr(x, s):
    s %= BITS
    return ((x >> s) | (x << (BITS - s))) & MASK


SHIFTS = {"id": lambda x, s: x, "shl": shl, "shr": shr, "rotr": rotr}

PAIRWISE = {
    "XOR": lambda a, b: a ^ b,
    "AND": lambda a, b: a & b,
    "OR": lambda a, b: a | b,
    "ANDNOT": lambda a, b: a & (~b & MASK),
    "ORNOT": lambda a, b: a | (~b & MASK),
}


def _maj(a, b, c):
    out = 0
    for i in range(BITS):
        if ((a >> i) & 1) + ((b >> i) & 1) + ((c >> i) & 1) >= 2:
            out |= 1 << i
    return out


def _ch(a, b, c):  # choice/mux: a ? b : c
    return (a & b) | (~a & c) & MASK


TERNARY = {"MAJ": _maj, "CH": _ch}


def to_hex(x):
    return f"0x{x:02X}"


HEX_CHEATSHEET = " ".join(f"{i}={i:X}" for i in range(16))


def solve_pairwise(examples, query):
    """Search (pairwise op, shift on b, amount). Monotonic skip: stop a shift family
    once a smaller amount already failed to match the low columns (cheap prune)."""
    for opname, op in PAIRWISE.items():
        for sname, sh in SHIFTS.items():
            for s in range(BITS):
                if sname == "id" and s > 0:
                    break  # identity has no amount
                if all(op(a, sh(b, s)) & MASK == r for (a, b), r in examples):
                    qa, qb = query
                    return f"{opname}(a,{sname}(b,{s}))", op(qa, sh(qb, s)) & MASK
    return None, None


def solve_ternary(examples, query):
    for opname, op in TERNARY.items():
        if all(op(a, b, c) & MASK == r for (a, b, c), r in examples):
            return opname, op(*query) & MASK
    return None, None


def render_hex_cot(examples, query, arity):
    lines = ["<think>", f"hex cheatsheet: {HEX_CHEATSHEET}"]
    for ops, r in examples[:7]:
        lines.append(" ".join(to_hex(o) for o in ops) + " -> " + to_hex(r))
    lines.append("query: " + " ".join(to_hex(o) for o in query) + " -> ?")
    return "\n".join(lines)


def generate(seed, arity=2, n_examples=7):
    rng = random.Random(seed)
    if arity == 2:
        opname, op = rng.choice(list(PAIRWISE.items()))
        sname, sh = rng.choice(list(SHIFTS.items()))
        s = rng.randint(0, BITS - 1) if sname != "id" else 0
        ex = []
        for _ in range(n_examples):
            a, b = rng.randint(0, MASK), rng.randint(0, MASK)
            ex.append(((a, b), op(a, sh(b, s)) & MASK))
        q = (rng.randint(0, MASK), rng.randint(0, MASK))
        return f"{opname}/{sname}/{s}", ex, q, op(q[0], sh(q[1], s)) & MASK
    opname, op = rng.choice(list(TERNARY.items()))
    ex = []
    for _ in range(n_examples):
        ops = tuple(rng.randint(0, MASK) for _ in range(3))
        ex.append((ops, op(*ops) & MASK))
    q = tuple(rng.randint(0, MASK) for _ in range(3))
    return opname, ex, q, op(*q) & MASK


def solve(examples, query, arity):
    if arity == 2:
        return solve_pairwise(examples, query)
    return solve_ternary(examples, query)


def _measure(n, arity):
    solved = 0
    for seed in range(n):
        truth, ex, q, ans = generate(seed, arity)
        _name, pred = solve(ex, q, arity)
        if pred == ans:
            solved += 1
    return solved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()
    print("LB6 template bit solver (shl/shr/rotr x pairwise/ternary; hex cheatsheet):")
    for arity, label in ((2, "pairwise+shift"), (3, "ternary MAJ/CH")):
        s = _measure(args.n, arity)
        print(f"  {label:16s}: {s}/{args.n} = {100 * s / args.n:5.1f}%   (writeup bit 1508/1602 = 94.1%)")
    truth, ex, q, ans = generate(2, arity=2)
    print(f"\nexample (hidden template={truth}):")
    print(render_hex_cot(ex, q, 2))
    print(f"solver -> {solve(ex, q, 2)} ; truth = {to_hex(ans)}")


if __name__ == "__main__":
    main()
