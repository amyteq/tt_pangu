"""Bit-manipulation rule-sequence catalog + Hamming repair (lb1-v1).

Re-derives the 1st-place "rule-sequence catalog": enumerate theoretically possible
8-bit transformations built from x / shift / rotate / not arguments combined by a
fixed set of 1-, 2-, and 3-input operators, convert each into **per-output-bit
operation notation** (an 8-rule sequence), and dedup.

Writeup target: **~5238 valid 8-rule sequences** (explicitly an *approximate*
sanity check — the writeup is prose and the exact enumeration grammar / dedup key
is unspecified; we report the actual count and document the grammar). Unlike the
signature catalog (exact 4205), this one is "≈" per the plan.

The *mechanism* (what matters for the method) is faithful and tested:
  * an 8-rule sequence is a tuple of 8 per-output-bit rules;
  * **HEX compression** of long bit columns frees token budget (`hex_compress`);
  * **repair** = nearest-neighbour projection of a heuristically-selected sequence
    onto the catalog by **Hamming distance over the 8 rule slots**, retrieving up
    to 32 candidates and applying the first whose function matches all examples.

Grammar (writeup "8-bit transformations enumerated"):
  unary primitives U = { x, not(x), shl1..7, shr1..7, rol1..7,
                         not(shl1..7), not(shr1..7), not(rol1..7) }   (44 named)
  1-input  : each u in U
  2-input  : xor/and/or (u1, u2)
  3-input  : maj, par3, ch, sel_nand_xnor, ao, oa, ax, ox, xa, xo (u1,u2,u3)
The arguments range over U. A per-output-bit rule = (op, source-bit-spec per arg).
Dedup is by the resulting 8-rule sequence.
"""

from __future__ import annotations

import argparse

# ---- unary primitives: each maps output bit i -> a "source" of the input -------
# source encoding: 0..15 = (input_bit_index<<1)|negated ; -1 = const 0 ; -2 = const 1
CONST0, CONST1 = -1, -2


def _src(bit: int, neg: bool) -> int:
    return (bit << 1) | (1 if neg else 0)


def _unary_primitives():
    """Return {name: [source_code for output bit 0..7]} (bit 0 = MSB, matching 8-char strings)."""
    prims = {}
    # x: output bit i reads input bit i
    prims["x"] = [_src(i, False) for i in range(8)]
    # not(x)
    prims["not_x"] = [_src(i, True) for i in range(8)]
    for k in range(1, 8):
        # shl k: out bit i = in bit (i+k) for an MSB-first string; bits shifted off the
        # right are filled with 0. (string << k drops leading chars, appends k zeros)
        shl = [(_src(i + k, False) if (i + k) < 8 else CONST0) for i in range(8)]
        shr = [(_src(i - k, False) if (i - k) >= 0 else CONST0) for i in range(8)]
        rol = [_src((i + k) % 8, False) for i in range(8)]
        prims[f"shl{k}"] = shl
        prims[f"shr{k}"] = shr
        prims[f"rol{k}"] = rol
        prims[f"not_shl{k}"] = [(CONST1 if s == CONST0 else s ^ 1) for s in shl]
        prims[f"not_shr{k}"] = [(CONST1 if s == CONST0 else s ^ 1) for s in shr]
        prims[f"not_rol{k}"] = [(s ^ 1) for s in rol]
    return prims


UNARY = _unary_primitives()
UNARY_NAMES = list(UNARY)

TWO_OPS = ("xor", "and", "or")
THREE_OPS = ("maj", "par3", "ch", "sel_nand_xnor", "ao", "oa", "ax", "ox", "xa", "xo")


def _eval_source(code: int, x: int) -> int:
    """Value (0/1) of a source code given input byte x (bit 0 = MSB)."""
    if code == CONST0:
        return 0
    if code == CONST1:
        return 1
    bit = code >> 1
    neg = code & 1
    v = (x >> (7 - bit)) & 1
    return v ^ neg if neg else v


def _two(op, a, b):
    if op == "xor":
        return a ^ b
    if op == "and":
        return a & b
    return a | b  # or


def _three(op, a, b, c):
    if op == "maj":
        return 1 if (a + b + c) >= 2 else 0
    if op == "par3":
        return a ^ b ^ c
    if op == "ch":  # choose a where s(=a) is 1 else b ... writeup: ch(s,a,b)
        return b if a == 1 else c
    if op == "sel_nand_xnor":  # s=a: nand(b,c) where s==1 else xnor(b,c)
        return (1 - (b & c)) if a == 1 else (1 if b == c else 0)
    if op == "ao":
        return (a & b) | c
    if op == "oa":
        return (a | b) & c
    if op == "ax":
        return (a & b) ^ c
    if op == "ox":
        return (a | b) ^ c
    if op == "xa":
        return (a ^ b) & c
    if op == "xo":
        return (a ^ b) | c
    raise ValueError(op)


