"""Rotate/shift key-table bit reasoner (lb10-v1) — the headline LB10 lever.

Reproduces the LB10 / 10th-place bit reasoner (method_summary.md / score_tricks.md;
"improve the teacher" → bit oracle toward ~98%): the true generator is modelled as a
**rotate/shift key-table**

    out[i] = F( rotl(x, a)[i], shl(x, b)[i], shr(x, c)[i] )

where ``F`` is a **3-bit-key → bit** lookup table (8 entries) read off the examples,
and ``(a, b, c)`` are small shift/rotate amounts recovered from the examples (the
**boundary bits** help: ``shl`` forces low bits to 0, ``shr`` forces high bits to 0,
which disambiguates b and c). Conflict-pruned key-table accumulation rejects an
``(a,b,c)`` whose key→bit map is inconsistent across examples; an agreement/majority
fallback fills keys unseen in the examples. Traces render compactly as ``key>value``.

This is a **single-operand** bit model (vs lb3 2-operand hex, lb5 ternary raw-bit,
lb13 3-input verify). Pure CPU; oracle (all-keys-seen) and with-fallback solve rates
are measured on synthetic instances with a known hidden (a,b,c,F).
"""

from __future__ import annotations

import argparse
import random

BITS = 8
MASK = (1 << BITS) - 1


def rotl(x, a):
    a %= BITS
    return ((x << a) | (x >> (BITS - a))) & MASK if a else x


def shl(x, b):
    return (x << b) & MASK


def shr(x, c):
    return (x >> c) & MASK


def _key(x, a, b, c, i):
    """3-bit key at position i: (rotl bit, shl bit, shr bit)."""
    return ((rotl(x, a) >> i) & 1) << 2 | ((shl(x, b) >> i) & 1) << 1 | ((shr(x, c) >> i) & 1)


def apply_keytable(x, a, b, c, table):
    """Compute output for x given (a,b,c) and a {key:bit} table (missing key -> 0)."""
    out = 0
    for i in range(BITS):
        out |= (table.get(_key(x, a, b, c, i), 0) & 1) << i
    return out


def _build_table(examples, a, b, c):
    """Accumulate key→bit from examples under (a,b,c); None on conflict (prune)."""
    table = {}
    for x, out in examples:
        for i in range(BITS):
            k = _key(x, a, b, c, i)
            bit = (out >> i) & 1
            if k in table and table[k] != bit:
                return None  # conflict -> this (a,b,c) is wrong
            table[k] = bit
    return table


def solve(examples, query, abc_range=BITS):
    """Recover (a,b,c) + key-table; return (pred, meta).

    meta: {abc, keys_seen, full_table (all 8 keys seen), fallback_used}.
    Picks the first conflict-free (a,b,c) that covers the most keys (oracle prefers
    a full 8-key table). Unseen query keys use a majority-bit fallback.
    """
    best = None
    for a in range(abc_range):
        for b in range(abc_range):
            for c in range(abc_range):
                table = _build_table(examples, a, b, c)
                if table is None:
                    continue
                cov = len(table)
                if best is None or cov > best[3]:
                    best = (a, b, c, cov, table)
                    if cov == 8:
                        break
            if best and best[3] == 8:
                break
        if best and best[3] == 8:
            break
    if best is None:
        return None, {"abc": None}
    a, b, c, cov, table = best
    # majority-bit fallback for keys unseen in the examples
    ones = sum(table.values())
    maj = 1 if ones * 2 >= max(len(table), 1) else 0
    fallback_used = False
    out = 0
    for i in range(BITS):
        k = _key(query, a, b, c, i)
        if k in table:
            bit = table[k]
        else:
            bit = maj
            fallback_used = True
        out |= (bit & 1) << i
    return out, {"abc": (a, b, c), "keys_seen": cov, "full_table": cov == 8, "fallback_used": fallback_used}


def to_bits(x):
    return format(x & MASK, f"0{BITS}b")


def render_trace(examples, query, a, b, c, table):
    """Compact key>value CoT (no per-example echo / candidate enumeration)."""
    lines = ["<think>", f"(a,b,c)=({a},{b},{c})"]
    lines.append("table: " + " ".join(f"{k:03b}>{v}" for k, v in sorted(table.items())))
    return "\n".join(lines)


def generate(seed, n_examples=8):
    rng = random.Random(seed)
    a, b, c = rng.randrange(BITS), rng.randrange(BITS), rng.randrange(BITS)
    table = {k: rng.randint(0, 1) for k in range(8)}  # full 3-bit-key -> bit table

    def fn(x):
        out = 0
        for i in range(BITS):
            out |= (table[_key(x, a, b, c, i)] & 1) << i
        return out

    xs = rng.sample(range(256), min(n_examples, 256))
    examples = [(x, fn(x)) for x in xs]
    q = rng.randrange(256)
    return (a, b, c, table), examples, q, fn(q)


def _measure(n, n_examples):
    solved = oracle = full = 0
    for seed in range(n):
        truth, examples, q, ans = generate(seed, n_examples)
        pred, meta = solve(examples, q)
        if pred == ans:
            solved += 1
        if meta.get("full_table"):
            full += 1
            if pred == ans:
                oracle += 1
    return solved, oracle, full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()
    print("LB10 rotate/shift key-table bit reasoner (out[i]=F(rotl(x,a),shl(x,b),shr(x,c))):")
    for ne in (args.examples, 16, 32):
        s, orc, full = _measure(args.n, ne)
        print(
            f"  {ne:2d} examples: solved {s}/{args.n} = {100 * s / args.n:5.1f}%   "
            f"full-table(oracle) {full}/{args.n}; oracle solve {orc}/{full or 1} = {100 * orc / (full or 1):5.1f}%"
        )
    print("  (writeup: 'improve the teacher' → bit oracle toward ~98% as examples cover all 8 keys)")
    truth, examples, q, ans = generate(0, 32)
    pred, meta = solve(examples, q)
    print(
        f"\nexample: hidden (a,b,c)={truth[:3]} -> recovered {meta['abc']}; pred={to_bits(pred)} truth={to_bits(ans)} ok={pred == ans}"
    )


if __name__ == "__main__":
    main()
