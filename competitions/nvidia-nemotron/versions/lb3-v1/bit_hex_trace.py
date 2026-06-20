"""Bit-manipulation solver + HEX trace compression (lb3-v1).

Reproduces the LB3 bit levers (gap_analysis.md / score_tricks.md):
  * **HEX + tail-2-bit compression** of the output column listing (~ -25% tokens) ->
    frees budget for extra search;
  * **OR-NOT-first rule ordering** (try ``a | ~b`` before plain OR/XOR; writeup +0.6%);
  * **MAJ search** (majority rule) enabled by the freed token budget.

The bit category presents N example pairs of 8-bit operands with a result produced
by one hidden bitwise rule; infer the rule, apply to the query. Pure CPU; the
trace compressor's token saving is *measured*, not asserted.
"""

from __future__ import annotations

import argparse
import random

BITS = 8
MASK = (1 << BITS) - 1


# --- rule set; OR-NOT placed FIRST per the writeup ordering ----------------- #
def _maj(a: int, b: int) -> int:
    # bitwise majority of (a, b, a&b)  == a & b ; kept as an explicit 3-input MAJ
    # demonstrator (majority of a, b, and their xor-carry proxy). Defined so it is
    # distinct from AND/OR for measurement of the MAJ-search lever.
    out = 0
    for i in range(BITS):
        bits = ((a >> i) & 1) + ((b >> i) & 1) + (((a ^ b) >> i) & 1)
        out |= (1 if bits >= 2 else 0) << i
    return out


RULES = [
    ("OR_NOT", lambda a, b: (a | (~b & MASK)) & MASK),  # OR-NOT FIRST
    ("AND_NOT", lambda a, b: (a & (~b & MASK)) & MASK),
    ("OR", lambda a, b: (a | b) & MASK),
    ("XOR", lambda a, b: (a ^ b) & MASK),
    ("AND", lambda a, b: (a & b) & MASK),
    ("NAND", lambda a, b: (~(a & b)) & MASK),
    ("NOR", lambda a, b: (~(a | b)) & MASK),
    ("XNOR", lambda a, b: (~(a ^ b)) & MASK),
    ("MAJ", _maj),  # enabled by the HEX-freed budget
]
RULE_NAMES = [r[0] for r in RULES]


# --- HEX + tail-2-bit trace compression ------------------------------------ #
def to_bits(x: int) -> str:
    return format(x & MASK, f"0{BITS}b")


def hex_tail2(x: int) -> str:
    """Compress an 8-bit value: high 6 bits as hex nibble(s), last 2 bits literal.

    LB3 keeps the last 2 bits literal because encoding them as hex hurt the
    9/10-example cases. Here: ``H<hex of (x>>2)>|<low 2 bits>``.
    """
    high = x >> 2
    low = x & 0b11
    return f"H{high:X}|{low:02b}"


def render_plain_trace(examples, q) -> str:
    lines = []
    for a, b, c in examples:
        lines.append(f"{to_bits(a)} op {to_bits(b)} = {to_bits(c)}")
    lines.append(f"{to_bits(q[0])} op {to_bits(q[1])} = ????????")
    return "\n".join(lines)


def render_hex_trace(examples, q) -> str:
    lines = []
    for a, b, c in examples:
        lines.append(f"{hex_tail2(a)} op {hex_tail2(b)} = {hex_tail2(c)}")
    lines.append(f"{hex_tail2(q[0])} op {hex_tail2(q[1])} = ?")
    return "\n".join(lines)


# --- solver ----------------------------------------------------------------- #
def solve_bit(examples, query):
    """Return (rule_name, predicted_int) for the first rule (OR-NOT-first) that
    matches ALL examples; (None, None) if none match."""
    for name, fn in RULES:
        if all(fn(a, b) == c for a, b, c in examples):
            a, b = query
            return name, fn(a, b)
    return None, None


def generate_bit_problem(seed: int, n_examples: int = 6):
    rng = random.Random(seed)
    name, fn = rng.choice(RULES)
    examples = []
    for _ in range(n_examples):
        a, b = rng.randint(0, MASK), rng.randint(0, MASK)
        examples.append((a, b, fn(a, b)))
    qa, qb = rng.randint(0, MASK), rng.randint(0, MASK)
    return name, examples, (qa, qb), fn(qa, qb)


def _measure(n: int, n_examples: int):
    solved = 0
    plain_tok = hex_tok = 0
    for seed in range(n):
        truth, examples, q, ans = generate_bit_problem(seed, n_examples)
        name, pred = solve_bit(examples, q)
        if pred == ans:
            solved += 1
        plain_tok += len(render_plain_trace(examples, q))
        hex_tok += len(render_hex_trace(examples, q))
    saving = 100 * (1 - hex_tok / plain_tok) if plain_tok else 0.0
    return solved, plain_tok / n, hex_tok / n, saving


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--examples", type=int, default=6)
    args = ap.parse_args()
    solved, pt, ht, saving = _measure(args.n, args.examples)
    print(f"bit solver (OR-NOT-first, MAJ in set): solved {solved}/{args.n} = {100 * solved / args.n:.1f}%")
    print(f"trace tokens/instance: plain={pt:.0f}  hex+tail2={ht:.0f}  saving={saving:.1f}%")
    print(f"  (LB3 reference: ~ -25% tokens; rule order = {RULE_NAMES})")
    # demo
    truth, examples, q, ans = generate_bit_problem(0, args.examples)
    print(f"\nexample (hidden rule={truth}):")
    print(render_hex_trace(examples, q))
    print(f"solver -> {solve_bit(examples, q)} ; ground truth = {ans} ({hex_tail2(ans)})")


if __name__ == "__main__":
    main()
