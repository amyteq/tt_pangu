"""Extend the cokernel attack to the multiplicative-hash family out = K*in mod M.

If out = K*val(in) mod M under a base-36 value map sigma, then
    K*val(in) - val(out) = Σ_g sigma(g)*(K*cin[g] - cout[g]) ≡ 0 (mod M)
so M divides every 36x36 minor of the K-weighted difference matrix R_K.
For a WRONG K the minors share only the structural divisor; for the TRUE K,
gcd(minors) carries an extra factor M. Sweep K and flag any K whose minor-gcd
has a large non-{2,3} prime factor (a real modulus candidate) -> then solve sigma.
"""

import json
import math
import random

random.seed(0)
pairs = json.load(open("analysis/equation/global_pairs.json"))
ALPHA = sorted(set("".join(pairs)) | set("".join(pairs.values())))
GI = {g: i for i, g in enumerate(ALPHA)}
N = len(ALPHA)


def cin_cout(lhs, rhs):
    ci = [0] * N
    co = [0] * N
    L = len(lhs)
    for i, ch in enumerate(lhs):
        ci[GI[ch]] += 36 ** (L - 1 - i)
    L = len(rhs)
    for j, ch in enumerate(rhs):
        co[GI[ch]] += 36 ** (L - 1 - j)
    return ci, co


CIN = []
COUT = []
for k, v in pairs.items():
    a, b = cin_cout(k, v)
    CIN.append(a)
    COUT.append(b)


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


def largest_prime_factor_small(n, limit=10**7):
    """strip 2s and 3s, then trial-divide; return (residue_after_23, small_factors)."""
    f23 = {2: 0, 3: 0}
    while n % 2 == 0:
        n //= 2
        f23[2] += 1
    while n % 3 == 0:
        n //= 3
        f23[3] += 1
    # n is now the non-{2,3} part
    return n, f23


idx = list(range(len(CIN)))
print(f"pairs {len(CIN)}, sweeping K...")
flagged = []
for K in range(1, 61):
    G = 0
    for _ in range(6):
        rows = random.sample(idx, N)
        sub = [[K * CIN[r][g] - COUT[r][g] for g in range(N)] for r in rows]
        d = det_int(sub)
        if d:
            G = math.gcd(G, abs(d))
    nonstruct, f23 = largest_prime_factor_small(G)
    # nonstruct == 1 means G is purely 2^a 3^b (structural). Flag otherwise.
    if nonstruct != 1:
        flagged.append((K, G, nonstruct, f23))
        print(f"  K={K}: G has non-2/3 part = {nonstruct} (2^{f23[2]} 3^{f23[3]} * {nonstruct})")
if not flagged:
    print("No K in 1..60 yields a non-structural modulus -> multiplicative-hash out=K*in mod M unlikely.")
else:
    print(f"\n{len(flagged)} candidate K flagged; inspect the non-2/3 modulus part above.")