def per_bit_sequence(op: str, args: tuple) -> tuple:
    """8-rule sequence for a transform: tuple over output bits of (op, source-codes)."""
    srcs = [UNARY[a] for a in args]
    seq = []
    for i in range(8):
        seq.append((op, tuple(s[i] for s in srcs)))
    return tuple(seq)


def transform_function(op: str, args: tuple):
    """Return a callable byte->byte for the transform (used by repair to test examples)."""
    srcs = [UNARY[a] for a in args]

    def fn(x: int) -> int:
        out = 0
        for i in range(8):
            vals = [_eval_source(s[i], x) for s in srcs]
            if len(vals) == 1:
                bit = vals[0]
            elif len(vals) == 2:
                bit = _two(op, vals[0], vals[1])
            else:
                bit = _three(op, vals[0], vals[1], vals[2])
            out |= (bit & 1) << (7 - i)
        return out

    return fn


def build_catalog(max_unary_for_three: int | None = None, verbose: bool = False):
    """Enumerate the grammar; return (sequences_set, meta).

    ``sequences_set`` is a set of 8-rule-sequence tuples (the dedup key).
    """
    seqs = {}
    names = UNARY_NAMES if max_unary_for_three is None else UNARY_NAMES[:max_unary_for_three]
    # 1-input
    for u in UNARY_NAMES:
        seq = per_bit_sequence("id", (u,))
        seqs.setdefault(seq, ("id", (u,)))
    # 2-input
    for op in TWO_OPS:
        for a in UNARY_NAMES:
            for b in UNARY_NAMES:
                seq = per_bit_sequence(op, (a, b))
                seqs.setdefault(seq, (op, (a, b)))
    # 3-input
    for op in THREE_OPS:
        for a in names:
            for b in names:
                for c in names:
                    seq = per_bit_sequence(op, (a, b, c))
                    seqs.setdefault(seq, (op, (a, b, c)))
    return seqs


CORE_PRIMS = (
    ["x", "not_x"]
    + [f"shl{k}" for k in range(1, 5)]
    + [f"shr{k}" for k in range(1, 5)]
    + [f"rol{k}" for k in range(1, 8)]
    + [f"not_shl{k}" for k in range(1, 5)]
    + [f"not_shr{k}" for k in range(1, 5)]
    + [f"not_rol{k}" for k in range(1, 8)]
)


def build_core_catalog(primitives=CORE_PRIMS):
    """A tractable, memorizable-scale catalog over a restricted primitive set.

    The full grammar over all 44 unaries overshoots the writeup's ~5238 (which was
    tuned to train.csv coverage and is not reproducible from prose). This core
    catalog keeps the *mechanism* (per-bit sequences + Hamming repair) at a usable
    size for repair NN and SFT memorisation; its count is reported, not forced.
    """
    seqs = {}
    for u in primitives:
        seqs.setdefault(per_bit_sequence("id", (u,)), ("id", (u,)))
    for op in TWO_OPS:
        for a in primitives:
            for b in primitives:
                seqs.setdefault(per_bit_sequence(op, (a, b)), (op, (a, b)))
    for op in THREE_OPS:
        for a in primitives:
            for b in primitives:
                for c in primitives:
                    seqs.setdefault(per_bit_sequence(op, (a, b, c)), (op, (a, b, c)))
    return seqs


def hamming(seq_a: tuple, seq_b: tuple) -> int:
    """Hamming distance over the 8 rule slots."""
    return sum(1 for x, y in zip(seq_a, seq_b) if x != y)


def repair(selected_seq: tuple, catalog_seqs, examples, k: int = 32):
    """Project a selected 8-rule sequence onto the catalog (writeup repair).

    examples = list of (in_byte, out_byte). Returns (repaired_seq, transform_repr)
    of the first of the <=k nearest catalog sequences whose function matches all
    examples, or None.
    """
    scored = sorted(catalog_seqs.items(), key=lambda kv: hamming(selected_seq, kv[0]))[:k]
    for seq, (op, args) in scored:
        fn = transform_function(op, args)
        if all(fn(i) == o for i, o in examples):
            return seq, (op, args)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=5238)
    ap.add_argument("--fast", action="store_true", help="restrict 3-input args (quick smoke)")
    args = ap.parse_args()

    cat = build_catalog(max_unary_for_three=12 if args.fast else None)
    n = len(cat)
    print(f"valid 8-rule sequences: {n}  (writeup target ~{args.target})")
    print(f"delta vs target       : {n - args.target:+d}")
    print(f"grammar: {len(UNARY_NAMES)} unary primitives, {len(TWO_OPS)} 2-input, {len(THREE_OPS)} 3-input ops")
    if args.fast:
        print("(--fast: 3-input args restricted; count is a lower bound for smoke only)")


if __name__ == "__main__":
    main()
