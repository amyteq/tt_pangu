"""Factor the gcd-of-determinants G from crack_mod.py (Pollard rho).
Default G = 6^36 = 36^18 (structural artifact -> residue-preserving hypothesis dead)."""

import math
import random
import sys

random.seed(1)
G = int(sys.argv[1]) if len(sys.argv) > 1 else 10314424798490535546171949056


def is_prime(n):
    if n < 2:
        return False
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]:
        if n % p == 0:
            return n == p
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        ok = False
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                ok = True
                break
        if not ok:
            return False
    return True


def rho(n):
    if n % 2 == 0:
        return 2
    while True:
        c = random.randrange(1, n)
        x = random.randrange(2, n)
        y = x
        d = 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
        if d != n:
            return d


def fac(n, out):
    if n == 1:
        return
    if is_prime(n):
        out[n] = out.get(n, 0) + 1
        return
    d = rho(n)
    fac(d, out)
    fac(n // d, out)


f = {}
fac(G, f)
print("G =", G)
print("factorization:")
for p in sorted(f):
    print(f"  {p}^{f[p]}")
print("36^3 =", 36**3, " 36^4 =", 36**4, " 36^5 =", 36**5)
print("note 36 = 2^2*3^2, so 6^36 = 36^18 is a structural divisor (not the modulus)")
