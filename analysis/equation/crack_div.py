"""Test the division/mod-of-operands hypothesis (EQ-2' round-2 lead).

Hypothesis family: split the 5 input glyphs into A (a base-36 number under a secret
value map sigma) and B (a smaller field, the divisor/modulus), and
    out = floor(A / B)   or   out = A mod B   (or B/A, B mod A).
Output is the base-36 encoding of the result under the same sigma.

We test each (split, op) and several sigma seeds. For floor-div the valid-interval
penalty is smooth, so we hill-climb sigma by swapping value assignments.

Decisive signal: if a (split, op, sigma) reaches a high EXACT-match rate, cracked.
A flat result near chance across all variants => this family is also wrong.
"""

import json
import random

random.seed(0)
pairs = json.load(open("analysis/equation/global_pairs.json"))
ALPHA = sorted(set("".join(pairs)) | set("".join(pairs.values())))
N = len(ALPHA)
items = [(k, v) for k, v in pairs.items()]

DIGITS = [c for c in ALPHA if c.isdigit()]
SYMS = [c for c in ALPHA if not c.isdigit()]


def val36(s, sig):
    n = 0
    for ch in s:
        n = n * 36 + sig[ch]
    return n


def encode36(n, sig_inv, length):
    """encode integer n into `length` base-36 glyphs (None if it doesn't fit)."""
    digs = []
    for _ in range(length):
        digs.append(sig_inv[n % 36])
        n //= 36
    if n != 0:
        return None
    return "".join(reversed(digs))


def make_seeds():
    seeds = {}
    # seed 1: digits->0..9, symbols->10..35 in alpha order
    s = {}
    for i, d in enumerate(DIGITS):
        s[d] = i
    for i, c in enumerate(SYMS):
        s[c] = 10 + i
    seeds["digits_natural"] = s
    # seed 2: pure alpha-sorted order 0..35
    seeds["alpha_sorted"] = {c: i for i, c in enumerate(ALPHA)}
    # seed 3..5: random
    for r in range(3):
        vals = list(range(36))
        rng = random.Random(100 + r)
        rng.shuffle(vals)
        seeds[f"rand{r}"] = {c: vals[i] for i, c in enumerate(ALPHA)}
    return seeds


def split_AB(k, sa):
    return k[:sa], k[sa:]


def predict(k, sa, op, sig, sig_inv, out_len):
    A_s, B_s = split_AB(k, sa)
    A, B = val36(A_s, sig), val36(B_s, sig)
    if op == "floordiv_AB":
        if B == 0:
            return None
        r = A // B
    elif op == "mod_AB":
        if B == 0:
            return None
        r = A % B
    elif op == "floordiv_BA":
        if A == 0:
            return None
        r = B // A
    elif op == "mod_BA":
        if A == 0:
            return None
        r = B % A
    else:
        return None
    return encode36(r, sig_inv, out_len)


def exact_rate(sa, op, sig):
    sig_inv = {v: k for k, v in sig.items()}
    hit = 0
    for k, v in items:
        if predict(k, sa, op, sig, sig_inv, len(v)) == v:
            hit += 1
    return hit


def soft_penalty(sa, op, sig):
    """For floordiv_AB: distance of A from the valid interval [out*B,(out+1)*B)."""
    pen = 0
    for k, v in items:
        A_s, B_s = split_AB(k, sa)
        A, B = val36(A_s, sig), val36(B_s, sig)
        out = val36(v, sig)
        if op == "floordiv_AB":
            if B == 0:
                pen += 10**8
                continue
            lo, hi = out * B, (out + 1) * B
            if A < lo:
                pen += lo - A
            elif A >= hi:
                pen += A - hi + 1
        elif op == "mod_AB":
            if B == 0:
                pen += 10**8
                continue
            pen += abs((A % B) - out)
    return pen


def main():
    seeds = make_seeds()
    ops = ["floordiv_AB", "mod_AB", "floordiv_BA", "mod_BA"]
    print(f"{len(items)} pairs, N={N}")
    print("=== seed exact-match rates (no search) ===")
    best = None
    for sa in (1, 2, 3, 4):
        for op in ops:
            for sname, sig in seeds.items():
                h = exact_rate(sa, op, sig)
                if h > 30:
                    print(f"  split A=in[:{sa}] {op:13s} seed={sname:14s} exact={h}/{len(items)}")
                if best is None or h > best[0]:
                    best = (h, sa, op, sname)
    print("best seed:", best, f"(chance≈{len(items) / 36:.0f} for len-1 only)")

    # Hill-climb the best floordiv_AB config with the soft penalty
    print("\n=== hill-climb (soft penalty) on the most promising floordiv split ===")
    for sa in (3, 4):
        op = "floordiv_AB"
        sig = dict(seeds["digits_natural"])
        rng = random.Random(7)
        cur = soft_penalty(sa, op, sig)
        chars = list(sig)
        for it in range(4000):
            a, b = rng.sample(chars, 2)
            sig[a], sig[b] = sig[b], sig[a]
            new = soft_penalty(sa, op, sig)
            if new <= cur:
                cur = new
            else:
                sig[a], sig[b] = sig[b], sig[a]
            if it % 1000 == 999:
                print(f"  A=in[:{sa}] iter {it + 1}: penalty {cur:.3e} exact {exact_rate(sa, op, sig)}")
        print(f"  -> A=in[:{sa}] final exact {exact_rate(sa, op, sig)}/{len(items)}")


if __name__ == "__main__":
    main()
