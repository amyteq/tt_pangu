"""Multiplication / polynomial seed-rate scan (nonlinear families the cokernel
attack can't reach). out candidates: A*B (split), (A*B) mod 36^len, product of all
digit values, and a*in^2+b*in+c style won't be scanned here (needs M). If every
variant sits at chance across seeds, the multiplicative family is also out."""

import json
import random

random.seed(0)
pairs = json.load(open("analysis/equation/global_pairs.json"))
ALPHA = sorted(set("".join(pairs)) | set("".join(pairs.values())))
DIGITS = [c for c in ALPHA if c.isdigit()]
SYMS = [c for c in ALPHA if not c.isdigit()]
items = list(pairs.items())


def val36(s, sig):
    n = 0
    for ch in s:
        n = n * 36 + sig[ch]
    return n


def enc36(n, inv, length):
    d = []
    for _ in range(length):
        d.append(inv[n % 36])
        n //= 36
    return None if n != 0 else "".join(reversed(d))


def seeds():
    out = {}
    s = {}
    for i, d in enumerate(DIGITS):
        s[d] = i
    for i, c in enumerate(SYMS):
        s[c] = 10 + i
    out["digits_nat"] = s
    out["alpha"] = {c: i for i, c in enumerate(ALPHA)}
    for r in range(3):
        v = list(range(36))
        random.Random(200 + r).shuffle(v)
        out[f"rand{r}"] = {c: v[i] for i, c in enumerate(ALPHA)}
    return out


def rate(fn, sig):
    inv = {v: k for k, v in sig.items()}
    hit = 0
    for k, v in items:
        try:
            r = fn(k, sig)
        except Exception:
            r = None
        if r is None:
            continue
        if enc36(r, inv, len(v)) == v:
            hit += 1
    return hit


def make_funcs():
    fns = {}
    for sa in (1, 2, 3, 4):
        fns[f"mulAB_s{sa}"] = lambda k, sig, sa=sa: val36(k[:sa], sig) * val36(k[sa:], sig)
        fns[f"mulAB_mod_s{sa}"] = lambda k, sig, sa=sa: (val36(k[:sa], sig) * val36(k[sa:], sig)) % (36**4)
    fns["prod_digits"] = lambda k, sig: sig[k[0]] * sig[k[1]] * sig[k[2]] * sig[k[3]] * sig[k[4]]
    fns["sum_sq"] = lambda k, sig: sum(sig[c] * sig[c] for c in k)
    return fns


def main():
    S = seeds()
    fns = make_funcs()
    n = len(items)
    print(f"{n} pairs; chance for an exact base-36 encode hit is tiny")
    best = (0, None, None)
    for fname, fn in fns.items():
        for sname, sig in S.items():
            h = rate(fn, sig)
            if h > 40:
                print(f"  {fname:16s} seed={sname:10s} exact={h}/{n}")
            if h > best[0]:
                best = (h, fname, sname)
    print("best:", best)


if __name__ == "__main__":
    main()
