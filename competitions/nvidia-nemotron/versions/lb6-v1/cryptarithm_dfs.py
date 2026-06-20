"""DFS cryptarithm solver with reversed search (lb6-v1).

Reproduces the LB6 cryptarithm lever (method_summary.md; 240/654 deduce, ~40% solved
*reversed*): a **tree search** over the digit<->symbol bijection with

  * **reversed search** — also try the equation with reversed operand/result digit
    order (LB6 reports ~40% of solves come from the reversed pass);
  * **leading-zero pruning** — a multi-digit number's leading symbol != 0;
  * **equation-sorting** — assign the most-constrained symbols first (those appearing
    in the shortest / most examples) to keep the search bounded;
  * **units-digit pruning** (op-deduction proxy) — prune as soon as a fully-known
    last column is inconsistent.

LB6's cryptarithm is a *plainer* DFS than LB1's signature catalog / LB3's CSP+two-stage
(hence its ~17% category) — this module reproduces that plainer mechanism. Validated on
synthetic instances with a known secret mapping. Pure CPU.
"""

from __future__ import annotations

import argparse
import random

OPS = {"*": lambda a, b: a * b, "+": lambda a, b: a + b}
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _gen(seed, op="*", n_examples=5):
    rng = random.Random(seed)
    syms = rng.sample(_ALPHABET, 10)
    mapping = {d: syms[d] for d in range(10)}

    def enc(n):
        return "".join(mapping[int(d)] for d in str(n))

    def operand():
        return rng.randint(2, 9) if rng.random() < 0.35 else rng.randint(10, 99)

    examples = []
    seen = set()
    for _ in range(n_examples):
        a, b = operand(), operand()
        c = OPS[op](a, b)
        examples.append((enc(a), op, enc(b), enc(c)))
        seen.update(str(a) + str(b) + str(c))
    for _ in range(200):
        qa, qb = operand(), operand()
        qc = OPS[op](qa, qb)
        if set(str(qa) + str(qb) + str(qc)).issubset(seen):
            return mapping, examples, (enc(qa), op, enc(qb)), enc(qc)
    return mapping, examples, (enc(qa), op, enc(qb)), enc(qc)


def _decode(s, assign):
    v = 0
    for ch in s:
        if ch not in assign:
            return None
        v = v * 10 + assign[ch]
    return v


def _dfs(examples, reverse):
    """DFS over the bijection. Returns assignment dict or None. equation-sorting +
    leading-zero + units pruning; `reverse` flips operand/result digit strings."""

    def rv(s):
        return s[::-1] if reverse else s

    exs = [(rv(a), op, rv(b), rv(c)) for a, op, b, c in examples]
    syms = set("".join(a + b + c for a, _o, b, c in exs))
    # equation-sorting: most frequent symbols first (most constrained)
    freq = {s: 0 for s in syms}
    for a, _o, b, c in exs:
        for ch in a + b + c:
            freq[ch] += 1
    order = sorted(syms, key=lambda s: -freq[s])
    leading = {n[0] for a, _o, b, c in exs for n in (a, b, c) if len(n) > 1}
    units = [(a[-1], b[-1], c[-1], op) for a, op, b, c in exs]

    def units_ok(assign):
        for ua, ub, uc, op in units:
            if ua in assign and ub in assign and uc in assign:
                f = (assign[ua] * assign[ub]) % 10 if op == "*" else (assign[ua] + assign[ub]) % 10
                if assign[uc] != f:
                    return False
        return True

    def full_ok(assign):
        for a, op, b, c in exs:
            if all(ch in assign for ch in a + b + c):
                if OPS[op](_decode(a, assign), _decode(b, assign)) != _decode(c, assign):
                    return False
        return True

    def bt(i, assign, used):
        if i == len(order):
            return dict(assign)
        s = order[i]
        for d in range(10):
            if d in used or (d == 0 and s in leading):
                continue
            assign[s] = d
            used.add(d)
            if units_ok(assign) and full_ok(assign):
                r = bt(i + 1, assign, used)
                if r:
                    return r
            used.discard(d)
            del assign[s]
        return None

    return bt(0, {}, set())


def solve(examples, query):
    """Try forward search, then reversed search (LB6: ~40% of solves are reversed)."""
    for reverse in (False, True):
        sol = _dfs(examples, reverse)
        if sol:
            qa, op, qb = query
            a = _decode(qa[::-1] if reverse else qa, sol)
            b = _decode(qb[::-1] if reverse else qb, sol)
            if a is None or b is None:
                continue
            res = str(OPS[op](a, b))
            inv = {d: ch for ch, d in sol.items()}
            try:
                enc = "".join(inv[int(d)] for d in res)
            except KeyError:
                continue
            return (enc[::-1] if reverse else enc), ("reversed" if reverse else "forward")
    return None, None


def _measure(n, op):
    solved = 0
    rev = 0
    for seed in range(n):
        mapping, examples, query, truth = _gen(seed, op=op)
        pred, how = solve(examples, query)
        if pred == truth:
            solved += 1
            if how == "reversed":
                rev += 1
    return solved, rev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    args = ap.parse_args()
    print("LB6 DFS cryptarithm solver (reversed search + leading-zero/units/equation-sorting pruning):")
    for op in ("*", "+"):
        s, rev = _measure(args.n, op)
        print(
            f"  op={op!r}: solved {s}/{args.n} = {100 * s / args.n:5.1f}%  ({rev} via reversed pass)  (writeup deduce 240/654=37%)"
        )


if __name__ == "__main__":
    main()
