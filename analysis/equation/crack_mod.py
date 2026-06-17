"""Cokernel attack on the residue-preserving hypothesis:
   out ≡ in (mod M) under a secret base-36 value map σ.

For each pair, val(in)-val(out) = Σ_g σ(g)·c[g], where c[g] is the signed
base-36 positional weight of glyph g (input positive, output negative).
If out ≡ in (mod M) then Σ_g σ(g)·c[g] ≡ 0 (mod M) for every pair.
=> the true σ vector lies in the mod-M nullspace of the count-matrix C.
=> M divides det of every 36×36 submatrix of C.  gcd(dets) is a multiple of M.
Recover M as a (large enough) divisor, then solve σ mod M and verify.
"""

import json
import random
from math import gcd

random.seed(0)
pairs = json.load(open("analysis/equation/global_pairs.json"))
ALPHA = sorted(set("".join(pairs)) | set("".join(pairs.values())))
GI = {g: i for i, g in enumerate(ALPHA)}
N = len(ALPHA)
assert N == 36


def cvec(lhs, rhs):
    v = [0] * N
    L = len(lhs)
    for i, ch in enumerate(lhs):
        v[GI[ch]] += 36 ** (L - 1 - i)
    L = len(rhs)
    for j, ch in enumerate(rhs):
        v[GI[ch]] -= 36 ** (L - 1 - j)
    return v


rows = [cvec(k, pairs[k]) for k in pairs]
print("rows", len(rows), "dim", N)


# integer determinant via fraction-free Bareiss
def det_int(M):
    M = [row[:] for row in M]
    n = len(M)
    sign = 1
    prev = 1
    for i in range(n):
        if M[i][i] == 0:
            sw = next((r for r in range(i + 1, n) if M[r][i] != 0), None)
            if sw is None:
                return 0
            M[i], M[sw] = M[sw], M[i]
            sign = -sign
        for r in range(i + 1, n):
            for c in range(i + 1, n):
                M[r][c] = (M[r][c] * M[i][i] - M[r][i] * M[i][c]) // prev
            M[r][i] = 0
        prev = M[i][i]
    return sign * M[n - 1][n - 1]


# gcd of several random 36x36 submatrix determinants
G = 0
tries = 0
for _ in range(12):
    sub = random.sample(rows, N)
    d = det_int(sub)
    tries += 1
    if d:
        G = gcd(G, abs(d))
    if G and len(str(G)) < 30 and G < 10**12:
        # already small enough
        pass
print("tries", tries, "gcd-of-dets G =", G, "(digits %d)" % len(str(G)))

if G == 0:
    print("G==0: submatrices are singular over Q -> residue-preserving structure UNLIKELY (or rank<36). STOP.")
else:
    # candidate moduli = divisors of G that are large enough (> max output value plausibly)
    # factor G
    def factor(n):
        f = {}
        d = 2
        while d * d <= n:
            while n % d == 0:
                f[d] = f.get(d, 0) + 1
                n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            f[n] = f.get(n, 0) + 1
        return f

    if G < 10**14:
        print("factor(G) =", factor(G))
    else:
        print("G too large to trial-factor quickly; printing G:", G)
