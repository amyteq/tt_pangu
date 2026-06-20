"""Ternary-extended byte-level bit solver (lb5-v1).

Reproduces the LB5 / 5th-place bit lever (method_summary.md; bit oracle 94.3%):
extend @huikang's byte-level (2-input) solver with **ternary (3-input) primitives**
(MAJORITY / CHOICE / XOR-NOT_OR ...), **15 primitives** total, operate on **raw bits**
(NOT merged-token / hex encodings — those broke the model, the LB5 negative lesson;
cf. `tokenizer_probe.py`), and **cut to ~7 examples** to fit the 7680-token budget.

The bit category presents N example tuples of 8-bit operands with a result produced
by one hidden bitwise primitive; infer it, apply to the query. Pure CPU; solve rate
and the 7-vs-10-example comparison are measured on synthetic instances.
"""

from __future__ import annotations

import argparse
import random

BITS = 8
MASK = (1 << BITS) - 1


def _bitwise3(fn):
    def g(a, b, c):
        out = 0
        for i in range(BITS):
            out |= (fn((a >> i) & 1, (b >> i) & 1, (c >> i) & 1) & 1) << i
        return out

    return g


# --- 15 primitives: 8 binary + 7 ternary ----------------------------------- #
BINARY = {
    "AND": lambda a, b: a & b,
    "OR": lambda a, b: a | b,
    "XOR": lambda a, b: a ^ b,
    "NAND": lambda a, b: ~(a & b) & MASK,
    "NOR": lambda a, b: ~(a | b) & MASK,
    "XNOR": lambda a, b: ~(a ^ b) & MASK,
    "AND_NOT": lambda a, b: a & (~b & MASK),
    "OR_NOT": lambda a, b: a | (~b & MASK),
}
TERNARY = {
    "MAJ3": _bitwise3(lambda x, y, z: 1 if (x + y + z) >= 2 else 0),
    "CHOICE": _bitwise3(lambda x, y, z: y if x else z),  # mux: x ? y : z
    "XOR_NOT_OR": _bitwise3(lambda x, y, z: (x ^ y) | (1 - z)),
    "CARRY": _bitwise3(lambda x, y, z: 1 if (x + y + z) >= 2 else 0),  # full-adder carry
    "SUM3": _bitwise3(lambda x, y, z: x ^ y ^ z),  # full-adder sum
    "AND3": _bitwise3(lambda x, y, z: x & y & z),
    "OR3": _bitwise3(lambda x, y, z: x | y | z),
}
assert len(BINARY) + len(TERNARY) == 15, "15-primitive inventory"
# OR-NOT-first within binary; ternary tried after binary (raw-bit, no search blowup)
BINARY_ORDER = ["OR_NOT", "AND_NOT", "OR", "XOR", "AND", "NAND", "NOR", "XNOR"]


def to_bits(x: int) -> str:
    return format(x & MASK, f"0{BITS}b")  # raw bits — the encoding LB5 kept


def solve_bit(examples, query, arity):
    """examples: [(operands_tuple, result_int)]; query: operands_tuple.

    Tries binary (OR-NOT-first) then ternary primitives on RAW bits. Returns
    (name, predicted_int) for the first primitive matching ALL examples.
    """
    if arity == 2:
        for name in BINARY_ORDER:
            fn = BINARY[name]
            if all(fn(*ops) & MASK == res for ops, res in examples):
                return name, fn(*query) & MASK
    else:
        for name, fn in TERNARY.items():
            if all(fn(*ops) & MASK == res for ops, res in examples):
                return name, fn(*query) & MASK
    return None, None


def generate_bit_problem(seed: int, arity: int, n_examples: int = 10):
    rng = random.Random(seed)
    pool = list(BINARY.items()) if arity == 2 else list(TERNARY.items())
    name, fn = rng.choice(pool)
    examples = []
    for _ in range(n_examples):
        ops = tuple(rng.randint(0, MASK) for _ in range(arity))
        examples.append((ops, fn(*ops) & MASK))
    q = tuple(rng.randint(0, MASK) for _ in range(arity))
    return name, examples, q, fn(*q) & MASK


def render_raw_cot(examples, q, arity):
    """Raw-bit CoT (no merged tokens). Cut to <=7 examples (LB5 token-budget fix)."""
    lines = ["<think>"]
    for ops, res in examples[:7]:
        lines.append(" ".join(to_bits(o) for o in ops) + " -> " + to_bits(res))
    lines.append("query: " + " ".join(to_bits(o) for o in q) + " -> ?")
    return "\n".join(lines)


def _measure(n, arity, cut):
    solved = 0
    for seed in range(n):
        truth, examples, q, ans = generate_bit_problem(seed, arity)
        used = examples[:cut]
        name, pred = solve_bit(used, q, arity)
        if pred == ans:
            solved += 1
    return solved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()
    print("LB5 ternary bit solver (raw bits, 15 primitives):")
    for arity, label in ((2, "binary "), (3, "ternary")):
        s10 = _measure(args.n, arity, 10)
        s7 = _measure(args.n, arity, 7)
        print(
            f"  {label}: 10-ex {s10}/{args.n} = {100 * s10 / args.n:5.1f}%   "
            f"7-ex cut {s7}/{args.n} = {100 * s7 / args.n:5.1f}%"
        )
    print(f"  primitives: {len(BINARY)} binary + {len(TERNARY)} ternary = 15; raw-bit encoding (no merged tokens)")
    truth, examples, q, ans = generate_bit_problem(3, arity=3)
    print(f"\nexample (hidden ternary primitive={truth}):")
    print(render_raw_cot(examples, q, 3))
    print(f"solver -> {solve_bit(examples[:7], q, 3)} ; truth = {ans} ({to_bits(ans)})")


if __name__ == "__main__":
    main()
